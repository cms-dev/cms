#!/usr/bin/python
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

from cms import logger
from cms.db import analyze_all_tables
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import metadata, SessionGen, Manager, \
    Testcase, User, Contest, SubmissionFormatElement, FSObject, \
    Submission
from cms.grading.ScoreType import ScoreTypes


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
        conf = yaml.load(codecs.open(\
                os.path.join(path, "contest.yaml"),
                "r", "utf-8"))

        logger.info("Loading parameters for contest %s." % name)

        params = {}
        params["name"] = name
        assert name == conf["nome_breve"]
        params["description"] = conf["nome"]
        params["token_initial"] = conf.get("token_initial", 10000)
        params["token_max"] = conf.get("token_max", None)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", None)
        params["token_gen_time"] = conf.get("token_gen_time", None)
        params["token_gen_number"] = conf.get("token_gen_number", None)
        if self.modif == 'zero_time':
            params["start"] = 0
            params["stop"] = 0
        elif self.modif == 'test':
            params["start"] = 0
            params["stop"] = 2000000000
        else:
            params["start"] = conf.get("inizio", 0)
            params["stop"] = conf.get("fine", 0)

        logger.info("Contest parameters loaded.")

        params["tasks"] = []
        params["users"] = []
        params["announcements"] = []
        params["ranking_view"] = None

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
            params["ip"] = '0.0.0.0'
        else:
            params["password"] = user_dict["password"]
            params["ip"] = user_dict.get("ip", "0.0.0.0")
        name = user_dict.get("nome", "")
        surname = user_dict.get("cognome", user_dict["username"])
        params["first_name"] = name
        params["last_name"] = surname
        params["hidden"] = "True" == user_dict.get("fake", "False")

        params["timezone"] = 0.0
        params["messages"] = []
        params["questions"] = []
        params["submissions"] = []

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
                           "Is this intended?")
        params["num"] = num
        params["time_limit"] = conf["timeout"]
        params["memory_limit"] = conf["memlimit"]
        params["attachments"] = {}  # FIXME - Use auxiliary
        params["statement"] = self.file_cacher.put_file(
            path=os.path.join(path, "testo", "testo.pdf"),
            description="PDF statement for task %s" % name)
        params["task_type"] = "Batch"

        params["submission_format"] = [
            SubmissionFormatElement("%s.%%l" % name).export_to_dict()]

        if os.path.exists(os.path.join(path, "cor", "correttore")):
            params["managers"] = [
                Manager(self.file_cacher.put_file(
                    path=os.path.join(path, "cor", "correttore"),
                    description="Manager for task %s" % (name)),
                        "checker").export_to_dict()]
            params["task_type_parameters"] = '["alone", "file", "comparator"]'
        elif os.path.exists(os.path.join(path, "cor", "manager")):
            params["task_type"] = "Communication"
            params["task_type_parameters"] = '[]'
            params["managers"] = [
                Manager(self.file_cacher.put_file(
                    path=os.path.join(path, "cor", "manager"),
                    description="Manager for task %s" % (name)),
                        "manager").export_to_dict()]
            for lang in Submission.LANGUAGES:
                stub_name = os.path.join(path, "sol", "stub.%s" % lang)
                if os.path.exists(stub_name):
                    params["managers"].append(
                        Manager(self.file_cacher.put_file(
                            path=stub_name,
                            description="Stub for task %s and language %s" % \
                            (name, lang)),
                                "stub.%s" % lang).export_to_dict())
        else:
            params["managers"] = {}
            params["task_type_parameters"] = '["alone", "file", "diff"]'
        params["score_type"] = conf.get("score_type",
                                        ScoreTypes.SCORE_TYPE_SUM)
        params["score_parameters"] = conf.get(
            "score_parameters", str(100.0 / float(conf["n_input"])))
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
            params["testcases"].append(Testcase(
                self.file_cacher.put_file(
                    path=_input,
                    description="Input %d for task %s" % (i, name)),
                self.file_cacher.put_file(
                    path=output,
                    description="Output %d for task %s" % (i, name)),
                public=(i in public_testcases)).export_to_dict())
        params["token_initial"] = conf.get("token_initial", 2)
        params["token_max"] = conf.get("token_max", 10)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", None)
        params["token_gen_time"] = conf.get("token_gen_time", 30)
        params["token_gen_number"] = conf.get("token_gen_number", 2)

        logger.info("Task parameters loaded.")

        params["attachments"] = []

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
                params["users"].append(User("User %d" % (i),
                                            "user%03d" % (i)).export_to_dict())
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
            with SessionGen() as session:
                FSObject.delete_all(session)
                session.commit()
            metadata.drop_all()
        metadata.create_all()

        contest = Contest.import_from_dict(
            self.loader.import_contest(self.path))

        logger.info("Creating contest on the database.")
        with SessionGen() as session:
            session.add(contest)
            contest.create_empty_ranking_view()
            session.flush()

            contest_id = contest.id

            logger.info("Analyzing database.")
            analyze_all_tables(session)
            session.commit()

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
                       "(times: 0, 2*10^9; ips: 0.0.0.0, passwords: a)")
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
