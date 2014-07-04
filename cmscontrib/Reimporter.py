#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Versari <veluca93@gmail.com>
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

"""This script reimports a contest from disk using one of the
available loaders.

The data parsed by the loader is used to update a Contest that's
already existing in the database.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import logging
import os
import os.path

from cms import utf8_decoder
from cms.db import SessionGen, Base, Contest, User, Task, Submission, \
    ask_for_contest
from cms.db.filecacher import FileCacher

from cmscontrib.Loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


def _is_rel(prp, attr):
    # The target of the relationship is in prp.mapper.class_
    return prp.parent.class_ == attr.class_ and prp.key == attr.key


class Reimporter(object):

    """This script reimports a contest from disk using the specified
    loader.

    The data parsed by the loader is used to update a Contest that's
    already existing in the database.

    """

    def __init__(self, path, contest_id, force, loader_class, full):
        self.old_contest_id = contest_id
        self.force = force
        self.full = full

        self.file_cacher = FileCacher()

        self.loader = loader_class(os.path.realpath(path), self.file_cacher)

    def _update_columns(self, old_object, new_object):
        for prp in old_object._col_props:
            if hasattr(new_object, prp.key):
                setattr(old_object, prp.key, getattr(new_object, prp.key))

    def _update_object(self, old_object, new_object):
        # This method copies the scalar column properties from the new
        # object into the old one, and then tries to do the same for
        # relationships too. The data model isn't a tree: for example
        # there are two distinct paths from Contest to Submission, one
        # through User and one through Task. Yet, at the moment, if we
        # ignore Submissions and UserTest (and thus their results, too)
        # we get a tree-like structure and Task.active_dataset and
        # Submission.token are the only scalar relationships that don't
        # refer to the parent. Therefore, if we catch these as special
        # cases, we can use a simple DFS to explore the whole data
        # graph, recursing only on "vector" relationships.
        # TODO Find a better way to handle all of this.

        self._update_columns(old_object, new_object)

        for prp in old_object._rel_props:
            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            # Special case #1: Contest.announcements, User.questions,
            #                  User.messages
            if _is_rel(prp, Contest.announcements) or \
                    _is_rel(prp, User.questions) or \
                    _is_rel(prp, User.messages):
                # A loader should not provide new Announcements,
                # Questions or Messages, since they are data generated
                # by the users during the contest: don't update them.
                # TODO Warn the admin if these attributes are non-empty
                # collections.
                pass

            # Special case #2: Task.datasets
            elif _is_rel(prp, Task.datasets):
                old_datasets = dict((d.description, d) for d in old_value)
                new_datasets = dict((d.description, d) for d in new_value)

                for key in set(new_datasets.keys()):
                    if key not in old_datasets:
                        # create
                        temp = new_datasets[key]
                        new_value.remove(temp)
                        old_value.append(temp)
                    else:
                        # update
                        self._update_object(old_datasets[key],
                                            new_datasets[key])

            # Special case #3: Task.active_dataset
            elif _is_rel(prp, Task.active_dataset):
                # We don't want to update the existing active dataset.
                pass

            # Special case #4: User.submissions, Task.submissions,
            #                  User.user_tests, Task.user_tests
            elif _is_rel(prp, User.submissions) or \
                    _is_rel(prp, Task.submissions) or \
                    _is_rel(prp, User.user_tests) or \
                    _is_rel(prp, Task.user_tests):
                # A loader should not provide new Submissions or
                # UserTests, since they are data generated by the users
                # during the contest: don't update them.
                # TODO Warn the admin if these attributes are non-empty
                # collections.
                pass

            # Special case #5: Submission.token
            elif _is_rel(prp, Submission.token):
                # We should never reach this point! We should never try
                # to update Submissions! We could even assert False...
                pass

            # General case #1: a dict
            elif isinstance(old_value, dict):
                for key in set(old_value.keys()) | set(new_value.keys()):
                    if key in new_value:
                        if key not in old_value:
                            # create
                            # FIXME This hack is needed because of some
                            # funny behavior of SQLAlchemy-instrumented
                            # collections when copying values, that
                            # resulted in new objects being added to
                            # the session. We need to investigate it.
                            temp = new_value[key]
                            del new_value[key]
                            old_value[key] = temp
                        else:
                            # update
                            self._update_object(old_value[key], new_value[key])
                    else:
                        # delete
                        del old_value[key]

            # General case #2: a list
            elif isinstance(old_value, list):
                old_len = len(old_value)
                new_len = len(new_value)
                for i in xrange(min(old_len, new_len)):
                    self._update_object(old_value[i], new_value[i])
                if old_len > new_len:
                    del old_value[new_len:]
                elif new_len > old_len:
                    for i in xrange(old_len, new_len):
                        # FIXME This hack is needed because of some
                        # funny behavior of SQLAlchemy-instrumented
                        # collections when copying values, that
                        # resulted in new objects being added to the
                        # session. We need to investigate it.
                        temp = new_value[i]
                        del new_value[i]
                        old_value.append(temp)

            # General case #3: a parent object
            elif isinstance(old_value, Base):
                # No need to climb back up the recursion tree...
                pass

            # General case #4: None
            elif old_value is None:
                # That should only happen in case of a scalar
                # relationship (i.e. a many-to-one or a one-to-one)
                # that is nullable. "Parent" relationships aren't
                # nullable, so the only possible cases are the active
                # datasets and the tokens, but we should have already
                # caught them. We could even assert False...
                pass

            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))

    def do_reimport(self):
        """Get the contest from the Loader and merge it."""
        with SessionGen() as session:
            # Load the old contest from the database.
            old_contest = Contest.get_from_id(self.old_contest_id, session)
            old_users = dict((x.username, x) for x in old_contest.users)
            old_tasks = dict((x.name, x) for x in old_contest.tasks)

            # Load the new contest from the filesystem.
            new_contest, new_tasks, new_users = self.loader.get_contest()

            # Updates contest-global settings that are set in new_contest.
            self._update_columns(old_contest, new_contest)

            # Do the actual merge: compare all users of the old and of
            # the new contest and see if we need to create, update or
            # delete them. Delete only if authorized, fail otherwise.
            users = set(old_users.keys()) | set(new_users)
            for username in users:
                old_user = old_users.get(username, None)

                if old_user is None:
                    # Create a new user.
                    logger.info("Creating user %s" % username)
                    new_user = self.loader.get_user(username)
                    old_contest.users.append(new_user)
                elif username in new_users:
                    # Update an existing user.
                    logger.info("Updating user %s" % username)
                    new_user = self.loader.get_user(username)
                    self._update_object(old_user, new_user)
                else:
                    # Delete an existing user.
                    if self.force:
                        logger.info("Deleting user %s" % username)
                        old_contest.users.remove(old_user)
                    else:
                        logger.critical(
                            "User %s exists in old contest, but "
                            "not in the new one. Use -f to force." %
                            username)
                        return False

            # The same for tasks. Setting num for tasks requires a bit
            # of trickery, since we have to avoid triggering a
            # duplicate key constraint violation while we're messing
            # with the task order. To do that we just set sufficiently
            # high number on the first pass and then fix it on a
            # second pass.
            tasks = set(old_tasks.keys()) | set(new_tasks)
            current_num = max(len(old_tasks), len(new_tasks))
            for task in tasks:
                old_task = old_tasks.get(task, None)

                if old_task is None:
                    # Create a new task.
                    logger.info("Creating task %s" % task)
                    new_task = self.loader.get_task(task)
                    new_task.num = current_num
                    current_num += 1
                    old_contest.tasks.append(new_task)
                elif task in new_tasks:
                    # Update an existing task.
                    if self.full or self.loader.has_changed(task):
                        logger.info("Updating task %s" % task)
                        new_task = self.loader.get_task(task)
                        new_task.num = current_num
                        current_num += 1
                        self._update_object(old_task, new_task)
                    else:
                        logger.info("Task %s has not changed" % task)
                        # Even unchanged tasks should use a temporary number
                        # to avoid duplicate numbers when we fix them.
                        old_task.num = current_num
                        current_num += 1
                else:
                    # Delete an existing task.
                    if self.force:
                        logger.info("Deleting task %s" % task)
                        session.delete(old_task)
                    else:
                        logger.critical(
                            "Task %s exists in old contest, but "
                            "not in the new one. Use -f to force." %
                            task)
                        return False

                session.flush()

            # And finally we fix the numbers; old_contest must be
            # refreshed because otherwise SQLAlchemy doesn't get aware
            # that some tasks may have been deleted
            tasks_order = dict((name, num)
                               for num, name in enumerate(new_tasks))
            session.refresh(old_contest)
            for task in old_contest.tasks:
                task.num = tasks_order[task.name]

            session.commit()

        logger.info("Reimport finished (contest id: %s)." %
                    self.old_contest_id)

        return True


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Reimport a contest from disk",
        epilog=build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest to overwrite")
    parser.add_argument("-f", "--force", action="store_true",
                        help="force the reimport even if some users or tasks "
                        "may get lost")
    parser.add_argument("-L", "--loader",
                        action="store", type=utf8_decoder, default=None,
                        help="use the specified loader (default: autodetect)")
    parser.add_argument("-F", "--full", action="store_true",
                        help="reimport tasks even if they haven't changed")
    parser.add_argument("import_directory", action="store", type=utf8_decoder,
                        help="source directory from where import")

    args = parser.parse_args()
    loader_class = choose_loader(args.loader,
                                 args.import_directory,
                                 parser.error)

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    Reimporter(path=args.import_directory,
               contest_id=args.contest_id,
               force=args.force,
               loader_class=loader_class,
               full=args.full).do_reimport()


if __name__ == "__main__":
    main()
