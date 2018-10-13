#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014-2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2015-2016 Luca Chiodini <luca@chiodini.org>
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

"""This script imports a contest from disk using one of the available
loaders.

The data parsed by the loader is used to create a new Contest in the
database.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import datetime
import ipaddress
import logging
import os
import sys

from cms import utf8_decoder
from cms.db import SessionGen, User, Team, Participation, Task, Contest
from cms.db.filecacher import FileCacher
from cmscontrib.importing import ImportDataError, update_contest, update_task
from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class ContestImporter:

    """This script creates a contest and all its associations to users
    and tasks.

    """

    def __init__(self, path, yes, zero_time, import_tasks,
                 update_contest, update_tasks, no_statements,
                 delete_stale_participations, loader_class):
        self.yes = yes
        self.zero_time = zero_time
        self.import_tasks = import_tasks
        self.update_contest = update_contest
        self.update_tasks = update_tasks
        self.no_statements = no_statements
        self.delete_stale_participations = delete_stale_participations
        self.file_cacher = FileCacher()

        self.loader = loader_class(os.path.abspath(path), self.file_cacher)

    def do_import(self):
        """Get the contest from the Loader and store it."""

        # We need to check whether the contest has changed *before* calling
        # get_contest() as that method might reset the "has_changed" bit.
        contest_has_changed = False
        if self.update_contest:
            contest_has_changed = self.loader.contest_has_changed()

        # Get the contest. The loader should give a bare contest, putting tasks
        # and participations only in the other return values. We make sure.
        contest, tasks, participations = self.loader.get_contest()
        if contest.tasks != []:
            contest.tasks = []
            logger.warning("Contest loader should not fill tasks.")
        if contest.participations != []:
            contest.participations = []
            logger.warning("Contest loader should not fill participations.")
        tasks = tasks if tasks is not None else []
        participations = participations if participations is not None else []

        # Apply the modification flags
        if self.zero_time:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(1970, 1, 1)

        with SessionGen() as session:
            try:
                contest = self._contest_to_db(
                    session, contest, contest_has_changed)
                # Detach all tasks before reattaching them
                for t in list(contest.tasks):
                    t.contest = None
                for tasknum, taskname in enumerate(tasks):
                    self._task_to_db(session, contest, tasknum, taskname)
                # Delete stale participations if asked to, then import all
                # others.
                if self.delete_stale_participations:
                    self._delete_stale_participations(
                        session, contest,
                        set(p["username"] for p in participations))
                for p in participations:
                    self._participation_to_db(session, contest, p)

            except ImportDataError as e:
                logger.error(str(e))
                logger.info("Error while importing, no changes were made.")
                return False

            session.commit()
            contest_id = contest.id

        logger.info("Import finished (new contest id: %s).", contest_id)
        return True

    def _contest_to_db(self, session, new_contest, contest_has_changed):
        """Add the new contest to the DB

        session (Session): session to use.
        new_contest (Contest): contest that has to end up in the DB.
        contest_has_changed (bool): whether the loader thinks new_contest has
            changed since the last time it was imported.

        return (Contest): the contest in the DB.

        raise (ImportDataError): if the contest already exists on the DB and
            the user did not ask to update any data.

        """
        contest = session.query(Contest)\
            .filter(Contest.name == new_contest.name).first()

        if contest is None:
            # Contest not present, we import it.
            logger.info("Creating contest on the database.")
            contest = new_contest
            session.add(contest)

        else:
            if not (self.update_contest or self.update_tasks):
                # Contest already present, but user did not ask to update any
                # data. We cannot import anything and this is most probably
                # not what the user wanted, so we let them know.
                raise ImportDataError(
                    "Contest \"%s\" already exists in database. "
                    "Use --update-contest to update it." % contest.name)

            if self.update_contest:
                # Contest already present, user asked us to update it; we do so
                # if it has changed.
                if contest_has_changed:
                    logger.info("Contest data has changed, updating it.")
                    update_contest(contest, new_contest)
                else:
                    logger.info("Contest data has not changed.")

        return contest

    def _task_to_db(self, session, contest, tasknum, taskname):
        """Add the task to the DB and attach it to the contest

        session (Session): session to use.
        contest (Contest): the contest in the DB.
        tasknum (int): num the task should have in the contest.
        taskname (string): name of the task.

        return (Task): the task in the DB.

        raise (ImportDataError): in case of one of these errors:
            - if the task is not in the DB and user did not ask to import it;
            - if the loader cannot load the task;
            - if the task is already in the DB, attached to another contest.

        """
        task_loader = self.loader.get_task_loader(taskname)
        task = session.query(Task).filter(Task.name == taskname).first()

        if task is None:
            # Task is not in the DB; if the user asked us to import it, we do
            # so, otherwise we return an error.

            if not self.import_tasks:
                raise ImportDataError(
                    "Task \"%s\" not found in database. "
                    "Use --import-task to import it." % taskname)

            task = task_loader.get_task(get_statement=not self.no_statements)
            if task is None:
                raise ImportDataError(
                    "Could not import task \"%s\"." % taskname)

            session.add(task)

        elif not task_loader.task_has_changed():
            # Task is in the DB and has not changed, nothing to do.
            logger.info("Task \"%s\" data has not changed.", taskname)

        elif self.update_tasks:
            # Task is in the DB, but has changed, and the user asked us to
            # update it. We do so.
            new_task = task_loader.get_task(
                get_statement=not self.no_statements)
            if new_task is None:
                raise ImportDataError(
                    "Could not reimport task \"%s\"." % taskname)
            logger.info("Task \"%s\" data has changed, updating it.", taskname)
            update_task(task, new_task, get_statements=not self.no_statements)

        else:
            # Task is in the DB, has changed, and the user didn't ask to update
            # it; we just show a warning.
            logger.warning("Not updating task \"%s\", even if it has changed. "
                           "Use --update-tasks to update it.", taskname)

        # Finally we tie the task to the contest, if it is not already used
        # elsewhere.
        if task.contest is not None and task.contest.name != contest.name:
            raise ImportDataError(
                "Task \"%s\" is already tied to contest \"%s\"."
                % (taskname, task.contest.name))

        task.num = tasknum
        task.contest = contest
        return task

    @staticmethod
    def _participation_to_db(session, contest, new_p):
        """Add the new participation to the DB and attach it to the contest

        session (Session): session to use.
        contest (Contest): the contest in the DB.
        new_p (dict): dictionary with the participation data, including at
            least "username"; may contain "team", "hidden", "ip", "password".

        return (Participation): the participation in the DB.

        raise (ImportDataError): in case of one of these errors:
            - the user for this participation does not already exist in the DB;
            - the team for this participation does not already exist in the DB.

        """
        user = session.query(User)\
            .filter(User.username == new_p["username"]).first()
        if user is None:
            # FIXME: it would be nice to automatically try to import.
            raise ImportDataError("User \"%s\" not found in database. "
                                  "Use cmsImportUser to import it." %
                                  new_p["username"])

        team = session.query(Team)\
            .filter(Team.code == new_p.get("team")).first()
        if team is None and new_p.get("team") is not None:
            # FIXME: it would be nice to automatically try to import.
            raise ImportDataError("Team \"%s\" not found in database. "
                                  "Use cmsImportTeam to import it."
                                  % new_p.get("team"))

        # Check that the participation is not already defined.
        p = session.query(Participation)\
            .filter(Participation.user_id == user.id)\
            .filter(Participation.contest_id == contest.id)\
            .first()
        # FIXME: detect if some details of the participation have been updated
        # and thus the existing participation needs to be changed.
        if p is not None:
            logger.warning("Participation of user %s in this contest already "
                           "exists, not updating it.", new_p["username"])
            return p

        # Prepare new participation
        args = {
            "user": user,
            "contest": contest,
        }
        if "team" in new_p:
            args["team"] = team
        if "hidden" in new_p:
            args["hidden"] = new_p["hidden"]
        if "ip" in new_p and new_p["ip"] is not None:
            args["ip"] = [ipaddress.ip_network(new_p["ip"])]
        if "password" in new_p:
            args["password"] = new_p["password"]

        new_p = Participation(**args)
        session.add(new_p)
        return new_p

    def _delete_stale_participations(self, session, contest,
                                     usernames_to_keep):
        """Delete the stale participations.

        Stale participations are those in the contest, with a username not in
        usernames_to_keep.

        session (Session): SQL session to use.
        contest (Contest): the contest to examine.
        usernames_to_keep ({str}): usernames of non-stale participations.

        """
        participations = [p for p in contest.participations
                          if p.user.username not in usernames_to_keep]
        if participations:
            ans = "y"
            if not self.yes:
                ans = input("There are %s stale participations. "
                            "Are you sure you want to delete them and their "
                            "associated data, including submissions? [y/N] "
                            % len(participations))\
                    .strip().lower()
            if ans in ["y", "yes"]:
                for p in participations:
                    logger.info("Deleting participations for user %s.",
                                p.user.username)
                    session.delete(p)


def main():
    """Parse arguments and launch process."""

    parser = argparse.ArgumentParser(
        description="""\
