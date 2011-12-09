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
from cms.db.SQLAlchemyAll import metadata, Session, Task, Manager, \
    Testcase, User, Contest, SubmissionFormatElement
from cms.service.FileStorage import FileCacher
from cms.service.ScoreType import ScoreTypes
from cms.async.AsyncLibrary import rpc_callback, Service, logger
from cms.db.Utils import analyze_all_tables, ask_for_contest


class YamlReimporter(Service):

    def __init__(self, shard, path, contest_id):
        self.path = path
        self.contest_id = contest_id

        logger.initialize(ServiceCoord("YamlReimporter", shard))
        logger.debug("YamlReimporter.__init__")
        Service.__init__(self, shard)
        self.FS = self.connect_to(ServiceCoord("FileStorage", 0))
        self.FC = FileCacher(self, self.FS)
        self.add_timeout(self.do_reimport, None, 10, immediately=True)

    def get_params_for_contest(self, path):
        """Given the path of a contest, extract the data from its
        contest.yaml file, and create a dictionary with the parameter
        to give to the Contest class. Since tasks and users need to be
        handled differently if we are doing an import or a reimport,
        we do not fill the dictionary with tasks' and users'
        information, but we return the lists of their names after the
        dictionay of parameters.

        """
        path = os.path.realpath(path)
        name = os.path.split(path)[1]
        conf = yaml.load(codecs.open(\
                os.path.join(path, "contest.yaml"),
                "r", "utf-8"))

        logger.info("Loading parameters for contest %s." % (name))

        params = {"name": name}
        assert name == conf["nome_breve"]
        params["description"] = conf["nome"]
        params["token_initial"] = conf.get("token_initial", 0)
        params["token_max"] = conf.get("token_max", None)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", None)
        params["token_gen_time"] = conf.get("token_gen_time", None)
        params["token_gen_number"] = conf.get("token_gen_number", None)
        params["start"] = conf.get("inizio", 0)
        params["stop"] = conf.get("fine", 0)

        logger.info("Contest parameters loaded.")

        return params, conf["problemi"], conf["utenti"]

    def get_params_for_user(self, user_dict):
        """Given the dictionary of information of a user (extracted
        from contest.yaml), it fills another dictionary with the
        parameters to give to our class User.

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

        logger.info("User parameters loaded.")

        return params

    def get_params_for_task(self, path):
        """Given the path of a task, this function put all needed data
        into FS, and fills the dictionary of parameters to pass to the
        class Task.

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
                                                               (name))]

        if os.path.exists(os.path.join(path, "cor", "correttore")):
            params["managers"] = {
                "checker": Manager(self.FC.put_file(
                    path=os.path.join(path, "cor", "correttore"),
                    description="Manager for task %s" % (name)))}
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
                public=(i in public_testcases)))
        params["token_initial"] = conf.get("token_initial", 0)
        params["token_max"] = conf.get("token_max", None)
        params["token_total"] = conf.get("token_total", None)
        params["token_min_interval"] = conf.get("token_min_interval", None)
        params["token_gen_time"] = conf.get("token_gen_time", None)
        params["token_gen_number"] = conf.get("token_gen_number", None)

        logger.info("Task parameters loaded.")

        return params

    def import_contest(self):
        """Import a contest into the system.
        """
        params, tasks, users = self.get_params_for_contest(self.path)
        params["tasks"] = []
        for task in tasks:
            task_params = self.get_params_for_task(os.path.join(self.path,
                                                                task))
            params["tasks"].append(Task(**task_params))
        params["users"] = []
        for user in users:
            user_params = self.get_params_for_user(user)
            params["users"].append(User(**user_params))
        return Contest(**params)

    def do_reimport(self):
        if not self.FS.connected:
            logger.warning("Please run FileStorage.")
            return True

        yaml_contest = self.import_contest()

        session = Session()
        cms_contest = session.query(Contest).\
            filter_by(id=contest_id).first()

        # TODO: implement reimport. The following is what we had
        # before.

        # params["tasks"] = []
        # for task in tasks:
        #     matching_tasks = [x for x in old_contest.tasks if x.name == task]
        #     if matching_tasks != []:
        #         params["tasks"].append(reimport_task(matching_tasks[0],
        #                                              os.path.join(path, task)))
        #     else:
        #         params["tasks"].append(reimport_task(None,
        #                                              os.path.join(path, task)))

        # params["users"] = []
        # for user in users:
        #     matching_users = [x for x in old_contest.users
        #                       if x.username == user["username"]]
        #     if matching_users != []:
        #         params["users"].append(reimport_user(matching_users[0], user))
        #     else:
        #         params["users"].append(reimport_user(None, user))

        # for i in xrange(Configuration.maximum_conflict_attempts):
        #     try:
        #         old_contest.__dict__.update(params)
        #         old_contest.to_couch()
        #         return old_contest
        #     except couchdb.ResourceConflict:
        #         old_contest.refresh()
        # else:
        #     raise couchdb.ResourceConflict()

        session.flush()

        contest_id = c.id

        logger.info("Analyzing database.")
        analyze_all_tables(session)
        session.commit()
        session.close()

        logger.info("Reimport finished.")

        self.exit()
        return False


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the contest directory")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")

    path = args[0]

    yaml_importer = YamlImporter(shard=options.shard,
                                 path=path,
                                 ask_for_contest(1)).run()


if __name__ == "__main__":
    main()
