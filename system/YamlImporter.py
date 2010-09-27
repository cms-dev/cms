#!/usr/lib/python
# -*- coding: utf-8 -*-

import yaml
import os
import sys
from Task import Task
import FileStorageLib

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
    params["token_num"] = conf.get("token_num", 0)
    params["token_min_interval"] = conf.get("token_min_interval", 0)
    params["token_gen_time"] = conf.get("token_gen_time", 0)
    params["users"] = []
    for user in conf["utenti"]:
        params["user"].append(import_user(user))
    params["start"] = conf["inizio"]
    params["stop"] = conf["fine"]

    return Contest(**params)

def import_user(user_dict):
    params = {}
    params["username"] = user["username"]
    params["password"] = user["password"]
    params["name"] = " ".join(user["nome"], user["cognome"])
    params["hidden"] = user["fake"]
    params["tokens"] = []

    return User(**uparams)

def import_task(path):
    path = os.path.realpath(path)
    super_path, name = os.path.split(path)
    conf = yaml.load(open(os.path.join(super_path, name + ".yaml")))
    FSL = FileStorageLib.FileStorageLib()

    params = {"name": name}
    assert name == conf["nome_breve"]
    params["title"] = conf["nome"]
    params["time_limit"] = conf["timeout"]
    params["memory_limit"] = conf["memlimit"]
    params["attachments"] = [] # FIXME - Use auxiliary
    params["statement"] = FSL.put(os.path.join(path, "testo", "testo.pdf"), "PDF statement for task %s" % (name))
    params["task_type"] = Task.TASK_TYPE_BATCH
    params["submission_format"] = ["%s.%%l" % (name)]
    params["managers"] = [] # FIXME - Add managers
    params["score_type"] = Task.SCORE_TYPE_SUM
    params["score_parameters"] = [],
    params["testcases"] = [ (FSL.put(os.path.join(path, "input", "input%d.txt" % (i)), "Input %d for task %s" % (i, name)),
                             FSL.put(os.path.join(path, "output", "output%d.txt" % (i)), "Output %d for task %s" % (i, name)))
                            for i in range(int(conf["n_input"]))]
    params["public_testcases"] = [ 0 ]
    params["token_num"] = conf.get("token_num", 0)
    params["token_min_interval"] = conf.get("token_min_interval", 0)
    params["token_gen_time"] = conf.get("token_gen_time", 0)

    return Task(**params)

if __name__ == "__main__":
    import sys
    c = import_contest(sys.argv[1])
    print "Couch ID: %s" % (c.couch_id)
