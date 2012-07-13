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
one used in Italian IOI repository ***over*** a contest already in
CMS.

"""

import argparse

from cms import logger
from cms.db import analyze_all_tables, ask_for_contest
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import SessionGen, Contest

from cmscontrib.YamlImporter import YamlLoader


class YamlReimporter:
    """This service load a contest from a tree structure "similar" to
    the one used in Italian IOI repository ***over*** a contest
    already in CMS.

    """
    def __init__(self, path, contest_id, force=False):
        self.path = path
        self.contest_id = contest_id
        self.force = force

        self.file_cacher = FileCacher()

        self.loader = YamlLoader(self.file_cacher, False, None, None)

    def run(self):
        """Interface to make the class do its job."""
        self.do_reimport()

    def do_reimport(self):
        """Ask the loader to load the contest and actually merge the
        two.

        """
        # Create the dict corresponding to the new contest.
        yaml_contest = self.loader.import_contest(self.path)
        yaml_users = dict(((x['username'], x) for x in yaml_contest['users']))
        yaml_tasks = dict(((x['name'], x) for x in yaml_contest['tasks']))

        with SessionGen(commit=False) as session:

            # Create the dict corresponding to the old contest, from
            # the database.
            contest = Contest.get_from_id(self.contest_id, session)
            cms_contest = contest.export_to_dict()
            cms_users = dict((x['username'], x) for x in cms_contest['users'])
            cms_tasks = dict((x['name'], x) for x in cms_contest['tasks'])

            # Delete the old contest from the database.
            session.delete(contest)
            session.flush()

            # Do the actual merge: first of all update all users of
            # the old contest with the corresponding ones from the new
            # contest; if some user is present in the old contest but
            # not in the new one we check if we have to fail or remove
            # it and, in the latter case, add it to a list
            users_to_remove = []
            for user_num, user in enumerate(cms_contest['users']):
                try:
                    user_submissions = \
                        cms_contest['users'][user_num]['submissions']
                    cms_contest['users'][user_num] = \
                        yaml_users[user['username']]
                    cms_contest['users'][user_num]['submissions'] = \
                        user_submissions
                except KeyError:
                    if self.force:
                        logger.warning("User %s exists in old contest, but "
                                       "not in the new one" % user['username'])
                        users_to_remove.append(user_num)
                        session.delete(contest.users[user_num])
                    else:
                        logger.error("User %s exists in old contest, but "
                                     "not in the new one" % user['username'])
                        return False

            # Delete the users
            for user_num in users_to_remove:
                del cms_contest['users'][user_num]

            # The append the users in the new contest, not present in
            # the old one.
            for user in yaml_contest['users']:
                if user['username'] not in cms_users.keys():
                    cms_contest['users'].append(user)

            # The same for tasks: update old tasks.
            tasks_to_remove = []
            for task_num, task in enumerate(cms_contest['tasks']):
                try:
                    cms_contest['tasks'][task_num] = yaml_tasks[task['name']]
                except KeyError:
                    if self.force:
                        logger.warning("Task %s exists in old contest, but "
                                       "not in the new one" % task['name'])
                        tasks_to_remove.append(task_num)
                        session.delete(contest.tasks[task_num])
                    else:
                        logger.error("Task %s exists in old contest, but "
                                     "not in the new one" % task['name'])
                        return False

            # Delete the tasks
            for task_num in tasks_to_remove:
                del cms_contest['tasks'][task_num]

            # And add new tasks.
            for task in yaml_contest['tasks']:
                if task['name'] not in cms_tasks.keys():
                    cms_contest['tasks'].append(task)

            # Reimport the contest in the db, with the previous ID.
            contest = Contest.import_from_dict(cms_contest)
            contest.id = self.contest_id
            session.add(contest)
            session.flush()

            logger.info("Analyzing database.")
            analyze_all_tables(session)
            session.commit()

        logger.info("Reimport of contest %s finished." % self.contest_id)

        return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Load a contest from the Italian repository "
        "over an old one in CMS.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest to overwrite")
    parser.add_argument("-f", "--force", action="store_true",
                        help="force the reimport even if some users or tasks "
                        "may get lost")
    parser.add_argument("import_directory",
                        help="source directory from where import")

    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    YamlReimporter(path=args.import_directory,
                   contest_id=args.contest_id,
                   force=args.force).run()


if __name__ == "__main__":
    main()
