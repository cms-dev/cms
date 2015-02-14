#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from __future__ import unicode_literals
from __future__ import print_function

import io
import logging
import os
import os.path
import sys
import yaml
from datetime import timedelta

from cms import LANGUAGES, LANGUAGE_TO_HEADER_EXT_MAP, \
    SCORE_MODE_MAX, SCORE_MODE_MAX_TOKENED_LAST
from cmscommon.datetime import make_datetime
from cms.db import Contest, User, Task, Statement, Attachment, \
    SubmissionFormatElement, Dataset, Manager, Testcase
from cmscontrib.BaseLoader import Loader
from cmscontrib import touch


logger = logging.getLogger(__name__)


# Patch PyYAML to make it load all strings as unicode instead of str
# (see http://stackoverflow.com/questions/2890146).
def construct_yaml_str(self, node):
    return self.construct_scalar(node)
yaml.Loader.add_constructor("tag:yaml.org,2002:str", construct_yaml_str)
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", construct_yaml_str)


def load(src, dst, src_name, dst_name=None, conv=lambda i: i):
    """Execute:
      dst[dst_name] = conv(src[src_name])
    with the following features:

      * If src_name is a list, it tries each of its element as
        src_name, stopping when the first one succedes.

      * If dst_name is None, it is set to src_name; if src_name is a
        list, dst_name is set to src_name[0] (_not_ the one that
        succedes).

      * By default conv is the identity function.

      * If dst is None, instead of assigning the result to
        dst[dst_name] (which would cast an exception) it just returns
        it.

      * If src[src_name] doesn't exist, the behavior is different
        depending on whether dst is None or not: if dst is None,
        conv(None) is returned; if dst is not None, nothing is done
        (in particular, dst[dst_name] is _not_ assigned to conv(None);
        it is not assigned to anything!).

    """
    if dst is not None and dst_name is None:
        if isinstance(src_name, list):
            dst_name = src_name[0]
        else:
            dst_name = src_name
    res = None
    found = False
    if isinstance(src_name, list):
        for this_src_name in src_name:
            try:
                res = src[this_src_name]
            except KeyError:
                pass
            else:
                found = True
                break
    else:
        if src_name in src:
            found = True
            res = src[src_name]
    if dst is not None:
        if found:
            dst[dst_name] = conv(res)
    else:
        return conv(res)


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

    short_name = 'italy_yaml'
    description = 'Italian YAML-based format'

    @classmethod
    def detect(cls, path):
        """See docstring in class Loader.

        """
        # TODO - Not really refined...
        return os.path.exists(os.path.join(path, "contest.yaml"))

    def get_contest(self):
        """See docstring in class Loader.

        """

        name = os.path.split(self.path)[1]
        conf = yaml.safe_load(
            io.open(os.path.join(self.path, "contest.yaml"),
                    "rt", encoding="utf-8"))

        logger.info("Loading parameters for contest %s.", name)

        args = {}

        load(conf, args, ["name", "nome_breve"])
        load(conf, args, ["description", "nome"])

        assert name == args["name"]

        # Use the new token settings format if detected.
        if "token_mode" in conf:
            load(conf, args, "token_mode")
            load(conf, args, "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_interval", conv=make_timedelta)
            load(conf, args, "token_gen_max")
        # Otherwise fall back on the old one.
        else:
            logger.warning(
                "contest.yaml uses a deprecated format for token settings "
                "which will soon stop being supported, you're advised to "
                "update it.")
            # Determine the mode.
            if conf.get("token_initial", None) is None:
                args["token_mode"] = "disabled"
            elif conf.get("token_gen_number", 0) > 0 and \
                    conf.get("token_gen_time", 0) == 0:
                args["token_mode"] = "infinite"
            else:
                args["token_mode"] = "finite"
            # Set the old default values.
            args["token_gen_initial"] = 0
            args["token_gen_number"] = 0
            args["token_gen_interval"] = timedelta()
            # Copy the parameters to their new names.
            load(conf, args, "token_total", "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_initial", "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_time", "token_gen_interval",
                 conv=make_timedelta)
            load(conf, args, "token_max", "token_gen_max")
            # Remove some corner cases.
            if args["token_gen_initial"] is None:
                args["token_gen_initial"] = 0
            if args["token_gen_interval"].total_seconds() == 0:
                args["token_gen_interval"] = timedelta(minutes=1)

        load(conf, args, ["start", "inizio"], conv=make_datetime)
        load(conf, args, ["stop", "fine"], conv=make_datetime)
        load(conf, args, ["per_user_time"], conv=make_timedelta)

        load(conf, args, "max_submission_number")
        load(conf, args, "max_user_test_number")
        load(conf, args, "min_submission_interval", conv=make_timedelta)
        load(conf, args, "min_user_test_interval", conv=make_timedelta)

        logger.info("Contest parameters loaded.")

        tasks = load(conf, None, ["tasks", "problemi"])
        self.tasks_order = dict((name, num)
                                for num, name in enumerate(tasks))
        self.users_conf = dict((user['username'], user)
                               for user
                               in load(conf, None, ["users", "utenti"]))
        users = self.users_conf.keys()

        return Contest(**args), tasks, users

    def has_changed(self, name):
        """See docstring in class Loader

        """
        path = os.path.realpath(os.path.join(self.path, name))

        try:
            conf = yaml.safe_load(
                io.open(os.path.join(path, "task.yaml"),
                        "rt", encoding="utf-8"))
        except IOError:
            conf = yaml.safe_load(
                io.open(os.path.join(self.path, name + ".yaml"),
                        "rt", encoding="utf-8"))

        # If there is no .itime file, we assume that the task has changed
        if not os.path.exists(os.path.join(path, ".itime")):
            return True

        getmtime = lambda fname: os.stat(fname).st_mtime

        itime = getmtime(os.path.join(path, ".itime"))

        # Generate a task's list of files
        # Testcases
        files = []
        for filename in os.listdir(os.path.join(path, "input")):
            files.append(os.path.join(path, "input", filename))

        for filename in os.listdir(os.path.join(path, "output")):
            files.append(os.path.join(path, "output", filename))

        # Attachments
        if os.path.exists(os.path.join(path, "att")):
            for filename in os.listdir(os.path.join(path, "att")):
                files.append(os.path.join(path, "att", filename))

        # Score file
        files.append(os.path.join(path, "gen", "GEN"))

        # Statement
        files.append(os.path.join(path, "statement", "statement.pdf"))
        files.append(os.path.join(path, "testo", "testo.pdf"))

        # Managers
        files.append(os.path.join(path, "check", "checker"))
        files.append(os.path.join(path, "cor", "correttore"))
        files.append(os.path.join(path, "check", "manager"))
        files.append(os.path.join(path, "cor", "manager"))
        if not conf.get('output_only', False) and \
                os.path.isdir(os.path.join(path, "sol")):
            for lang in LANGUAGES:
                files.append(os.path.join(path, "sol", "grader.%s" % lang))
            for other_filename in os.listdir(os.path.join(path, "sol")):
                if any(other_filename.endswith(header)
                       for header in LANGUAGE_TO_HEADER_EXT_MAP.itervalues()):
                    files.append(os.path.join(path, "sol", other_filename))

        # Yaml
        files.append(os.path.join(path, "task.yaml"))
        files.append(os.path.join(self.path, name + ".yaml"))

        # Check is any of the files have changed
        for fname in files:
            if os.path.exists(fname):
                if getmtime(fname) > itime:
                    return True

        if os.path.exists(os.path.join(path, ".import_error")):
            logger.warning("Last attempt to import task %s failed,"
                           " I'm not trying again.", name)
        return False

    def get_user(self, username):
        """See docstring in class Loader.

        """
        logger.info("Loading parameters for user %s.", username)
        conf = self.users_conf[username]
        assert username == conf['username']

        args = {}

        load(conf, args, "username")

        load(conf, args, "password")
        load(conf, args, "ip")

        load(conf, args, ["first_name", "nome"])
        load(conf, args, ["last_name", "cognome"])

        if "first_name" not in args:
            args["first_name"] = ""
        if "last_name" not in args:
            args["last_name"] = args["username"]

        load(conf, args, ["hidden", "fake"],
             conv=lambda a: a is True or a == "True")

        logger.info("User parameters loaded.")

        return User(**args)

    def get_task(self, name):
        """See docstring in class Loader.

        """
        try:
            num = self.tasks_order[name]

        # Here we expose an undocumented behavior, so that cmsMake can
        # import a task even without the whole contest; this is not to
        # be relied upon in general
        except AttributeError:
            num = 1

        task_path = os.path.join(self.path, name)

        # We first look for the yaml file inside the task folder,
        # and eventually fallback to a yaml file in its parent folder.
        try:
            conf = yaml.safe_load(
                io.open(os.path.join(task_path, "task.yaml"),
                        "rt", encoding="utf-8"))
        except IOError:
            conf = yaml.safe_load(
                io.open(os.path.join(self.path, name + ".yaml"),
                        "rt", encoding="utf-8"))

        logger.info("Loading parameters for task %s.", name)

        # Here we update the time of the last import
        touch(os.path.join(task_path, ".itime"))
        # If this file is not deleted, then the import failed
        touch(os.path.join(task_path, ".import_error"))

        args = {}

        args["num"] = num
        load(conf, args, ["name", "nome_breve"])
        load(conf, args, ["title", "nome"])

        assert name == args["name"]

        if args["name"] == args["title"]:
            logger.warning("Short name equals long name (title). "
                           "Please check.")

        primary_language = load(conf, None, "primary_language")
        if primary_language is None:
            primary_language = 'it'
        paths = [os.path.join(task_path, "statement", "statement.pdf"),
                 os.path.join(task_path, "testo", "testo.pdf")]
        for path in paths:
            if os.path.exists(path):
                digest = self.file_cacher.put_file_from_path(
                    path,
                    "Statement for task %s (lang: %s)" % (name,
                                                          primary_language))
                break
        else:
            logger.critical("Couldn't find any task statement, aborting...")
            sys.exit(1)
        args["statements"] = [Statement(primary_language, digest)]

        args["primary_statements"] = '["%s"]' % (primary_language)

        args["attachments"] = []  # FIXME Use auxiliary

        args["submission_format"] = [
            SubmissionFormatElement("%s.%%l" % name)]

        if conf.get("score_mode", None) == SCORE_MODE_MAX:
            args["score_mode"] = SCORE_MODE_MAX
        elif conf.get("score_mode", None) == SCORE_MODE_MAX_TOKENED_LAST:
            args["score_mode"] = SCORE_MODE_MAX_TOKENED_LAST

        # Use the new token settings format if detected.
        if "token_mode" in conf:
            load(conf, args, "token_mode")
            load(conf, args, "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_interval", conv=make_timedelta)
            load(conf, args, "token_gen_max")
        # Otherwise fall back on the old one.
        else:
            logger.warning(
                "%s.yaml uses a deprecated format for token settings which "
                "will soon stop being supported, you're advised to update it.",
                name)
            # Determine the mode.
            if conf.get("token_initial", None) is None:
                args["token_mode"] = "disabled"
            elif conf.get("token_gen_number", 0) > 0 and \
                    conf.get("token_gen_time", 0) == 0:
                args["token_mode"] = "infinite"
            else:
                args["token_mode"] = "finite"
            # Set the old default values.
            args["token_gen_initial"] = 0
            args["token_gen_number"] = 0
            args["token_gen_interval"] = timedelta()
            # Copy the parameters to their new names.
            load(conf, args, "token_total", "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_initial", "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_time", "token_gen_interval",
                 conv=make_timedelta)
            load(conf, args, "token_max", "token_gen_max")
            # Remove some corner cases.
            if args["token_gen_initial"] is None:
                args["token_gen_initial"] = 0
            if args["token_gen_interval"].total_seconds() == 0:
                args["token_gen_interval"] = timedelta(minutes=1)

        load(conf, args, "max_submission_number")
        load(conf, args, "max_user_test_number")
        load(conf, args, "min_submission_interval", conv=make_timedelta)
        load(conf, args, "min_user_test_interval", conv=make_timedelta)

        # Attachments
        args["attachments"] = []
        if os.path.exists(os.path.join(task_path, "att")):
            for filename in os.listdir(os.path.join(task_path, "att")):
                digest = self.file_cacher.put_file_from_path(
                    os.path.join(task_path, "att", filename),
                    "Attachment %s for task %s" % (filename, name))
                args["attachments"] += [Attachment(filename, digest)]

        task = Task(**args)

        args = {}
        args["task"] = task
        args["description"] = conf.get("version", "Default")
        args["autojudge"] = False

        load(conf, args, ["time_limit", "timeout"], conv=float)
        load(conf, args, ["memory_limit", "memlimit"])

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
                    digest = self.file_cacher.put_file_from_path(
                        grader_filename,
                        "Grader for task %s and language %s" % (name, lang))
                    args["managers"] += [
                        Manager("grader.%s" % lang, digest)]
                else:
                    logger.warning("Grader for language %s not found ", lang)
            # Read managers with other known file extensions
            for other_filename in os.listdir(os.path.join(task_path, "sol")):
                if any(other_filename.endswith(header)
                       for header in LANGUAGE_TO_HEADER_EXT_MAP.itervalues()):
                    digest = self.file_cacher.put_file_from_path(
                        os.path.join(task_path, "sol", other_filename),
                        "Manager %s for task %s" % (other_filename, name))
                    args["managers"] += [
                        Manager(other_filename, digest)]
            compilation_param = "grader"
        else:
            compilation_param = "alone"

        # If there is check/checker (or equivalent), then, presuming
        # that the task type is Batch or OutputOnly, we retrieve the
        # comparator
        paths = [os.path.join(task_path, "check", "checker"),
                 os.path.join(task_path, "cor", "correttore")]
        for path in paths:
            if os.path.exists(path):
                digest = self.file_cacher.put_file_from_path(
                    path,
                    "Manager for task %s" % name)
                args["managers"] += [
                    Manager("checker", digest)]
                evaluation_param = "comparator"
                break
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
                        # This line represents a testcase, otherwise
                        # it's just a blank
                        if splitted[0] != '':
                            testcases += 1

                    else:
                        testcase, comment = splitted
                        testcase = testcase.strip()
                        comment = comment.strip()
                        testcase_detected = testcase != ''
                        copy_testcase_detected = comment.startswith("COPY:")
                        subtask_detected = comment.startswith('ST:')

                        flags = [testcase_detected,
                                 copy_testcase_detected,
                                 subtask_detected]
                        if len([x for x in flags if x]) > 1:
                            raise Exception("No testcase and command in"
                                            " the same line allowed")

                        # This line represents a testcase and contains a
                        # comment, but the comment doesn't start a new
                        # subtask
                        if testcase_detected or copy_testcase_detected:
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
                    n_input = testcases
                    if n_input != 0:
                        input_value = total_value / n_input
                    args["score_type_parameters"] = "%s" % input_value
                else:
                    subtasks.append([points, testcases])
                    assert(100 == sum([int(st[0]) for st in subtasks]))
                    n_input = sum([int(st[1]) for st in subtasks])
                    args["score_type"] = "GroupMin"
                    args["score_type_parameters"] = "%s" % subtasks

                if "n_input" in conf:
                    assert int(conf['n_input']) == n_input

        # If gen/GEN doesn't exist, just fallback to Sum
        except IOError:
            args["score_type"] = "Sum"
            total_value = float(conf.get("total_value", 100.0))
            input_value = 0.0
            n_input = int(conf['n_input'])
            if n_input != 0:
                input_value = total_value / n_input
            args["score_type_parameters"] = "%s" % input_value

        # If output_only is set, then the task type is OutputOnly
        if conf.get('output_only', False):
            args["task_type"] = "OutputOnly"
            args["time_limit"] = None
            args["memory_limit"] = None
            args["task_type_parameters"] = '["%s"]' % evaluation_param
            task.submission_format = [
                SubmissionFormatElement("output_%03d.txt" % i)
                for i in xrange(n_input)]

        # If there is check/manager (or equivalent), then the task
        # type is Communication
        else:
            paths = [os.path.join(task_path, "check", "manager"),
                     os.path.join(task_path, "cor", "manager")]
            for path in paths:
                if os.path.exists(path):
                    args["task_type"] = "Communication"
                    args["task_type_parameters"] = '[]'
                    digest = self.file_cacher.put_file_from_path(
                        path,
                        "Manager for task %s" % name)
                    args["managers"] += [
                        Manager("manager", digest)]
                    for lang in LANGUAGES:
                        stub_name = os.path.join(
                            task_path, "sol", "stub.%s" % lang)
                        if os.path.exists(stub_name):
                            digest = self.file_cacher.put_file_from_path(
                                stub_name,
                                "Stub for task %s and language %s" % (name,
                                                                      lang))
                            args["managers"] += [
                                Manager("stub.%s" % lang, digest)]
                        else:
                            logger.warning("Stub for language %s not "
                                           "found.", lang)
                    for other_filename in os.listdir(os.path.join(task_path,
                                                                  "sol")):
                        if any(other_filename.endswith(header) for header in
                               LANGUAGE_TO_HEADER_EXT_MAP.itervalues()):
                            digest = self.file_cacher.put_file_from_path(
                                os.path.join(task_path, "sol", other_filename),
                                "Stub %s for task %s" % (other_filename, name))
                            args["managers"] += [
                                Manager(other_filename, digest)]
                    break

            # Otherwise, the task type is Batch
            else:
                args["task_type"] = "Batch"
                args["task_type_parameters"] = \
                    '["%s", ["%s", "%s"], "%s"]' % \
                    (compilation_param, infile_param, outfile_param,
                     evaluation_param)

        args["testcases"] = []
        for i in xrange(n_input):
            input_digest = self.file_cacher.put_file_from_path(
                os.path.join(task_path, "input", "input%d.txt" % i),
                "Input %d for task %s" % (i, name))
            output_digest = self.file_cacher.put_file_from_path(
                os.path.join(task_path, "output", "output%d.txt" % i),
                "Output %d for task %s" % (i, name))
            args["testcases"] += [
                Testcase("%03d" % i, False, input_digest, output_digest)]
            if args["task_type"] == "OutputOnly":
                task.attachments += [
                    Attachment("input_%03d.txt" % i, input_digest)]
        public_testcases = load(conf, None, ["public_testcases", "risultati"],
                                conv=lambda x: "" if x is None else x)
        if public_testcases != "":
            for x in public_testcases.split(","):
                args["testcases"][int(x.strip())].public = True

        dataset = Dataset(**args)
        task.active_dataset = dataset

        # Import was successful
        os.remove(os.path.join(task_path, ".import_error"))

        logger.info("Task parameters loaded.")

        return task
