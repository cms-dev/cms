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

import os
import couchdb
import sys

from YamlImporter import get_params_for_contest, \
    get_params_for_user, get_params_for_task
from Task import Task
from User import User
import Configuration
import Utils


def reimport_contest(path, old_contest):
    """Tries to overwrite a given contest already in the system with
    the data coming from another contest outside the system. After
    doing this, it is at least needed to restart ES.

    Note: if the reimport fails for too many conflicts in the contest,
    then tasks and users not linked to any contest may appear in the
    couchdb.
    """
    params, tasks, users = get_params_for_contest(path)

    params["couch_id"] = old_contest.couch_id
    params["couch_rev"] = old_contest.couch_rev

    params["tasks"] = []
    for task in tasks:
        matching_tasks = [x for x in old_contest.tasks if x.name == task]
        if matching_tasks != []:
            params["tasks"].append(reimport_task(matching_tasks[0],
                                                 os.path.join(path, task)))
        else:
            params["tasks"].append(reimport_task(None,
                                                 os.path.join(path, task)))

    params["users"] = []
    for user in users:
        matching_users = [x for x in old_contest.users
                          if x.username == user["username"]]
        if matching_users != []:
            params["users"].append(reimport_user(matching_users[0], user))
        else:
            params["users"].append(reimport_user(None, user))

    for i in xrange(Configuration.maximum_conflict_attempts):
        try:
            old_contest.__dict__.update(params)
            old_contest.to_couch()
            return old_contest
        except couchdb.ResourceConflict:
            old_contest.refresh()
    else:
        raise couchdb.ResourceConflict()


def reimport_user(old_user, user_dict):
    """Refresh the information of a user.
    """
    params = get_params_for_user(user_dict)
    for i in xrange(Configuration.maximum_conflict_attempts):
        try:
            if old_user == None:
                renewed_user = User(**params)
            else:
                old_user.__dict__.update(params)
                renewed_user = old_user
            renewed_user.to_couch()
            return renewed_user
        except couchdb.ResourceConflict:
            old_user.refresh()
    else:
        raise couchdb.ResourceConflict()


def reimport_task(old_task, path):
    """Refresh the information of a task (also the files in FS).
    """
    params = get_params_for_task(path)
    for i in xrange(Configuration.maximum_conflict_attempts):
        try:
            if old_task == None:
                renewed_task = Task(**params)
            else:
                old_task.__dict__.update(params)
                renewed_task = old_task

            renewed_task.to_couch()
            return renewed_task
        except couchdb.ResourceConflict:
            old_task.refresh()
    else:
        raise couchdb.ResourceConflict()


if __name__ == "__main__":
    c = Utils.ask_for_contest(1)
    c = reimport_contest(sys.argv[1], c)
    print "Couch ID: %s" % (c.couch_id)
