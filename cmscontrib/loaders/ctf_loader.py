#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2017 Kiarash Golezardi <kiarashgolezardi@gmail.com>
# Copyright © 2017 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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
import re
import subprocess
import zipfile

from datetime import timedelta
from tempfile import TemporaryDirectory

from cms.db import Task, Dataset, Manager, Testcase, Attachment, Statement

from .base_loader import TaskLoader

from cmscommon.constants import SCORE_MODE_MAX_SUBTASK


logger = logging.getLogger(__name__)


def make_timedelta(t):
    return timedelta(seconds=t)


class CtfTaskLoader(TaskLoader):
    """Loader for CTF formatted tasks.

    """

    short_name = 'ctf_task'
    description = 'CTF task format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(os.path.join(path, "metadata.json"))

    def task_has_changed(self):
        """See docstring in class Loader.

        """
        return True

    def _get_task_type_parameters_oo(self, data, evaluation_param):
        return [
            evaluation_param
        ]

    def _get_task_type_parameters_comm(self, data, has_grader):
        return [
            data["num_processes"],
            "stub" if has_grader else "alone",
            "fifo_io", # TODO: Support "std_io" as well
        ]

    def _get_task_type_parameters_batch(self, data, evaluation_param, has_grader):
        return [
            # alone:  Self-sufficient
            # grader: Compiled with grader
            "grader" if has_grader else "alone",
            [
                data['input_file'] if 'input_file' in data else '',
                data['output_file'] if 'output_file' in data else '',
            ],
            evaluation_param
        ]

    def get_task(self, get_statement=True):
        """See docstring in class Loader.

        """

        json_src = os.path.join(self.path, 'metadata.json')
        if not os.path.exists(json_src):
            logger.critical('No task found.')
            raise IOError('No task found at path %s' % json_src)

        with io.open(json_src, 'rt', encoding='utf-8') as json_file:
            data = json.load(json_file)
            if 'cms' in data:
                cms_specific_data = data['cms']
                logger.info("%s", str(cms_specific_data))
            else:
                cms_specific_data = {}

        short_name = data['short_name']
        logger.info("Loading parameters for task %s.", short_name)

        ## Args for Task object
        args = {}

        # TODO: We should probably use a friendlier name
        args["name"] = cms_specific_data['name'] if 'name' in cms_specific_data else short_name
        args["title"] = data['problem_name']

        # Statements
        if get_statement:
          logger.info('Statement requested')

          # Just pick english as the primary language
          args['statements'] = dict()
          args["primary_statements"] = ["en"]
          digest = self.file_cacher.put_file_from_path(
              os.path.join(self.path, 'statement.pdf'),
              "Statement for task %s" % (short_name,))
          args['statements']["en"] = Statement("en", digest)

        # Attachments
        args["attachments"] = dict()
        attachments_dir = os.path.join(self.path, 'attachments')
        if os.path.exists(attachments_dir):
            logger.info("Attachments found")
            for filename in sorted(os.listdir(attachments_dir)):
                digest = self.file_cacher.put_file_from_path(
                    os.path.join(attachments_dir, filename),
                    "Attachment %s for task %s" % (filename, short_name))
                args["attachments"][filename] = Attachment(filename, digest)

        # Obtaining testcases' codename
        # FIXME: Unzip or something?
        td = TemporaryDirectory()

        with zipfile.ZipFile(os.path.join(self.path, 'data.zip'), 'r') as zip_ref:
            zip_ref.extractall(td.name)

        testcase_codenames = sorted([
            filename[:-3]
            for filename in os.listdir(td.name)
            if filename[-3:] == '.in'])

        if "task_type" in data and data["task_type"] == "output_only":
            args["submission_format"] = ["output_%s.txt" % (cn,) for cn in testcase_codenames]
        else:
            args["submission_format"] = ["%s.%%l" % args["name"]]

        # These options cannot be configured in the CTF format.
        # Uncomment the following to set specific values for them.

        # No user tests for AIO
        # args['max_user_test_number'] = 10
        # args['min_user_test_interval'] = make_timedelta(60)
        # args['min_user_test_interval'] = make_timedelta(60)

        # No tokens for AIO
        # args['token_mode'] = 'infinite'
        # args['token_max_number'] = 100
        # args['token_min_interval'] = make_timedelta(60)
        # args['token_gen_initial'] = 1
        # args['token_gen_number'] = 1
        # args['token_gen_interval'] = make_timedelta(1800)
        # args['token_gen_max'] = 2

        # Takes best score for each subtask
        args['score_mode'] = SCORE_MODE_MAX_SUBTASK

        # Unlimited submissions per problem
        #args['max_submission_number'] = 50
        #args['max_user_test_number'] = 50
        
        # 60 seconds between submissions
        args['min_submission_interval'] = make_timedelta(60)

        args['score_precision'] = 2

        args['feedback_level'] = 'restricted'

        task = Task(**args)

        # Args for test data
        args = dict()

        args["task"] = task
        args["description"] = "Default" # Default dataset
        args["autojudge"] = True

        MB_TO_BYTES = 1024*1024
        if "task_type" not in data or data["task_type"] != "output_only":
            if "timelimit" in cms_specific_data:
                args["time_limit"] = float(cms_specific_data['timelimit'])
            else:
                args["time_limit"] = float(data['timelimit'])
            if "memlimit" in cms_specific_data:
                args["memory_limit"] = int(cms_specific_data['memlimit'])*MB_TO_BYTES
            else:
                args["memory_limit"] = int(data['memlimit'])*MB_TO_BYTES

        args["managers"] = {}

        # Graders
        has_grader_files = False
        managers_dir = os.path.join(self.path, 'managers')
        logger.info("Now for manager files {}".format(managers_dir))
        if os.path.exists(managers_dir):
            for manager_file in os.listdir(managers_dir):
                manager_file_path = os.path.join(managers_dir, manager_file)
                # Directories in managers/ are checker sources, so ignore.
                if os.path.isfile(manager_file_path):
                    logger.info("Found manager file {}".format(manager_file_path))
                    # We can make this assumption because the only non-grader
                    # manager files are checkers, which are not handled in this
                    # if statement
                    has_grader_files = True
                    manager_digest = self.file_cacher.put_file_from_path(
                        manager_file_path,
                        "Manager file %s for task %s" % (manager_file, short_name))
                    args["managers"][manager_file] = Manager(manager_file, manager_digest)

        # Checker
        # Unlike grader files, we have to compile the checker from source
        checker_dir = os.path.join(self.path, 'managers', 'checker')
        if os.path.isdir(checker_dir):
            evaluation_param = "comparator"
            subprocess.run(["make", "-C", checker_dir, "clean"])
            subprocess.run(["make", "-C", checker_dir, "all"])
            checker_digest = self.file_cacher.put_file_from_path(
                os.path.join(checker_dir, "bin", "checker"),
                "Checker for task %s" % (short_name,))
            args["managers"]["checker"] = Manager("checker", checker_digest)
        else:
            evaluation_param = "diff"

        # Manager
        # Unlike grader files, we have to compile the maager from source
        manager_dir = os.path.join(self.path, 'managers', 'manager')
        if os.path.isdir(manager_dir):
            subprocess.run(["make", "-C", manager_dir, "clean"])
            subprocess.run(["make", "-C", manager_dir, "all"])
            manager_digest = self.file_cacher.put_file_from_path(
                os.path.join(manager_dir, "bin", "manager"),
                "Manager for task %s" % (short_name,))
            args["managers"]["manager"] = Manager("manager", manager_digest)

        # Note that the original TPS worked with custom task type Batch2017
        # and Communication2017 instead of Batch and Communication.
        if "task_type" in data and data["task_type"] == "communication":
            args["task_type"] = "Communication"
            args["task_type_parameters"] = self._get_task_type_parameters_comm(
                data, has_grader_files)
        elif "task_type" in data and data["task_type"] == "output_only":
            args["task_type"] = "OutputOnly"
            args["task_type_parameters"] = self._get_task_type_parameters_oo(
                data, evaluation_param)
        else:
            args["task_type"] = "Batch"
            args["task_type_parameters"] = self._get_task_type_parameters_batch(
                data, evaluation_param, has_grader_files)

        # Manager (for Communcation tasks)
        # TODO: Add support for getting the manager

        # Testcases
        args["testcases"] = {}

        # Finally, upload testcases
        for codename in testcase_codenames:
            infile = os.path.join(td.name, "%s.in" % codename)
            outfile = os.path.join(td.name, "%s.out" % codename)
            if not os.path.exists(outfile):
                logger.critical(
                    'Could not find the output file for testcase %s', codename)
                logger.critical('Aborting...')
                return

            input_digest = self.file_cacher.put_file_from_path(
                infile,
                "Input %s for task %s" % (codename, short_name))
            output_digest = self.file_cacher.put_file_from_path(
                outfile,
                "Output %s for task %s" % (codename, short_name))
            testcase = Testcase(codename, True,
                                input_digest, output_digest)
            args["testcases"][codename] = testcase

        # Score Type
        cms_spec_path = os.path.join(self.path, 'cms_spec')
        if not os.path.exists(cms_spec_path):
            logger.critical('Could not find CMS spec. Aborting...')
            return
        with io.open(cms_spec_path, 'rt', encoding='utf-8') as f:
            cms_spec_string = f.read()

        # TODO: Support other score types
        args["score_type"] = "GroupMin"
        args["score_type_parameters"] = json.loads(cms_spec_string)

        dataset = Dataset(**args)
        task.active_dataset = dataset

        logger.info("Task parameters loaded.")

        return task