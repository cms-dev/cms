#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""This service load a contest from a tree structure "similar" to the
one used in Italian IOI repository.

"""

import yaml
import os
import codecs
import argparse

import sqlalchemy.exc

from cms import logger
from cms.db import analyze_all_tables
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import metadata, SessionGen, Manager, \
    Testcase, User, Contest, SubmissionFormatElement, FSObject, \
    Submission, Statement, Attachment


class YamlLoader:
    """Actually look into the directory of the contest, and load all
    data and files.

    """
    def __init__(self, file_cacher, drop, modif, user_number):
        self.drop = drop
        self.modif = modif
        self.user_number = user_number
        self.file_cacher = file_cacher

    def get_params_for_contest(self, path):
        """Given the path of a contest, extract the data from its
        contest.yaml file, and create a dictionary with the parameter
        required by Contest.import_from_dict().

        Returns that dictionary and the two pieces of data that must
        be processed with get_params_for_task and
        get_params_for_users.

        path (string): the input directory.

        return (dict): data of the contest.

        """
        path = os.path.realpath(path)
        name = os.path.split(path)[1]
        conf = yaml.load(codecs.open(
                os.path.join(path, "contest.yaml"),
                "r", "utf-8"))

        logger.info("Loading parameters for contest %s." % name)

        params = {}
        params["name"] = name
        assert name == conf["nome_breve"]
        params["description"] = conf["nome"]
        params["token_initial"] = conf.get("token_initial", None)
        params["token_max"] = conf.get("token_max", None)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", 0)
        params["token_gen_time"] = conf.get("token_gen_time", 0)
        params["token_gen_number"] = conf.get("token_gen_number", 0)
        if params["token_gen_time"] is None or \
               params["token_gen_number"] is None:
            params["token_gen_time"] = 1
            params["token_gen_number"] = 0
        if self.modif == 'zero_time':
            params["start"] = 0
            params["stop"] = 0
        elif self.modif == 'test':
            params["start"] = 0
            params["stop"] = 2000000000
        else:
            params["start"] = conf.get("inizio", 0)
            params["stop"] = conf.get("fine", 0)

        params["max_submission_number"] = \
            conf.get("max_submission_number", None)
        params["max_user_test_number"] = \
            conf.get("max_user_test_number", None)
        params["min_submission_interval"] = \
            conf.get("min_submission_interval", None)
        params["min_user_test_interval"] = \
            conf.get("min_user_test_interval", None)

        logger.info("Contest parameters loaded.")

        params["tasks"] = []
        params["users"] = []
        params["announcements"] = []

        return params, conf["problemi"], conf["utenti"]

    def get_params_for_user(self, user_dict):
        """Given the dictionary of information of a user (extracted
        from contest.yaml), it fills another dictionary with the
        parameters required by User.import_from_dict().

        """
        params = {}
        params["username"] = user_dict["username"]

        logger.info("Loading parameters for user %s." % params['username'])

        if self.modif == 'test':
            params["password"] = 'a'
            params["ip"] = None
        else:
            params["password"] = user_dict["password"]
            params["ip"] = user_dict.get("ip", None)
        name = user_dict.get("nome", "")
        surname = user_dict.get("cognome", user_dict["username"])
        params["first_name"] = name
        params["last_name"] = surname
        params["hidden"] = "True" == user_dict.get("fake", "False")

        params["timezone"] = None
        params["messages"] = []
        params["questions"] = []
        params["submissions"] = []
        params["user_tests"] = []

        logger.info("User parameters loaded.")

        return params

    def get_params_for_task(self, path, num):
        """Given the path of a task, this function put all needed data
        into FS, and fills the dictionary of parameters required by
        Task.import_from_dict().

        path (string): path of the task.
        num (int): number of the task in the contest task ordering.

        return (dict): info of the task.

        """
        path = os.path.realpath(path)
        super_path, name = os.path.split(path)
        conf = yaml.load(codecs.open(
            os.path.join(super_path, name + ".yaml"), "r", "utf-8"))

        logger.info("Loading parameters for task %s." % name)

        params = {"name": name}
        assert name == conf["nome_breve"]
        params["title"] = conf["nome"]
        if name == params["title"]:
            logger.warning("Short name equals long name (title). "
                           "Please check.")
        params["num"] = num
        params["time_limit"] = conf.get("timeout", None)
        params["time_limit"] = float(params["time_limit"]) \
                if params["time_limit"] is not None else None
        params["memory_limit"] = conf.get("memlimit", None)
        params["attachments"] = []  # FIXME - Use auxiliary
        params["statements"] = [Statement(
                "",
                self.file_cacher.put_file(
                    path=os.path.join(path, "testo", "testo.pdf"),
                    description="Statement for task %s (lang: )" % name),
                ).export_to_dict()]

        params["submission_format"] = [
            SubmissionFormatElement("%s.%%l" % name).export_to_dict()]

        params["primary_statements"] = "[\"\"]"

        # Builds the parameters that depend on the task type
        params["managers"] = []
        infile_param = conf.get("infile", "input.txt")
        outfile_param = conf.get("outfile", "output.txt")

        # If there is sol/grader.%l for some language %l, then,
        # presuming that the task type is Batch, we retrieve graders
        # in the form sol/grader.%l
        graders = False
        for lang in Submission.LANGUAGES:
            if os.path.exists(os.path.join(path, "sol", "grader.%s" % (lang))):
                graders = True
                break
        if graders:
            # Read grader for each language
            for lang in Submission.LANGUAGES:
                grader_filename = os.path.join(path, "sol", "grader.%s" %
                                               (lang))
                if os.path.exists(grader_filename):
                    params["managers"].append(Manager(
                        "grader.%s" % (lang),
                        self.file_cacher.put_file(
                            path=grader_filename,
                            description="Grader for task %s and "
                            "language %s" % (name, lang)),
                        ).export_to_dict())
                else:
                    logger.error("Grader for language %s not found " % lang)
            # Read managers with other known file extensions
            for other_filename in os.listdir(os.path.join(path, "sol")):
                if other_filename.endswith('.h') or \
                        other_filename.endswith('lib.pas'):
                    params["managers"].append(Manager(
                        other_filename,
                        self.file_cacher.put_file(
                            path=os.path.join(path, "sol",
                                              other_filename),
                            description="Manager %s for task %s" %
                            (other_filename, name)),
                        ).export_to_dict())
            compilation_param = "grader"
        else:
            compilation_param = "alone"

        # If there is cor/correttore, then, presuming that the task
        # type is Batch or OutputOnly, we retrieve the comparator
        if os.path.exists(os.path.join(path, "cor", "correttore")):
            params["managers"].append(Manager(
                "checker",
                self.file_cacher.put_file(
                    path=os.path.join(path, "cor", "correttore"),
                    description="Manager for task %s" % (name)),
                ).export_to_dict())
            evaluation_parameter = "comparator"
        else:
            evaluation_parameter = "diff"

        # Detect subtasks by checking GEN
        gen_filename = os.path.join(path, 'gen', 'GEN')
        try:
            with open(gen_filename) as gen_file:
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
                    params["score_type"] = "Sum"
                    total_value = float(conf.get("total_value", 100.0))
                    input_value = 0.0
                    if int(conf['n_input']) != 0:
                        input_value = total_value / int(conf['n_input'])
                    params["score_type_parameters"] = str(input_value)
                else:
                    subtasks.append([points, testcases])
                    assert(100 == sum([int(st[0]) for st in subtasks]))
                    assert(int(conf['n_input']) ==
                           sum([int(st[1]) for st in subtasks]))
                    params["score_type"] = "GroupMin"
                    params["score_type_parameters"] = str(subtasks)

        # If gen/GEN doesn't exist, just fallback to Sum
        except IOError:
            params["score_type"] = "Sum"
            total_value = float(conf.get("total_value", 100.0))
            input_value = 0.0
            if int(conf['n_input']) != 0:
                input_value = total_value / int(conf['n_input'])
            params["score_type_parameters"] = str(input_value)

        # If output_only is set, then the task type is OutputOnly
        if conf.get('output_only', False):
            params["task_type"] = "OutputOnly"
            params["time_limit"] = None
            params["memory_limit"] = None
            params["task_type_parameters"] = '["%s"]' % (evaluation_parameter)
            params["submission_format"] = [
                SubmissionFormatElement("output_%03d.txt" % i).export_to_dict()
                for i in xrange(int(conf["n_input"]))]

        # If there is cor/manager, then the task type is Communication
        elif os.path.exists(os.path.join(path, "cor", "manager")):
            params["task_type"] = "Communication"
            params["task_type_parameters"] = '[]'
            params["managers"].append(Manager(
                "manager",
                self.file_cacher.put_file(
                    path=os.path.join(path, "cor", "manager"),
                    description="Manager for task %s" % (name)),
                ).export_to_dict())
            for lang in Submission.LANGUAGES:
                stub_name = os.path.join(path, "sol", "stub.%s" % lang)
                if os.path.exists(stub_name):
                    params["managers"].append(Manager(
                        "stub.%s" % lang,
                        self.file_cacher.put_file(
                            path=stub_name,
                            description="Stub for task %s and language %s" %
                            (name, lang)),
                        ).export_to_dict())
                else:
                    logger.error("Stub for language %s not found." % lang)
            for header_filename in os.listdir(os.path.join(path, "sol")):
                if header_filename.endswith(".h") or \
                        header_filename.endswith(".lib.pas"):
                    header_name = os.path.join(path, "sol", header_filename)
                    if os.path.exists(header_name):
                        params["managers"].append(Manager(
                            header_filename,
                            self.file_cacher.put_file(
                                path=header_name,
                                description="Header for task %s" % name),
                            ).export_to_dict())

        # Otherwise, the task type is Batch
        else:
            params["task_type"] = "Batch"
            params["task_type_parameters"] = \
                '["%s", ["%s", "%s"], "%s"]' % \
                (compilation_param, infile_param, outfile_param,
                 evaluation_parameter)

        public_testcases = conf.get("risultati", "").strip()
        if public_testcases != "":
            public_testcases = [int(x.strip())
                                for x in public_testcases.split(",")]
        else:
            public_testcases = []
        params["testcases"] = []
        for i in xrange(int(conf["n_input"])):
            _input = os.path.join(path, "input", "input%d.txt" % i)
            output = os.path.join(path, "output", "output%d.txt" % i)
            input_digest = self.file_cacher.put_file(
                path=_input,
                description="Input %d for task %s" % (i, name))
            output_digest = self.file_cacher.put_file(
                path=output,
                description="Output %d for task %s" % (i, name))
            params["testcases"].append(Testcase(
                num=i,
                public=(i in public_testcases),
                input=input_digest,
                output=output_digest).export_to_dict())
            if params["task_type"] == "OutputOnly":
                params["attachments"].append(Attachment(
                        "input_%03d.txt" % (i),
                        input_digest).export_to_dict())
        params["token_initial"] = conf.get("token_initial", None)
        params["token_max"] = conf.get("token_max", None)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", 0)
        params["token_gen_time"] = conf.get("token_gen_time", 0)
        params["token_gen_number"] = conf.get("token_gen_number", 0)

        params["max_submission_number"] = \
            conf.get("max_submission_number", None)
        params["max_user_test_number"] = \
            conf.get("max_user_test_number", None)
        params["min_submission_interval"] = \
            conf.get("min_submission_interval", None)
        params["min_user_test_interval"] = \
            conf.get("min_user_test_interval", None)

        logger.info("Task parameters loaded.")

        return params

    def import_contest(self, path):
        """Import a contest into the system, returning a dictionary
        that can be passed to Contest.import_from_dict().

        """
        params, tasks, users = self.get_params_for_contest(path)
        for i, task in enumerate(tasks):
            task_params = self.get_params_for_task(os.path.join(path, task),
                                                   num=i)
            params["tasks"].append(task_params)
        if self.user_number is None:
            for user in users:
                user_params = self.get_params_for_user(user)
                params["users"].append(user_params)
        else:
            logger.info("Generating %s random users." % self.user_number)
            for i in xrange(self.user_number):
                user = User("User %d" % (i),
                            "Last name %d" % (i),
                            "user%03d" % (i))
                if self.modif == 'test':
                    user.password = 'a'
                params["users"].append(user.export_to_dict())

        return params


class YamlImporter:
    """This service load a contest from a tree structure "similar" to
    the one used in Italian IOI repository.

    """
    def __init__(self, drop, modif, path, user_number):
        self.drop = drop
        self.modif = modif
        self.path = path
        self.user_number = user_number

        self.file_cacher = FileCacher()

        self.loader = YamlLoader(self.file_cacher, drop, modif, user_number)

    def run(self):
        """Interface to make the class do its job."""
        self.do_import()

    def do_import(self):
        """Take care of creating the database structure, delegating
        the loading of the contest data and putting them on the
        database.

        """
        logger.info("Creating database structure.")
        if self.drop:
            try:
                with SessionGen() as session:
                    FSObject.delete_all(session)
                    session.commit()
                metadata.drop_all()
            except sqlalchemy.exc.OperationalError as error:
                logger.critical("Unable to access DB.\n%r" % error)
                return False
        try:
            metadata.create_all()
        except sqlalchemy.exc.OperationalError as error:
            logger.critical("Unable to access DB.\n%r" % error)
            return False

        contest = Contest.import_from_dict(
            self.loader.import_contest(self.path))

        logger.info("Creating contest on the database.")
        with SessionGen() as session:
            session.add(contest)
            logger.info("Analyzing database.")
            session.commit()
            contest_id = contest.id
            analyze_all_tables(session)

        logger.info("Import finished (new contest id: %s)." % contest_id)

        return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Importer from the Italian repository for CMS.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-z", "--zero-time", action="store_true",
                       help="set to zero contest start and stop time")
    group.add_argument("-t", "--test", action="store_true",
                       help="setup a contest for testing "
                       "(times: 0, 2*10^9; ips: unset, passwords: a)")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop everything from the database "
                        "before importing")
    parser.add_argument("-n", "--user-number", action="store", type=int,
                        help="put N random users instead of importing them")
    parser.add_argument("import_directory",
                        help="source directory from where import")

    args = parser.parse_args()

    modif = None
    if args.test:
        modif = 'test'
    elif args.zero_time:
        modif = 'zero_time'

    YamlImporter(drop=args.drop,
                 modif=modif,
                 path=args.import_directory,
                 user_number=args.user_number).run()


if __name__ == "__main__":
    main()
