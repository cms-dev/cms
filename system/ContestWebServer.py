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

from time import time
from StringIO import StringIO

import Configuration
import WebConfig
import CouchObject
import Contest
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib


def get_task(taskname):
    for t in c.tasks:
        if t.name == taskname:
            return t
    else:
        raise KeyError("Task not found")

def token_available(user,task):
    return True

def update_submissions():
    for s in c.submissions:
        s.refresh()

def update_users():
    for u in c.users:
        u.refresh()

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        if self.get_secure_cookie("login") == None:
            return None
        try:
            username,cookie_time = pickle.loads(self.get_secure_cookie("login"))
        except:
            return None
        if cookie_time==None or cookie_time<upsince:
            return None
        for u in c.users:
            if u.username == username:
                return u
        else:
            return None

class MainHandler(BaseHandler):
    def get(self):
        self.render("welcome.html",contest=c , cookie = str(self.cookies))

class LoginHandler(BaseHandler):
    def post(self):
        username = self.get_argument("username","")
        password = self.get_argument("password","")
        for u in c.users:
            if u.username == username and u.password == password:
                self.set_secure_cookie("login",pickle.dumps( (self.get_argument("username"),time()) ))
                self.redirect("/")
                break
        else:
            self.redirect("/?login_error=true")

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")

class SubmissionViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, taskname):
        update_submissions()
        try:
            task = get_task(taskname)
        except:
            self.write("Task not found: " + taskname)
            return
        subm = []
        for s in c.submissions:
            if s.user.username == self.current_user.username and s.task.name == task.name:
                subm.append(s)
        self.render("submission.html",submissions=subm, task = task)

class TaskViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, taskname):
        try:
            task = get_task(taskname)
        except:
            self.write("Task not found: " + taskname)
            return
            #raise tornado.web.HTTPError(404)
        self.render("task.html",task=task);

class TaskStatementViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, taskname):
        try:
            task = get_task(taskname)
        except:
            self.write("Task not found: "+taskname)
        statementFile = StringIO()
        FSL = FileStorageLib()
        FSL.get_file(task.statement, statementFile)
        self.set_header("Content-Type", "application/pdf")
        self.set_header("Content-Disposition", "attachment; filename=\"%s.pdf\"" % (task.name))
        self.write(statementFile.getvalue())
        statementFile.close()

class UseTokenHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        update_submissions()
        u = self.get_current_user()
        if(u == None):
            raise tornado.web.HTTPError(403)

        if(self.get_arguments("id")==[]):
            raise tornado.web.HTTPError(404)
        ident = self.get_argument("id")
        for s in c.submissions:
            if s.couch_id == ident:
                #se utilizza già un token
                if s.token_timestamp != None:
                    self.write("This submission is already marked for detailed feedback.")
                # ha token disponibili?
                elif token_available(u,s.task):
                    s.token_timestamp = time()
                    u.tokens.append(s)
                    # salvataggio in couchdb
                    s.to_couch()
                    u.to_couch()
                    # avvisare Eval Server
                    try:
                        es = xmlrpclib.ServerProxy("http://%s:%d"%Configuration.evaluation_server)
                        es.use_token(s.couch_id)
                    except:
                        # FIXME - log
                        pass
                    self.redirect("/submissions/"+s.task.name)
                    return
                else:
                    self.write("No tokens available.")
                    return
        else:
            raise tornado.web.HTTPError(404)            

class SubmitHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, taskname):
        timestamp = time()
        uploaded = self.request.files[taskname][0]
        files = {}
        if uploaded["content_type"] == "application/zip":
            # TODO: unpack zip and save each file
            pass
        else:
            files[uploaded["filename"]] = uploaded["body"]
        task = get_task(taskname)
        if not task.valid_submission(files.keys()):
            raise tornado.web.HTTPError(404)
        for filename, content in files.items():
            tempFile, tempFilename = tempfile.mkstemp()
            tempFile = os.fdopen(tempFile, "w")
            tempFile.write(content)
            tempFile.close()
            files[filename] = FSL.put(tempFilename)
        s = Submission(self.current_user,
                       task,
                       timestamp,
                       files.values())
        ES.add_job(s.couch_id)

handlers = [
            (r"/",MainHandler),
            (r"/login",LoginHandler),
            (r"/logout",LogoutHandler),
            (r"/submissions/([a-zA-Z0-9-]+)",SubmissionViewHandler),
            (r"/tasks/([a-zA-Z0-9-]+)",TaskViewHandler),
            (r"/task_statement/([a-zA-Z0-9-]+)",TaskStatementViewHandler),
            (r"/usetoken/",UseTokenHandler),
            (r"/submit/([a-zA-Z0-9-]+)",SubmitHandler)
           ]

application = tornado.web.Application( handlers, **WebConfig.parameters)
FSL = FileStorageLib()
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

get_contests='''function(doc) {
    if (doc.document_type=='contest')
        emit(doc,null)
}'''

if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888);
    if len(sys.argv)>1:
        contestid=sys.argv[1]
    else:
        db = Utils.get_couchdb_database()
        print "Contests available:"
        for row in db.query(get_contests,include_docs=True):
            print "ID: " + row.id + " - Name: " + row.doc["name"]
        contestid=raw_input("Insert the contest ID:")
    try:
        c=CouchObject.from_couch(contestid)
    except couchdb.client.ResourceNotFound:
        print "Invalid contest ID"
        exit(1)
    print 'Contest "' + c.name + '" loaded.'
    upsince=time()
    tornado.ioloop.IOLoop.instance().start()
