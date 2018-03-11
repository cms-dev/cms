#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 Edoardo Morassutto <edoardo.morassutto@gmail.com>
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from six import iteritems

import imp
import io
import logging
import os

from datetime import datetime
from datetime import timedelta

import xml.etree.ElementTree as ET

from cms import config
from cms.db import Contest, User, Task, Statement, \
    SubmissionFormatElement, Dataset, Manager, Testcase
from cmscommon.crypto import build_password
from cmscontrib import touch

from .base_loader import ContestLoader, TaskLoader, UserLoader

logger = logging.getLogger(__name__)


def make_timedelta(t):
    return timedelta(seconds=t)


# TODO: add all languages.
LANGUAGE_MAP = {'english': 'en', 'russian': 'ru', 'italian': 'it'}


class PolygonTaskLoader(TaskLoader):
    """Load a task stored using the Codeforces Polygon format.

    Given the filesystem location of a unpacked task that was packaged
    in the Polygon format (tests should already be generated), parse
    those files and directories to produce data that can be consumed by
    CMS, i.e. a Task object

    Also, as Polygon doesn't support CMS directly, and doesn't allow
    to customize some task parameters, users can add task configuration
    files which will be parsed and applied as is. By default, all tasks
    are batch files, with custom checker and score type is Sum.

    Loaders assumes that checker is check.cpp and written with usage of
    testlib.h. It provides customized version of testlib.h which allows
    using Polygon checkers with CMS. Checkers will be compiled during
    importing the contest.

    """

    short_name = 'polygon_task'
    description = 'Polygon (XML-based) task format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(os.path.join(path, "problem.xml"))

    def task_has_changed(self):
        """See docstring in class Loader.

        """
        return True

    def get_task(self, get_statement=True):
        """See docstring in class Loader.

        """

        logger.info("Checking dos2unix presence")
        i = os.system('dos2unix -V 2>/dev/null')
        self.dos2unix_found = (i == 0)
        if not self.dos2unix_found:
            logger.error("dos2unix not found - tests will not be converted!")

        name = os.path.basename(self.path)
        logger.info("Loading parameters for task %s.", name)

        args = {}

        # Here we update the time of the last import.
        touch(os.path.join(self.path, ".itime"))
        # If this file is not deleted, then the import failed.
        touch(os.path.join(self.path, ".import_error"))

        # Get alphabetical task index for use in title.

        tree = ET.parse(os.path.join(self.path, "problem.xml"))
        root = tree.getroot()

        args["name"] = name
        args["title"] = root.find('names').find("name").attrib['value']

        if get_statement:
            args["statements"] = {}
            args["primary_statements"] = []
            for language, lang in iteritems(LANGUAGE_MAP):
                path = os.path.join(self.path, 'statements',
                                    '.pdf', language, 'problem.pdf')
                if os.path.exists(path):
                    digest = self.file_cacher.put_file_from_path(
                        path,
                        "Statement for task %s (lang: %s)" % (name,
                                                              language))
                    args["statements"][lang] = Statement(lang, digest)
                    args["primary_statements"].append(lang)

        args["submission_format"] = [SubmissionFormatElement("%s.%%l" % name)]

        # These options cannot be configured in the Polygon format.
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

        task_cms_conf_path = os.path.join(self.path, 'files', 'cms_conf.py')
        task_cms_conf = None
        if os.path.exists(task_cms_conf_path):
            logger.info("Found additional CMS options for task %s.", name)
            with open(task_cms_conf_path, 'r') as f:
                task_cms_conf = imp.load_module('cms_conf', f,
                                                task_cms_conf_path,
                                                ('.py', 'r', imp.PY_SOURCE))
        if task_cms_conf is not None and hasattr(task_cms_conf, "general"):
            args.update(task_cms_conf.general)

        task = Task(**args)

        judging = root.find('judging')
        testset = None
        for testset in judging:
            testset_name = testset.attrib["name"]

            args = {}
            args["task"] = task
            args["description"] = testset_name
            args["autojudge"] = False

            tl = float(testset.find('time-limit').text)
            ml = float(testset.find('memory-limit').text)
            args["time_limit"] = tl * 0.001
            args["memory_limit"] = ml

            args["managers"] = {}
            infile_param = judging.attrib['input-file']
            outfile_param = judging.attrib['output-file']

            # Checker can be in any of these two locations.
            checker_src = os.path.join(self.path, "files", "check.cpp")
            if not os.path.exists(checker_src):
                checker_src = os.path.join(self.path, "check.cpp")

            if os.path.exists(checker_src):
                logger.info("Checker found, compiling")
                checker_exe = os.path.join(
                    os.path.dirname(checker_src), "checker")
                testlib_path = "/usr/local/include/cms/testlib.h"
                if not config.installed:
                    testlib_path = os.path.join(os.path.dirname(__file__),
                                                "polygon", "testlib.h")
                os.system("cat %s | \
                    sed 's$testlib.h$%s$' | \
                    g++ -x c++ -O2 -static -o %s -" %
                          (checker_src, testlib_path, checker_exe))
                digest = self.file_cacher.put_file_from_path(
                    checker_exe,
                    "Manager for task %s" % name)
                args["managers"]["checker"] = Manager("checker", digest)
                evaluation_param = "comparator"
            else:
                logger.info("Checker not found, using diff")
                evaluation_param = "diff"

            args["task_type"] = "Batch"
            args["task_type_parameters"] = \
                ["alone", [infile_param, outfile_param], evaluation_param]

            args["score_type"] = "Sum"
            total_value = 100.0
            input_value = 0.0

            testcases = int(testset.find('test-count').text)

            n_input = testcases
            if n_input != 0:
                input_value = total_value / n_input
            args["score_type_parameters"] = input_value

            args["testcases"] = {}

            for i in range(testcases):
                infile = os.path.join(self.path, testset_name,
                                      "%02d" % (i + 1))
                outfile = os.path.join(self.path, testset_name,
                                       "%02d.a" % (i + 1))
                if self.dos2unix_found:
                    os.system('dos2unix -q %s' % (infile, ))
                    os.system('dos2unix -q %s' % (outfile, ))
                input_digest = self.file_cacher.put_file_from_path(
                    infile,
                    "Input %d for task %s" % (i, name))
                output_digest = self.file_cacher.put_file_from_path(
                    outfile,
                    "Output %d for task %s" % (i, name))
                testcase = Testcase("%03d" % (i, ), False,
                                    input_digest, output_digest)
                testcase.public = True
                args["testcases"][testcase.codename] = testcase

            if task_cms_conf is not None and \
               hasattr(task_cms_conf, "datasets") and \
               testset_name in task_cms_conf.datasets:
                args.update(task_cms_conf.datasets[testset_name])

            dataset = Dataset(**args)
            if testset_name == "tests":
                task.active_dataset = dataset

        os.remove(os.path.join(self.path, ".import_error"))

        logger.info("Task parameters loaded.")
        return task


