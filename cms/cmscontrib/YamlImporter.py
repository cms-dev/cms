#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import yaml
import os
import sys
import codecs
import optparse

from cms.async import ServiceCoord
from cms.db.SQLAlchemyAll import metadata, SessionGen, Task, Manager, \
    Testcase, User, Contest, SubmissionFormatElement
from cms.service.FileStorage import FileCacher
from cms.service.ScoreType import ScoreTypes
from cms.async.AsyncLibrary import rpc_callback, Service, logger
from cms.db.Utils import analyze_all_tables


class YamlLoader:

    def __init__(self, FC, drop, modif, user_num):
        self.drop = drop
        self.modif = modif
        self.user_num = user_num
        self.FC = FC

    def get_params_for_contest(self, path):
        """Given the path of a contest, extract the data from its
        contest.yaml file, and create a dictionary with the parameter
        required by Contest.import_from_dict().

        Returns that dictionary and the two pieces of data that must
        be processed with get_params_for_task and
        get_params_for_users.

        """
        path = os.path.realpath(path)
        name = os.path.split(path)[1]
        conf = yaml.load(codecs.open(\
                os.path.join(path, "contest.yaml"),
                "r", "utf-8"))

        logger.info("Loading parameters for contest %s." % (name))

        params = {}
        params["name"] = name
        assert name == conf["nome_breve"]
        params["description"] = conf["nome"]
        params["token_initial"] = conf.get("token_initial", 0)
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

        logger.info("Loading parameters for user %s." % (params['username']))

        if self.modif == 'test':
            params["password"] = 'a'
            params["ip"] = '0.0.0.0'
        else:
            params["password"] = user_dict["password"]
            params["ip"] = user_dict.get("ip", "0.0.0.0")
        name = user_dict.get("nome", "")
        surname = user_dict.get("cognome", user_dict["username"])
        params["real_name"] = " ".join([name, surname])
        params["hidden"] = "True" == user_dict.get("fake", "False")

        params["timezone"] = 0.0
        params["messages"] = []
        params["questions"] = []
        params["submissions"] = []

        logger.info("User parameters loaded.")

        return params

    def get_params_for_task(self, path):
        """Given the path of a task, this function put all needed data
        into FS, and fills the dictionary of parameters required by
        Task.import_from_dict().

        """
        path = os.path.realpath(path)
        super_path, name = os.path.split(path)
        conf = yaml.load(codecs.open(
            os.path.join(super_path, name + ".yaml"), "r", "utf-8"))

        logger.info("Loading parameters for task %s." % (name))

        params = {"name": name}
        assert name == conf["nome_breve"]
        params["title"] = conf["nome"]
        params["time_limit"] = conf["timeout"]
        params["memory_limit"] = conf["memlimit"]
        params["attachments"] = {} # FIXME - Use auxiliary
        params["statement"] = self.FC.put_file(
            path=os.path.join(path, "testo", "testo.pdf"),
            description="PDF statement for task %s" % name)
        params["task_type"] = Task.TASK_TYPE_BATCH

        params["submission_format"] = [SubmissionFormatElement("%s.%%l" %
                                                               (name)).export_to_dict()]

        if os.path.exists(os.path.join(path, "cor", "correttore")):
            params["managers"] = [Manager(self.FC.put_file(
                        path=os.path.join(path, "cor", "correttore"),
                        description="Manager for task %s" % (name)),
                                          "checker").export_to_dict()]
            params["task_type_parameters"] = "[\"comp\", \"file\"]"
        else:
            params["managers"] = {}
            params["task_type_parameters"] = "[\"diff\", \"file\"]"
        params["score_type"] = conf.get("score_type",
                                        ScoreTypes.SCORE_TYPE_SUM)
        params["score_parameters"] = conf.get("score_parameters", "5.0")
        public_testcases = conf.get("risultati", "").strip()
        if public_testcases != "":
            public_testcases = [int(x.strip())
                                for x in public_testcases.split(",")]
        else:
            public_testcases = []
        params["testcases"] = []
        for i in xrange(int(conf["n_input"])):
            fi = os.path.join(path, "input", "input%d.txt" % i)
            fo = os.path.join(path, "output", "output%d.txt" % i)
            params["testcases"].append(Testcase(
                self.FC.put_file(
                    path=fi, description="Input %d for task %s" % (i, name)),
                self.FC.put_file(
                    path=fo, description="Output %d for task %s" % (i, name)),
                public=(i in public_testcases)).export_to_dict())
        params["token_initial"] = conf.get("token_initial", 0)
        params["token_max"] = conf.get("token_max", None)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", None)
        params["token_gen_time"] = conf.get("token_gen_time", None)
        params["token_gen_number"] = conf.get("token_gen_number", None)

        logger.info("Task parameters loaded.")

        params["attachments"] = []

        return params

    def import_contest(self, path):
        """Import a contest into the system, returning a dictionary
        that can be passed to Contest.import_from_dict().

        """
        params, tasks, users = self.get_params_for_contest(path)
        for task in tasks:
            task_params = self.get_params_for_task(os.path.join(path, task))
            params["tasks"].append(task_params)
        if self.user_num is None:
            for user in users:
                user_params = self.get_params_for_user(user)
                params["users"].append(user_params)
        else:
            logger.info("Generating %d random users." % (self.user_num))
            for i in xrange(self.user_num):
                params["users"].append(User("User %d" % (i), "user%03d" % (i)).export_to_dict())
        return params


