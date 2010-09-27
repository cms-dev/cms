#!/usr/bin/python
# -*- coding: utf-8 -*-

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape
import CouchObject
import Contest
import WebConfig
import xmlrpclib
import Configuration
from time import time

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
        for u in c.users:
            if u.username == self.get_secure_cookie("user"):
                return u
        else:
            return None

class MainHandler(BaseHandler):
    def get(self):
        self.render("welcome.html",title="Titolo",header="Header",description="Descrizione",contest=c )

class LoginHandler(BaseHandler):
    def post(self):
        username = self.get_argument("username","")
        password = self.get_argument("password","")
        for u in c.users:
            if u.username == username and u.password == password:
                self.set_secure_cookie("user",self.get_argument("username"))
                break
        self.redirect("/?login_error=true")

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")

class SubmissionViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,taskname):
        update_submissions()
        try:
            task = get_task(taskname)
        except:
            self.write("Task not found: "+taskname)
            return
        subm=[]
        for s in c.submissions:
            if s.user.username == self.current_user.username and s.task.name == task.name:
                subm.append(s)
        self.render("submission.html",submissions=subm, task = task)

class TaskViewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self,taskname):
        try:
            task = get_task(taskname)
        except:
            self.write("Task not found: "+taskname)
            return
            #raise tornado.web.HTTPError(404)
        self.render("task.html",task=task);
        
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
                    # avvisare Eval Server
                    try
                        es = xmlrpclib.ServerProxy("http://%s:%d"%Configuration.evaluation_server)
                        es.use_token(s.couch_id)
                    except:
                        pass
                    self.redirect("/submissions/"+s.task.name)
                    return
                else:
                    self.write("No tokens available.")
                    return
        else:
            raise tornado.web.HTTPError(404)            
        

handlers = [
            (r"/",MainHandler),
            (r"/login",LoginHandler),
            (r"/logout",LogoutHandler),
            (r"/submissions/([a-zA-Z0-9-]+)",SubmissionViewHandler),
            (r"/tasks/([a-zA-Z0-9-]+)",TaskViewHandler),
            (r"/usetoken/",UseTokenHandler),
           ]
                                       
application = tornado.web.Application( handlers, **WebConfig.parameters)

c = CouchObject.from_couch("sample_contest")

if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888);
    tornado.ioloop.IOLoop.instance().start()
