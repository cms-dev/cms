#!/usr/bin/python
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

"""
This source file handle the creation and the management of the Ranking
Web Server, that is the interface between the system and the outside
world. Typically, RWS shows the ranking (maybe with some problems
missing, or stopping an hour before the conclusion) without any
authentication requirement.
"""

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape

import couchdb
import os
import pickle
import sys
import tempfile
import xmlrpclib
import zipfile
import time
from StringIO import StringIO

import Configuration
import WebConfig
import CouchObject
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib


class BaseHandler(tornado.web.RequestHandler):
    """
    Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.
    """
    pass

class MainHandler(BaseHandler):
    """
    Home page handler.
    """
    def get(self):
        self.render("ranking.html", contest = c)

class TaskViewHandler(BaseHandler):
    """
    Shows the data and some stats of a task in the contest.
    """
    def get(self, task_name):
        try:
            task = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))
            return
        self.render("task_details.html", task = task, contest = c);

class TaskStatementViewHandler(BaseHandler):
    """
    Shows the statement file of a task in the contest.
    """
    def get(self, task_name):
        try:
            task = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))
        statement_file = StringIO()
        FSL = FileStorageLib()
        FSL.get_file(task.statement, statement_file)
        self.set_header("Content-Type", "application/pdf")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s.pdf\"" % (task.name))
        self.write(statement_file.getvalue())
        statement_file.close()

handlers = [
            (r"/", MainHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)", TaskViewHandler),
            (r"/task_statement/([a-zA-Z0-9_-]+)", TaskStatementViewHandler),
           ]

application = tornado.web.Application(handlers, **WebConfig.parameters)
FSL = FileStorageLib()

def update_ranking():
    Utils.log("Refreshing scores.")
    c.ranking_view.refresh()
    instance.add_timeout(time.time() + 5, update_ranking)

if __name__ == "__main__":
    Utils.set_service("ranking web server")
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(9999);
    c = Utils.ask_for_contest()
    Utils.log("Ranking Web Server for contest %s started..." % (c.couch_id))
    upsince = time.time()
    try:
        instance = tornado.ioloop.IOLoop.instance()
        instance.add_timeout(time.time() + 5, update_ranking)
        instance.start()
    except KeyboardInterrupt:
        Utils.log("Ranking Web Server for contest %s stopped." % (c.couch_id))