class PolygonUserLoader(UserLoader):
    """Load a user stored using the Codeforces Polygon format.

    As Polygon doesn't support CMS directly, and doesn't allow
    to specify users, we support(?) a non-standard file named
    contestants.txt to allow importing some set of users.

    """

    short_name = 'polygon_user'
    description = 'Polygon (XML-based) user format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(
            os.path.join(os.path.dirname(path), "contestants.txt"))

    def user_has_changed(self):
        """See docstring in class Loader.

        """
        return True

    def get_user(self):
        """See docstring in class Loader.

        """

        username = os.path.basename(self.path)
        userdata = None

        # This is not standard Polygon feature, but useful for CMS users
        # we assume contestants.txt contains one line for each user:
        #
        # username;password;first_name;last_name;hidden
        #
        # For example:
        #
        # contestant1;123;Cont;Estant;0
        # jury;1234;Ju;Ry;1

        users_path = os.path.join(
            os.path.dirname(self.path), 'contestants.txt')
        if os.path.exists(users_path):
            with io.open(users_path, "rt", encoding="utf-8") as users_file:
                for user in users_file.readlines():
                    user = user.strip().split(';')
                    name = user[0].strip()
                    if name == username:
                        userdata = [x.strip() for x in user]

        if userdata is not None:
            logger.info("Loading parameters for user %s.", username)
            args = {}
            args['username'] = userdata[0]
            args['password'] = build_password(userdata[1])
            args['first_name'] = userdata[2]
            args['last_name'] = userdata[3]
            args['hidden'] = (len(userdata) > 4 and userdata[4] == '1')
            logger.info("User parameters loaded.")
            return User(**args)
        else:
            logger.critical(
                "User %s not found in contestants.txt file.", username)
            return None


