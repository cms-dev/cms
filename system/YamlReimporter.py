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

from Task import Task
from User import User
from Contest import Contest
from ScoreType import ScoreTypes
from FileStorageLib import FileStorageLib
import Configuration
import Utils

def reimport_contest(path, old_contest):
    path = os.path.realpath(path)
    super_path, name = os.path.split(path)
    conf = yaml.load(open(os.path.join(path,"contest.yaml")))

    params = {"name": name, "couch_id": old_contest.couch_id, "couch_rev": old_contest.couch_rev}
    assert name == conf["nome_breve"]
    params["description"] = conf["nome"]
    params["tasks"] = []
    for task in conf["problemi"]:
        matching_tasks = [ x for x in old_contest.tasks if x.name == task ]
        if matching_tasks != []:
          params["tasks"].append(reimport_task(matching_tasks[0], os.path.join(path, task)))
        else:
          params["tasks"].append(reimport_task(None, os.path.join(path, task)))
        
    params["token_initial"] = conf.get("token_initial", 0)
    params["token_max"] = conf.get("token_max", 0)
    params["token_total"] = conf.get("token_total", 0)
    params["token_min_interval"] = conf.get("token_min_interval", 0)
    params["token_gen_time"] = conf.get("token_gen_time", 1)
    params["users"] = []
    for user in conf["utenti"]:
        matching_users = [ x for x in old_contest.users if x.username == user["username"] ]
        if matching_users != []:
            params["users"].append(reimport_user(matching_users[0],user))
        else:
            params["users"].append(reimport_user(None,user))

    params["start"] = conf["inizio"]
    params["stop"] = conf["fine"]

    for i in xrange(Configuration.maximum_conflict_attempts):
      try:
          old_contest.__dict__.update(params)
          old_contest.to_couch()
          return old_contest
      except couchdb.ResourceConflict as e:
          old_contest.refresh()
    else:
        raise couchdb.ResourceConflict()

def reimport_user(old_user, user_dict):
    
    params = {}

    params["username"] = user_dict["username"]
    params["password"] = user_dict["password"]
    name = user_dict.get("nome", "")
    surname = user_dict.get("cognome", user_dict["username"])
    params["real_name"] = " ".join([name, surname])
    params["ip"] = user_dict.get("ip", "0.0.0.0")
    params["hidden"] = user_dict.get("fake", False)
    params["tokens"] = []

    for i in xrange(Configuration.maximum_conflict_attempts):
        try:
            if old_user == None:
                renewed_user = User(**params)
            else:
                old_user.__dict__.update(params)
                renewed_user = old_user
            renewed_user.to_couch()
            return renewed_user
        except couchdb.ResourceConflict as e:
            old_user.refresh()
    else:
        raise couchdb.ResourceConflict()



def reimport_task(old_task, path):
    path = os.path.realpath(path)
    super_path, name = os.path.split(path)
    conf = yaml.load(open(os.path.join(super_path, name + ".yaml")))
    FSL = FileStorageLib()

    params = {"name": name}

    assert name == conf["nome_breve"]
    params["title"] = conf["nome"]
    params["time_limit"] = conf["timeout"]
    params["memory_limit"] = conf["memlimit"]
    params["attachments"] = [] # FIXME - Use auxiliary
    params["statement"] = FSL.put(os.path.join(path, "testo", "testo.pdf"), "PDF statement for task %s" % (name))
    params["task_type"] = Task.TASK_TYPE_BATCH
    params["submission_format"] = ["%s.%%l" % (name)]
    try:
        fd = open(os.path.join(path, "cor", "correttore"))
    except IOError:
        fd = None
    if fd != None:
        params["managers"] = { "checker": FSL.put_file(fd) }
    else:
        params["managers"] = {}
    params["score_type"] = ScoreTypes.SCORE_TYPE_SUM
    params["score_parameters"] = [],
    params["testcases"] = [ (FSL.put(os.path.join(path, "input", "input%d.txt" % (i)), "Input %d for task %s" % (i, name)),
                             FSL.put(os.path.join(path, "output", "output%d.txt" % (i)), "Output %d for task %s" % (i, name)))
                            for i in range(int(conf["n_input"]))]
    params["public_testcases"] = conf.get("risultati", "").split(",")
    if params["public_testcases"] == [""]:
        params["public_testcases"] = []
    params["public_testcases"] = [ int(x) for x in params["public_testcases"] ]
    params["token_initial"] = conf.get("token_initial", 0)
    params["token_max"] = conf.get("token_max", 0)
    params["token_total"] = conf.get("token_total", 0)
    params["token_min_interval"] = conf.get("token_min_interval", 0)
    params["token_gen_time"] = conf.get("token_gen_time", 60)

    for i in xrange(Configuration.maximum_conflict_attempts):
        try:
            if old_task == None:
                renewed_task = Task(**params)
            else:
                old_task.__dict__.update(params)
                renewed_task = old_task

            renewed_task.to_couch()
            return renewed_task
        except couchdb.ResourceConflict as e:
            old_task.refresh()
    else:
        raise couchdb.ResourceConflict()

if __name__ == "__main__":
    import sys
    c = Utils.ask_for_contest(1)
    c = reimport_contest(sys.argv[1], c)
    print "Couch ID: %s" % (c.couch_id)
