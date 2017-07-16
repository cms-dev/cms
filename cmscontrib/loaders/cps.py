#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2017 Kiarash Golezardi <kiarashgolezardi@gmail.com>
# Copyright © 2017 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import os
import re

from datetime import timedelta

from cms.db import Task, SubmissionFormatElement, Dataset, Manager, Testcase, Attachment, Statement
from cmscontrib import touch
from .base_loader import TaskLoader

logger = logging.getLogger(__name__)


def make_timedelta(t):
    return timedelta(seconds=t)


class CpsTaskLoader(TaskLoader):
    # TODO: doc string
    """ Loader for CPS exported tasks
    """

    short_name = 'cps_task'
    description = 'CPS task format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(os.path.join(path, "problem.json"))

    def task_has_changed(self):
        """See docstring in class Loader.

        """
        return True

    def _get_task_type_parameters(self, data, task_type, evaluation_param):
        parameters_str = data['task_type_params']
        if parameters_str is None or \
                parameters_str == '':
            parameters_str = '{}'
        task_type_parameters = json.loads(parameters_str)

        if task_type == 'Batch':
            if 'task_type_parameters_Batch_compilation' not in task_type_parameters:
                task_type_parameters['task_type_parameters_Batch_compilation'] = 'grader'
            if 'task_type_parameters_Batch_io_0_inputfile' not in task_type_parameters:
                task_type_parameters['task_type_parameters_Batch_io_0_inputfile'] = ''
            if 'task_type_parameters_Batch_io_1_outputfile' not in task_type_parameters:
                task_type_parameters['task_type_parameters_Batch_io_1_outputfile'] = ''
            if 'task_type_parameters_Batch_user_managers' not in task_type_parameters:
                pas_grader = os.path.join(self.path, 'graders', 'graderlib.pas')
                user_managers = '[\\"grader.cpp\\", \\"grader.java\\", \\"graderlib.pas\\"]'
                if not os.path.exists(pas_grader):
                    user_managers = '[\\"grader.%l\\"]'
                task_type_parameters['task_type_parameters_Batch_user_managers'] = user_managers
            return '["%s", ["%s", "%s"], "%s", "%s"]' % \
                   (task_type_parameters['task_type_parameters_Batch_compilation'],
                    task_type_parameters['task_type_parameters_Batch_io_0_inputfile'],
                    task_type_parameters['task_type_parameters_Batch_io_1_outputfile'],
                    evaluation_param,
                    task_type_parameters['task_type_parameters_Batch_user_managers'])

        if task_type == 'Communication':
            if 'task_type_parameters_Communication_num_processes' not in task_type_parameters:
                task_type_parameters['task_type_parameters_Communication_num_processes'] = 1
            return '[%s, "%s"]' % \
                   (task_type_parameters['task_type_parameters_Communication_num_processes'],
                    evaluation_param)

        if task_type == 'TwoSteps' or task_type == 'OutputOnly':
            return '["%s"]' % evaluation_param

        return ""

    def get_task(self, get_statement=True):
        """See docstring in class Loader.

        """

        json_src = os.path.join(self.path, 'problem.json')
        if not os.path.exists(json_src):
            logger.error('No task found.')
        with open(json_src) as json_file:
            data = json.load(json_file)

        name = data['code']
        logger.info("Loading parameters for task %s.", name)

        args = {}

        # Here we update the time of the last import.
        touch(os.path.join(self.path, ".itime"))
        # If this file is not deleted, then the import failed.
        touch(os.path.join(self.path, ".import_error"))

        args["name"] = name
        args["title"] = data['name']

        # Statements
        if get_statement:
            statements_dir = os.path.join(self.path, 'statements')
            if os.path.exists(statements_dir):
                statements = [filename for filename in
                              os.listdir(statements_dir) if filename[-4:] == ".pdf"]
                if len(statements) > 0:
                    args['statements'] = dict()
                    logger.info('Statements found')
                for statement in statements:
                    language = statement[:-4]
                    if language == "en_US":
                        args["primary_statements"] = '["en_US"]'
                    digest = self.file_cacher.put_file_from_path(
                        os.path.join(statements_dir, statement),
                        "Statement for task %s (lang: %s)" %
                        (name, language))
                    args['statements'][language] = Statement(language, digest)

        # Attachments
        args["attachments"] = dict()
        attachments_dir = os.path.join(self.path, 'attachments')
        if os.path.exists(attachments_dir):
            logger.info("Attachments found")
            for filename in os.listdir(attachments_dir):
                digest = self.file_cacher.put_file_from_path(
                    os.path.join(attachments_dir, filename),
                    "Attachment %s for task %s" % (filename, name))
                args["attachments"][filename] = Attachment(filename, digest)

        data["task_type"] = data["task_type"][0].upper() + data["task_type"][1:]

        # Setting the submission format
        # Obtaining testcases' codename
        testcases_dir = os.path.join(self.path, 'tests')
        if not os.path.exists(testcases_dir):
            logger.warning('Testcase folder was not found')
            testcase_codenames = []
        else:
            testcase_codenames = sorted([filename[:-3]
                                         for filename in os.listdir(testcases_dir)
                                         if filename[-3:] == '.in'])
        if data["task_type"] == 'OutputOnly':
            args["submission_format"] = list()
            for codename in testcase_codenames:
                args["submission_format"].append(SubmissionFormatElement("output_%s.txt" % codename))
        elif data["task_type"] == 'Notice':
            args["submission_format"] = list()
        else:
            args["submission_format"] = [SubmissionFormatElement("%s.%%l" % name)]

        # These options cannot be configured in the CPS format.
        # Uncomment the following to set specific values for them.

        # args['max_submission_number'] = 100
        # args['max_user_test_number'] = 100
        # args['min_submission_interval'] = make_timedelta(60)
        # args['min_user_test_interval'] = make_timedelta(60)

        # args['max_user_test_number'] = 10
        # args['min_user_test_interval'] = make_timedelta(60)

        # args['token_mode'] = 'infinite'
        # args['token_max_number'] = 100
        # args['token_min_interval'] = make_timedelta(60)
        # args['token_gen_initial'] = 1
        # args['token_gen_number'] = 1
        # args['token_gen_interval'] = make_timedelta(1800)
        # args['token_gen_max'] = 2

        args['score_precision'] = 2
        args['max_submission_number'] = 50
        args['max_user_test_number'] = 50
        if data["task_type"] == 'OutputOnly':
            args['max_submission_number'] = 100
            args['max_user_test_number'] = 100

        args['min_submission_interval'] = make_timedelta(60)
        args['min_user_test_interval'] = make_timedelta(60)

        task = Task(**args)

        args = dict()

        args["task"] = task
        args["description"] = "Default"
        args["autojudge"] = True

        if data['task_type'] != 'OutputOnly' and data['task_type'] != 'Notice':
            args["time_limit"] = float(data['time_limit'])
            args["memory_limit"] = int(data['memory_limit'])

        args["managers"] = {}

        # Checker
        checker_dir = os.path.join(self.path, "checker")
        checker_src = os.path.join(checker_dir, "checker.cpp")

        if os.path.exists(checker_src):
            logger.info("Checker found, compiling")
            checker_exe = os.path.join(checker_dir, "checker")
            os.system("g++ -x c++ -O2 -static -o %s %s" %
                      (checker_exe, checker_src))
            digest = self.file_cacher.put_file_from_path(
                checker_exe,
                "Manager for task %s" % name)
            args["managers"]['checker'] = Manager("checker", digest)
            evaluation_param = "comparator"
        else:
            logger.info("Checker not found, using diff if neccessary")
            evaluation_param = "diff"

        args["task_type"] = data['task_type']
        if data['task_type'] != 'OutputOnly' and data['task_type'] != 'Notice':
            args["task_type"] += '2017'
        args["task_type_parameters"] = \
            self._get_task_type_parameters(data, data['task_type'], evaluation_param)

        # Graders
        graders_dir = os.path.join(self.path, 'graders')

        if data['task_type'] == 'TwoSteps':
            pas_manager = name + 'lib.pas'
            pas_manager_path = os.path.join(graders_dir, pas_manager)
            if not os.path.exists(pas_manager_path):
                digest = self.file_cacher.put_file_content(
                    '', 'Pascal manager for task %s' % name)
                args["managers"][pas_manager] = Manager(pas_manager, digest)

        if not os.path.exists(graders_dir):
            logger.warning('Grader folder was not found')
            graders_list = []
        else:
            graders_list = \
                [filename for filename in os.listdir(graders_dir) if filename != 'manager.cpp']
        for grader_name in graders_list:
            grader_src = os.path.join(graders_dir, grader_name)
            digest = self.file_cacher.put_file_from_path(
                grader_src,
                "Manager for task %s" % name)
            args["managers"][grader_name] = Manager(grader_name, digest)

        # Manager
        manager_src = os.path.join(graders_dir, 'manager.cpp')

        if os.path.exists(manager_src):
            logger.info("Manager found, compiling")
            manager_exe = os.path.join(graders_dir, "manager")
            os.system("cat %s | \
                            g++ -x c++ -O2 -static -o %s -" %
                      (manager_src, manager_exe))
            digest = self.file_cacher.put_file_from_path(
                manager_exe,
                "Manager for task %s" % name)
            args["managers"]["manager"] = Manager("manager", digest)

        # Testcases
        args["testcases"] = {}

        for codename in testcase_codenames:
            infile = os.path.join(testcases_dir, "%s.in" % codename)
            outfile = os.path.join(testcases_dir, "%s.out" % codename)
            if not os.path.exists(outfile):
                logger.critical('Could not file the output file for testcase %s'
                                % codename)
                logger.critical('Aborting...')
                return

            input_digest = self.file_cacher.put_file_from_path(
                infile,
                "Input %s for task %s" % (codename, name))
            output_digest = self.file_cacher.put_file_from_path(
                outfile,
                "Output %s for task %s" % (codename, name))
            testcase = Testcase(codename, True,
                                input_digest, output_digest)
            args["testcases"][codename] = testcase

        # Score Type
        subtasks_dir = os.path.join(self.path, 'subtasks')
        if not os.path.exists(subtasks_dir):
            logger.warning('Subtask folder was not found')
            subtasks = []
        else:
            subtasks = sorted(os.listdir(subtasks_dir))

        if len(subtasks) == 0:
            number_tests = max(len(testcase_codenames), 1)
            args["score_type"] = "Sum"
            args["score_type_parameters"] = str(100 / number_tests)
        else:
            args["score_type"] = "GroupMin"
            parsed_data = []
            subtask_no = -1
            add_optional_name = False
            for subtask in subtasks:
                subtask_no += 1
                with open(os.path.join(subtasks_dir, subtask)) as subtask_json:
                    subtask_data = json.load(subtask_json)
                    score = int(subtask_data["score"])
                    testcases = "|".join(
                        re.escape(testcase)
                        for testcase in subtask_data["testcases"]
                    )
                    optional_name = "Subtask %d" % subtask_no
                    if subtask_no == 0 and score == 0:
                        add_optional_name = True
                        optional_name = "Samples"
                    if add_optional_name:
                        parsed_data.append([score, testcases, optional_name])
                    else:
                        parsed_data.append([score, testcases])
            args["score_type_parameters"] = json.dumps(parsed_data)

        dataset = Dataset(**args)
        task.active_dataset = dataset

        os.remove(os.path.join(self.path, ".import_error"))

        logger.info("Task parameters loaded.")

        return task
