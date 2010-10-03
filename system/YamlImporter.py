#!/usr/lib/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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
from FileStorageLib import FileStorageLib

def import_contest(path):
    path = os.path.realpath(path)
    super_path, name = os.path.split(path)
    conf = yaml.load(open(os.path.join(path,"contest.yaml")))

    params = {"name": name}
    assert name == conf["nome_breve"]
    params["description"] = conf["nome"]
    params["tasks"] = []
    for task in conf["problemi"]:
        params["tasks"].append(import_task(os.path.join(path, task)))
    params["token_initial"] = conf.get("token_initial", 0)
    params["token_max"] = conf.get("token_max", 0)
    params["token_total"] = conf.get("token_total", 0)
    params["token_min_interval"] = conf.get("token_min_interval", 0)
    params["token_gen_time"] = conf.get("token_gen_time", 1)
    params["users"] = []
    for user in conf["utenti"]:
        params["users"].append(import_user(user))
    params["start"] = conf["inizio"]
    params["stop"] = conf["fine"]

    return Contest(**params)

def import_user(user_dict):
    params = {}
    params["username"] = user_dict["username"]
    params["password"] = user_dict["password"]
    name = user_dict.get("nome", "")
    surname = user_dict.get("cognome", user_dict["username"])
    params["real_name"] = " ".join([name, surname])
    params["ip"] = user_dict.get("ip", "0.0.0.0")
    params["hidden"] = user_dict.get("fake", False)
    params["tokens"] = []

    return User(**params)

def import_task(path):
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
    params["score_type"] = Task.SCORE_TYPE_SUM
    params["score_parameters"] = [],
    params["testcases"] = [ (FSL.put(os.path.join(path, "input", "input%d.txt" % (i)), "Input %d for task %s" % (i, name)),
                             FSL.put(os.path.join(path, "output", "output%d.txt" % (i)), "Output %d for task %s" % (i, name)))
                            for i in range(int(conf["n_input"]))]
    params["public_testcases"] = [ 0 ]
    params["token_initial"] = conf.get("token_initial", 0)
    params["token_max"] = conf.get("token_max", 0)
    params["token_total"] = conf.get("token_total", 0)
    params["token_min_interval"] = conf.get("token_min_interval", 0)
    params["token_gen_time"] = conf.get("token_gen_time", 60)

    return Task(**params)

if __name__ == "__main__":
    import sys
    c = import_contest(sys.argv[1])
    print "Couch ID: %s" % (c.couch_id)