Import a contest from disk

If updating a contest already in the DB:
- tasks attached to the contest in the DB but not to the contest to be imported
  will be detached;
- participations attached to the contest in the DB but not to the contest to be
  imported will be retained, this to avoid deleting submissions.

""",
        epilog=build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="don't ask for confirmation before deleting data"
    )
    parser.add_argument(
        "-z", "--zero-time",
        action="store_true",
        help="set to zero contest start and stop time"
    )
    parser.add_argument(
        "-L", "--loader",
        action="store", type=utf8_decoder,
        default=None,
        help="use the specified loader (default: autodetect)"
    )
    parser.add_argument(
        "-i", "--import-tasks",
        action="store_true",
        help="import tasks if they do not exist"
    )
    parser.add_argument(
        "-u", "--update-contest",
        action="store_true",
        help="update an existing contest"
    )
    parser.add_argument(
        "-U", "--update-tasks",
        action="store_true",
        help="update existing tasks"
    )
    parser.add_argument(
        "-S", "--no-statements",
        action="store_true",
        help="do not import / update task statements"
    )
    parser.add_argument(
        "--delete-stale-participations",
        action="store_true",
        help="when updating a contest, delete the participations not in the "
        "new contest, including their submissions and other data"
    )
    parser.add_argument(
        "import_directory",
        action="store", type=utf8_decoder,
        help="source directory from where import"
    )

    args = parser.parse_args()

    loader_class = choose_loader(
        args.loader,
        args.import_directory,
        parser.error
    )

    importer = ContestImporter(
        path=args.import_directory,
        yes=args.yes,
        zero_time=args.zero_time,
        import_tasks=args.import_tasks,
        update_contest=args.update_contest,
        update_tasks=args.update_tasks,
        no_statements=args.no_statements,
        delete_stale_participations=args.delete_stale_participations,
        loader_class=loader_class)
    success = importer.do_import()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