class PolygonContestLoader(ContestLoader):
    """Load a contest stored using the Codeforces Polygon format.

    Given the filesystem location of a unpacked package of contest in
    the Polygon format, parse those files and directories to produce
    data that can be consumed by CMS, i.e. a Contest object.

    Polygon (by now) doesn't allow custom contest-wide files, so
    general contest options should be hard-coded in the loader.

    """

    short_name = 'polygon_contest'
    description = 'Polygon (XML-based) contest format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(os.path.join(path, "contest.xml")) and \
            os.path.exists(os.path.join(path, "problems"))

    def get_task_loader(self, taskname):
        taskpath = os.path.join(self.path, "problems", taskname)
        return PolygonTaskLoader(taskpath, self.file_cacher)

    def get_contest(self):
        """See docstring in class Loader.

        """

        name = os.path.split(self.path)[1]

        logger.info("Loading parameters for contest %s.", name)

        args = {}

        tree = ET.parse(os.path.join(self.path, "contest.xml"))
        root = tree.getroot()

        args['name'] = name

        # TODO: find proper way to choose contest primary language.

        self.primary_language = root.find('names') \
            .find('name').attrib['language']

        # All available contest languages are allowed to be used.

        self.languages = []
        for alternative_name in root.find('names'):
            self.languages.append(alternative_name.attrib['language'])

        logger.info("Contest languages are %s %s",
                    self.primary_language, str(self.languages))

        args['description'] = root.find('names') \
            .find("name[@language='%s']" % self.primary_language) \
            .attrib['value']

        logger.info("Contest description is %s", args['description'])

        # For now Polygon doesn't support custom contest-wide files,
        # so we need to hardcode some contest settings.

        args['start'] = datetime(1970, 1, 1)
        args['stop'] = datetime(1970, 1, 1)

        # Uncomment the following to set specific values for these
        # options.

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

        logger.info("Contest parameters loaded.")

        tasks = []
        for problem in root.find('problems'):
            tasks.append(os.path.basename(problem.attrib['url']))

        participations = []

        # This is not standard Polygon feature, but useful for CMS users
        # we assume contestants.txt contains one line for each user:
        #
        # username;password;first_name;last_name;hidden
        #
        # For example:
        #
        # contestant1;123;Cont;Estant;0
        # jury;1234;Ju;Ry;1

        users_path = os.path.join(self.path, 'contestants.txt')
        if os.path.exists(users_path):
            with io.open(users_path, "rt", encoding="utf-8") as users_file:
                for user in users_file.readlines():
                    user = user.strip()
                    user = user.split(';')
                    participations.append({
                        "username": user[0].strip(),
                        "password": build_password(user[1].strip()),
                        "hidden": user[4].strip()
                        # "ip" is not passed
                    })

        return Contest(**args), tasks, participations

    def contest_has_changed(self):
        """See docstring in class Loader.

        """
        return True
