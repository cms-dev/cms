#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import io
import os
import os.path
import yaml

from datetime import timedelta

from cms import LANGUAGES, logger
from cmscommon.DateTime import make_datetime
from cms.db.SQLAlchemyAll import \
    Contest, User, Task, Statement, Attachment, SubmissionFormatElement, \
    Dataset, Manager, Testcase
from cmscontrib.BaseLoader import Loader


def load(src, dst, src_name, dst_name=None, conv=lambda i: i):
    if dst_name is None:
        dst_name = src_name
    if src_name in src:
        dst[dst_name] = conv(src[src_name])


def make_timedelta(t):
    return timedelta(seconds=t)


class YamlLoader(Loader):
    """Load a contest stored using the Italian IOI format.

    Given the filesystem location of a contest saved in the Italian IOI
    format, parse those files and directories to produce data that can
    be consumed by CMS, i.e. a hierarchical collection of instances of
    the DB classes, headed by a Contest object, and completed with all
    needed (and available) child objects.

    """

    @classmethod
    def short_name(cls):
        """See docstring in class Loader.

        """
        return 'italy_yaml'

    @classmethod
    def description(cls):
        """See docstring in class Loader.

        """
        return 'Italian YAML-based format'

    @classmethod
    def detect(cls, path):
        """See docstring in class Loader.

        """
        # Not really refined...
        return os.path.exists(os.path.join(path, "contest.yaml"))

    def get_contest(self):
        """See docstring in class Loader.

        """

        name = os.path.split(self.path)[1]
        conf = yaml.safe_load(
            io.open(os.path.join(self.path, "contest.yaml"),
                    "rt", encoding="utf-8"))

        logger.info("Loading parameters for contest %s." % name)

        args = {}

        load(conf, args, "nome_breve", "name")
        load(conf, args, "nome", "description")

        assert name == args["name"]

        load(conf, args, "token_initial")
        load(conf, args, "token_max")
        load(conf, args, "token_total")
        load(conf, args, "token_min_interval", conv=make_timedelta)
        load(conf, args, "token_gen_time", conv=make_timedelta)
        load(conf, args, "token_gen_number")

        load(conf, args, "inizio", "start", conv=make_datetime)
        load(conf, args, "fine", "stop", conv=make_datetime)

        load(conf, args, "max_submission_number")
        load(conf, args, "max_user_test_number")
        load(conf, args, "min_submission_interval", conv=make_timedelta)
        load(conf, args, "min_user_test_interval", conv=make_timedelta)

        logger.info("Contest parameters loaded.")

        self.tasks_order = dict((name, num)
                                for num, name in enumerate(conf["problemi"]))
        self.users_conf = dict((user['username'], user)
                               for user in conf["utenti"])

        tasks = conf["problemi"]
        users = self.users_conf.keys()

        return Contest(**args), tasks, users

    def get_user(self, username):
        """See docstring in class Loader.

        """
        logger.info("Loading parameters for user %s." % username)
        conf = self.users_conf[username]
        assert username == conf['username']

        args = {}

        load(conf, args, "username")

        load(conf, args, "password")
        load(conf, args, "ip")

        load(conf, args, "nome", "first_name")
        load(conf, args, "cognome", "last_name")

        if "first_name" not in args:
            args["first_name"] = ""
        if "last_name" not in args:
            args["last_name"] = args["username"]

        load(conf, args, "fake", "hidden", lambda a: a == "True")

        logger.info("User parameters loaded.")

        return User(**args)

    def get_task(self, name):
        """See docstring in class Loader.

        """
        num = self.tasks_order[name]

        conf = yaml.safe_load(
            io.open(os.path.join(self.path, name + ".yaml"),
                    "rt", encoding="utf-8"))
        task_path = os.path.join(self.path, name)

        logger.info("Loading parameters for task %s." % name)

        args = {}

        args["num"] = num
        load(conf, args, "nome_breve", "name")
        load(conf, args, "nome", "title")

        assert name == args["name"]

        if args["name"] == args["title"]:
            logger.warning("Short name equals long name (title). "
                           "Please check.")

        digest = self.file_cacher.put_file(
            path=os.path.join(task_path, "testo", "testo.pdf"),
            description="Statement for task %s (lang: it)" % name)
        args["statements"] = [Statement("it", digest)]

        args["primary_statements"] = '["it"]'

        args["attachments"] = []  # FIXME Use auxiliary

        args["submission_format"] = [
            SubmissionFormatElement("%s.%%l" % name)]

        load(conf, args, "token_initial")
        load(conf, args, "token_max")
        load(conf, args, "token_total")
        load(conf, args, "token_min_interval", conv=make_timedelta)
        load(conf, args, "token_gen_time", conv=make_timedelta)
        load(conf, args, "token_gen_number")

        load(conf, args, "max_submission_number")
        load(conf, args, "max_user_test_number")
        load(conf, args, "min_submission_interval", conv=make_timedelta)
        load(conf, args, "min_user_test_interval", conv=make_timedelta)

        task = Task(**args)

        args = {}
        args["task"] = task
        args["description"] = conf.get("version", "Default")
        args["autojudge"] = False

        load(conf, args, "timeout", "time_limit", conv=float)
        load(conf, args, "memlimit", "memory_limit")

        # Builds the parameters that depend on the task type
        args["managers"] = []
        infile_param = conf.get("infile", "input.txt")
        outfile_param = conf.get("outfile", "output.txt")

        # If there is sol/grader.%l for some language %l, then,
        # presuming that the task type is Batch, we retrieve graders
        # in the form sol/grader.%l
        graders = False
        for lang in LANGUAGES:
            if os.path.exists(os.path.join(
                    task_path, "sol", "grader.%s" % lang)):
                graders = True
                break
        if graders:
            # Read grader for each language
            for lang in LANGUAGES:
                grader_filename = os.path.join(
                    task_path, "sol", "grader.%s" % lang)
                if os.path.exists(grader_filename):
                    digest = self.file_cacher.put_file(
                        path=grader_filename,
                        description="Grader for task %s and language %s" %
                                    (name, lang))
                    args["managers"] += [
                        Manager("grader.%s" % lang, digest)]
                else:
                    logger.error("Grader for language %s not found " % lang)
            # Read managers with other known file extensions
            for other_filename in os.listdir(os.path.join(task_path, "sol")):
                if other_filename.endswith('.h') or \
                        other_filename.endswith('lib.pas'):
                    digest = self.file_cacher.put_file(
                        path=os.path.join(task_path, "sol", other_filename),
                        description="Manager %s for task %s" %
                                    (other_filename, name))
                    args["managers"] += [
                        Manager(other_filename, digest)]
            compilation_param = "grader"
        else:
            compilation_param = "alone"

        # If there is cor/correttore, then, presuming that the task
        # type is Batch or OutputOnly, we retrieve the comparator
        if os.path.exists(os.path.join(task_path, "cor", "correttore")):
            digest = self.file_cacher.put_file(
                path=os.path.join(task_path, "cor", "correttore"),
                description="Manager for task %s" % name)
            args["managers"] += [
                Manager("checker", digest)]
            evaluation_param = "comparator"
        else:
            evaluation_param = "diff"

        # Detect subtasks by checking GEN
        gen_filename = os.path.join(task_path, 'gen', 'GEN')
        try:
            with io.open(gen_filename, "rt", encoding="utf-8") as gen_file:
                subtasks = []
                testcases = 0
                points = None
                for line in gen_file:
                    line = line.strip()
                    splitted = line.split('#', 1)

                    if len(splitted) == 1:
                        # This line represents a testcase, otherwise it's
                        # just a blank
                        if splitted[0] != '':
                            testcases += 1

                    else:
                        testcase, comment = splitted
                        testcase_detected = False
                        subtask_detected = False
                        if testcase.strip() != '':
                            testcase_detected = True
                        comment = comment.strip()
                        if comment.startswith('ST:'):
                            subtask_detected = True

                        if testcase_detected and subtask_detected:
                            raise Exception("No testcase and subtask in the"
                                            " same line allowed")

                        # This line represents a testcase and contains a
                        # comment, but the comment doesn't start a new
                        # subtask
                        if testcase_detected:
                            testcases += 1

                        # This line starts a new subtask
                        if subtask_detected:
                            # Close the previous subtask
                            if points is None:
                                assert(testcases == 0)
                            else:
                                subtasks.append([points, testcases])
                            # Open the new one
                            testcases = 0
                            points = int(comment[3:].strip())

                # Close last subtask (if no subtasks were defined, just
                # fallback to Sum)
                if points is None:
                    args["score_type"] = "Sum"
                    total_value = float(conf.get("total_value", 100.0))
                    input_value = 0.0
                    if int(conf['n_input']) != 0:
                        input_value = total_value / int(conf['n_input'])
                    args["score_type_parameters"] = str(input_value)
                else:
                    subtasks.append([points, testcases])
                    assert(100 == sum([int(st[0]) for st in subtasks]))
                    assert(int(conf['n_input']) ==
                           sum([int(st[1]) for st in subtasks]))
                    args["score_type"] = "GroupMin"
                    args["score_type_parameters"] = str(subtasks)

        # If gen/GEN doesn't exist, just fallback to Sum
        except IOError:
            args["score_type"] = "Sum"
            total_value = float(conf.get("total_value", 100.0))
            input_value = 0.0
            if int(conf['n_input']) != 0:
                input_value = total_value / int(conf['n_input'])
            args["score_type_parameters"] = str(input_value)

        # If output_only is set, then the task type is OutputOnly
        if conf.get('output_only', False):
            args["task_type"] = "OutputOnly"
            args["time_limit"] = None
            args["memory_limit"] = None
            args["task_type_parameters"] = '["%s"]' % evaluation_param
            task.submission_format = [
                SubmissionFormatElement("output_%03d.txt" % i)
                for i in xrange(int(conf["n_input"]))]

        # If there is cor/manager, then the task type is Communication
        elif os.path.exists(os.path.join(task_path, "cor", "manager")):
            args["task_type"] = "Communication"
            args["task_type_parameters"] = '[]'
            digest = self.file_cacher.put_file(
                path=os.path.join(task_path, "cor", "manager"),
                description="Manager for task %s" % name)
            args["managers"] += [
                Manager("manager", digest)]
            for lang in LANGUAGES:
                stub_name = os.path.join(task_path, "sol", "stub.%s" % lang)
                if os.path.exists(stub_name):
                    digest = self.file_cacher.put_file(
                        path=stub_name,
                        description="Stub for task %s and language %s" %
                                    (name, lang))
                    args["managers"] += [
                        Manager("stub.%s" % lang, digest)]
                else:
                    logger.error("Stub for language %s not found." % lang)

        # Otherwise, the task type is Batch
        else:
            args["task_type"] = "Batch"
            args["task_type_parameters"] = \
                '["%s", ["%s", "%s"], "%s"]' % \
                (compilation_param, infile_param, outfile_param,
                 evaluation_param)

        args["testcases"] = []
        for i in xrange(int(conf["n_input"])):
            input_digest = self.file_cacher.put_file(
                path=os.path.join(task_path, "input", "input%d.txt" % i),
                description="Input %d for task %s" % (i, name))
            output_digest = self.file_cacher.put_file(
                path=os.path.join(task_path, "output", "output%d.txt" % i),
                description="Output %d for task %s" % (i, name))
            args["testcases"] += [
                Testcase(i, False, input_digest, output_digest)]
            if args["task_type"] == "OutputOnly":
                task.attachments += [
                    Attachment("input_%03d.txt" % i, input_digest)]
        public_testcases = conf.get("risultati", "").strip()
        if public_testcases != "":
            for x in public_testcases.split(","):
                args["testcases"][int(x.strip())].public = True

        dataset = Dataset(**args)
        task.active_dataset = dataset

        logger.info("Task parameters loaded.")

        return task
