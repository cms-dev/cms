#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2017 Kiarash Golezardi <kiarashgolezardi@gmail.com>
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import io
import json
import logging
import os

from datetime import timedelta

from cms.db import Task, SubmissionFormatElement, Dataset, Manager, Testcase

from .base_loader import TaskLoader


logger = logging.getLogger(__name__)


def make_timedelta(t):
    return timedelta(seconds=t)


class TpsTaskLoader(TaskLoader):
    """Loader for TPS exported tasks.

    """

    short_name = 'tps_task'
    description = 'TPS task format'

    # FIXME: stay?
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
        if parameters_str is None or parameters_str == '':
            parameters_str = '{}'
        task_type_parameters = json.loads(parameters_str)
        par_prefix = 'task_type_parameters_%s' % task_type
        if task_type == 'Batch':
            par_compilation = '%s_compilation' % par_prefix
            par_input = '%s_io_0_inputfile' % par_prefix
            par_output = '%s_io_1_outputfile' % par_prefix
            if par_compilation not in task_type_parameters:
                task_type_parameters[par_compilation] = 'alone'
            if par_input not in task_type_parameters:
                task_type_parameters[par_input] = ''
            if par_output not in task_type_parameters:
                task_type_parameters[par_output] = ''
            return '["%s", ["%s", "%s"], "%s"]' % \
                   (task_type_parameters[par_compilation],
                    task_type_parameters[par_input],
                    task_type_parameters[par_output],
                    evaluation_param)
        if task_type == 'Communication':
            par_processes = '%s_num_processes' % par_prefix
            if par_processes not in task_type_parameters:
                task_type_parameters[par_processes] = 1
            return '[%s]' % task_type_parameters[par_processes]
        return '[%s]' % evaluation_param

    def get_task(self, get_statement=True):
        """See docstring in class Loader.

        """

        json_src = os.path.join(self.path, 'problem.json')
        if not os.path.exists(json_src):
            logger.critical('No task found.')
            raise IOError('No task found at path %s' % json_src)
        with io.open(json_src, 'rt', encoding='utf-8') as json_file:
            data = json.load(json_file)

        name = data['code']
        logger.info("Loading parameters for task %s.", name)

        args = {}

        args["name"] = name
        args["title"] = data['name']

        # TODO: import statements

        args["submission_format"] = [SubmissionFormatElement("%s.%%l" % name)]

        # These options cannot be configured in the TPS format.
        # Uncomment the following to set specific values for them.

        # args['max_user_test_number'] = 10
        # args['min_user_test_interval'] = make_timedelta(60)

        # args['token_mode'] = 'infinite'
        # args['token_max_number'] = 100
        # args['token_min_interval'] = make_timedelta(60)
        # args['token_gen_initial'] = 1
        # args['token_gen_number'] = 1
        # args['token_gen_interval'] = make_timedelta(1800)
        # args['token_gen_max'] = 2

        # TODO: additional cms config files

        task = Task(**args)

        args = dict()

        args["task"] = task
        args["description"] = "Default"
        args["autojudge"] = True

        args["time_limit"] = float(data['time_limit'])
        args["memory_limit"] = int(data['memory_limit'])

        args["managers"] = {}

        # Checker
        checker_dir = os.path.join(self.path, "checker")
        checker_src = os.path.join(checker_dir, "checker.cpp")

        if os.path.exists(checker_src):
            logger.info("Checker found, compiling")
            checker_exe = os.path.join(checker_dir, "checker")
            os.system("cat %s | \
                g++ -x c++ -O2 -static -o %s -" %
                      (checker_src, checker_exe))
            digest = self.file_cacher.put_file_from_path(
                checker_exe,
                "Manager for task %s" % name)
            args["managers"]['checker'] = Manager("checker", digest)
            evaluation_param = "comparator"
        else:
            logger.info("Checker not found, using diff if necessary")
            evaluation_param = "diff"

        args["task_type"] = data['task_type']
        args["task_type_parameters"] = \
            self._get_task_type_parameters(
                data, data['task_type'], evaluation_param)

        # Graders
        graders_dir = os.path.join(self.path, 'graders')
        graders_list = \
            [filename
             for filename in os.listdir(graders_dir)
             if filename != 'manager.cpp']
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
            args["managers"] += [Manager("manager", digest)]

        # Testcases
        testcases_dir = os.path.join(self.path, 'tests')
        testcase_codenames = [filename[:-3]
                              for filename in os.listdir(testcases_dir)
                              if filename[-3:] == '.in']

        args["testcases"] = {}

        for codename in testcase_codenames:
            infile = os.path.join(testcases_dir, "%s.in" % codename)
            outfile = os.path.join(testcases_dir, "%s.out" % codename)
            if not os.path.exists(outfile):
                logger.critical(
                    'Could not find the output file for testcase %s', codename)
                logger.critical('Aborting...')
                exit()

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
        subtasks = os.listdir(subtasks_dir)

        if len(subtasks) == 0:
            number_tests = len(testcase_codenames)
            args["score_type"] = "Sum"
            args["score_type_parameters"] = str(100 / number_tests)
        else:
            args["score_type"] = "GroupMin"
            # FIXME: create the score_type_parameters

        dataset = Dataset(**args)
        task.active_dataset = dataset

        logger.info("Task parameters loaded.")

        return task