class YamlImporter(Service):

    def __init__(self, shard, drop, modif, path, user_num):
        self.drop = drop
        self.modif = modif
        self.path = path
        self.user_num = user_num

        logger.initialize(ServiceCoord("YamlImporter", shard))
        logger.debug("YamlImporter.__init__")
        Service.__init__(self, shard)
        self.FS = self.connect_to(ServiceCoord("FileStorage", 0))
        self.FC = FileCacher(self, self.FS)

        self.loader = YamlLoader(self.FC, drop, modif, user_num)

        self.add_timeout(self.do_import, None, 10, immediately=True)

    def do_import(self):
        if not self.FS.connected:
            logger.warning("Please run FileStorage.")
            return True

        logger.info("Creating database structure.")
        if self.drop:
            metadata.drop_all()
        metadata.create_all()

        c = Contest.import_from_dict(self.loader.import_contest(self.path))

        logger.info("Creating contest on the database.")
        with SessionGen() as session:
            session.add(c)
            c.create_empty_ranking_view()
            session.flush()

            contest_id = c.id

            logger.info("Analyzing database.")
            analyze_all_tables(session)
            session.commit()

        logger.info("Import finished (new contest ID: %d)." % (contest_id))

        self.exit()
        return False


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-z", "--zero-time",
                      dest="zero_time",
                      help="set to zero contest start and stop time",
                      default=False, action="store_true")
    parser.add_option("-t", "--test",
                      dest="test",
                      help="setup a contest for testing "
                      "(times: 0, 2*10^9; ips: 0.0.0.0, passwords: a)",
                      default=False, action="store_true")
    parser.add_option("-d", "--drop",
                      dest="drop", help="drop everything from the database "
                      "before importing",
                      default=False, action="store_true")
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    parser.add_option("-n", "--user-number",
                      help="put N random users instead of importing them",
                      dest="user_num", action="store", type="int",
                      default=None)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the contest directory")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")
    if options.test and options.zero_time:
        parser.error("At most one between `-z' and `-t' can be specified")

    modif = None
    if options.test:
        modif = 'test'
    elif options.zero_time:
        modif = 'zero_time'

    path = args[0]

    yaml_importer = YamlImporter(shard=options.shard,
                                 drop=options.drop,
                                 modif=modif,
                                 path=path,
                                 user_num=options.user_num).run()


if __name__ == "__main__":
    main()
