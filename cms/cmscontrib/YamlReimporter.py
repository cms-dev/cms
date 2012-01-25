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

import optparse

from cms.async import ServiceCoord
from cms.async.AsyncLibrary import Service
from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.db.Utils import analyze_all_tables, ask_for_contest
from cms.service.FileStorage import FileCacher
from cms.service.LogService import logger

from cmscontrib.YamlImporter import YamlLoader


class YamlReimporter(Service):

    def __init__(self, shard, path, contest_id):
        self.path = path
        self.contest_id = contest_id

        logger.initialize(ServiceCoord("YamlReimporter", shard))
        Service.__init__(self, shard, custom_logger=logger)
        self.FC = FileCacher(self)

        self.loader = YamlLoader(self.FC, False, None, None)

        self.add_timeout(self.do_reimport, None, 10, immediately=True)

    def do_reimport(self):
        # Create the dict corresponding to the new contest
        yaml_contest = self.loader.import_contest(self.path)
        yaml_users = dict(map(lambda x: (x['username'], x),
                              yaml_contest['users']))
        yaml_tasks = dict(map(lambda x: (x['name'], x),
                              yaml_contest['tasks']))

        with SessionGen(commit=False) as session:

            # Create the dict corresponding to the old contest, from
            # the database
            contest = Contest.get_from_id(self.contest_id, session)
            cms_contest = contest.export_to_dict()
            cms_users = dict(map(lambda x: (x['username'], x),
                                 cms_contest['users']))
            cms_tasks = dict(map(lambda x: (x['name'], x),
                                 cms_contest['tasks']))

            # Delete the old contest from the database
            session.delete(contest)
            session.flush()

            # Do the actual merge: first of all update all users of
            # the old contest with the corresponding ones from the new
            # contest; fail if some user is present in the old contest
            # but not in the new one
            for user_num, user in enumerate(cms_contest['users']):
                try:
                    user_submissions = \
                        cms_contest['users'][user_num]['submissions']
                    cms_contest['users'][user_num] = \
                        yaml_users[user['username']]
                    cms_contest['users'][user_num]['submissions'] = \
                        user_submissions
                except KeyError:
                    logger.error("User %s exists in old contest, "
                                 "but not in the new one" % (user['username']))

            # The append the users in the new contest, not present in
            # the old one
            for user in yaml_contest['users']:
                if user['username'] not in cms_users.keys():
                    cms_contest['users'].append(user)

            # The same for tasks: update old tasks
            for task_num, task in enumerate(cms_contest['tasks']):
                try:
                    cms_contest['tasks'][task_num] = yaml_tasks[task['name']]
                except KeyError:
                    logger.error("Task %d exists in old contest, "
                                 "but not in the new one" % (task['name']))

            # And add new tasks
            for task in yaml_contest['tasks']:
                if task['name'] not in cms_tasks.keys():
                    cms_contest['tasks'].append(task)

            # Reimport the contest in the database, with the previous ID
            contest = Contest.import_from_dict(cms_contest)
            contest.id = self.contest_id
            session.add(contest)
            session.flush()

            logger.info("Analyzing database.")
            analyze_all_tables(session)
            session.commit()

        logger.info("Reimport of contest %d finished." % (self.contest_id))

        self.exit()
        return False


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    parser.add_option("-c", "--contest",
                      help="contest ID to overwrite",
                      dest="contest_id", action="store", type="int",
                      default=None)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the contest directory")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")

    contest_id = options.contest_id
    if contest_id is None:
        contest_id = ask_for_contest()

    path = args[0]

    YamlReimporter(shard=options.shard,
                   path=path,
                   contest_id=contest_id).run()


if __name__ == "__main__":
    main()
