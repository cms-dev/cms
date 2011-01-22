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


import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape

import couchdb
import datetime
import os
import pickle
import sys
import xmlrpclib
import time
 
import Configuration
import WebConfig
import CouchObject
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib
from Contest import Contest

class BaseHandler(tornado.web.RequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.
    """
    def get_current_user(self):
        """Gets the current user logged in from the cookies

        If a valid cookie is retrieved, returns a User object with the
        username specified in the cookie. Otherwise, returns None.
        """
        if self.get_secure_cookie("login") == None:
            return None
        try:
            username, cookie_time = pickle.loads(self.get_secure_cookie("login"))
        except:
            return None
        if cookie_time == None or cookie_time < upsince:
            return None
         #TODO: Use another user db...   
            
#        for u in c.users:
#            if u.username == username:
#                return u
#        else:
#            return None
        return None

class MainHandler(BaseHandler):
    """Home page handler.
    """
    def get(self):
        #Retrieve the contest list
        contests = Utils.get_contest_list()
        self.render("welcome.html", contests = contests, cookie = str(self.cookies))

class ContestViewHandler(BaseHandler):
    def get(self,contest_id):
      try:
        c = CouchObject.from_couch(contest_id)
      except couchdb.client.ResourceNotFound:
        self.write("Cannot load contest %s." % (contest_id))
        return
      self.render("contest.html", contest = c, cookie = str(self.cookies))
      
class EditContestHandler(BaseHandler):
    def post(self,contest_id):
        try:
          c = CouchObject.from_couch(contest_id)
        except couchdb.client.ResourceNotFound:
          self.write("Cannot load contest %s." % (contest_id))
        if self.get_arguments("name") == []:
          self.write("No contest name specified")
          return
        name = self.get_argument("name")
        description = self.get_argument("description","")
        
        try:
          token_initial = int(self.get_argument("token_initial","0"))
          token_max = int(self.get_argument("token_max","0"))
          token_total = int(self.get_argument("token_total","0"))
        except:
          self.write("Invalid token number field(s).")
          return;
        timearguments = ["_hour","_minute"]
        
        token_min_interval = int(self.get_argument("min_interval_hour","0")) * 60 + \
                             int(self.get_argument("min_interval_minute","0"))
        token_gen_time = int(self.get_argument("token_gen_hour","0")) * 60 + \
                             int(self.get_argument("token_gen_minute","0"))
        
        datetimearguments = ["_year","_month","_day","_hour","_minute"]
        try:
          start = datetime.datetime(*[int(self.get_argument("start"+x)) for x in datetimearguments] )
          end = datetime.datetime(*[int(self.get_argument("end"+x)) for x in datetimearguments] )
        except:
          self.write("Invalid date(s).")
          return
        if start > end :
          self.write("Contest ends before it starts")
          return
        c.name = name
        c.description = description
        c.token_initial = token_initial
        c.token_max = token_max
        c.token_total = token_total
        c.token_min_interval = token_min_interval
        c.token_gen_time = token_gen_time
        c.start = start
        c.stop = end
        try:
          c.to_couch()
        except:
          self.write("Contest storage in CouchDB failed!")
        self.redirect("/")
        return 

class AddContestHandler(BaseHandler):
    def get(self):
        self.render("addcontest.html", cookie = str(self.cookies))        
    def post(self):
        from Contest import Contest
        if self.get_arguments("name") == []:
          self.write("No contest name specified")
          return
        name = self.get_argument("name")
        description = self.get_argument("description","")
        
        try:
          token_initial = int(self.get_argument("token_initial","0"))
          token_max = int(self.get_argument("token_max","0"))
          token_total = int(self.get_argument("token_total","0"))
        except:
          self.write("Invalid token number field(s).")
          return;
        timearguments = ["_hour","_minute"]
        
        token_min_interval = int(self.get_argument("min_interval_hour","0")) * 60 + \
                             int(self.get_argument("min_interval_minute","0"))
        token_gen_time = int(self.get_argument("token_gen_hour","0")) * 60 + \
                             int(self.get_argument("token_gen_minute","0"))
        
        datetimearguments = ["_year","_month","_day","_hour","_minute"]
        try:
          time_start = time.mktime(time.strptime(" ".join([self.get_argument("start"+x,"0") for x in datetimearguments]) ,  "%Y %m %d %H %M")) 
          time_stop = time.mktime(time.strptime(" ".join([self.get_argument("end"+x,"0") for x in datetimearguments]) , "%Y %m %d %H %M" ))
        except Exception as e:
          self.write("Invalid date(s)." + repr(e))
          return
        if time_start > time_stop :
          self.write("Contest ends before it starts")
          return
        try:
          c = Contest(name,description,[],[],
                      token_initial, token_max, token_total, 
                      token_min_interval, token_gen_time,
                      start = time_start, stop = time_stop )
        except:
          self.write("Contest creation failed!")
          return
        if c == None:
          self.write("Contest creation failed!")
          return
        try:
          print c
          c.to_couch()
        except:
          self.write("Contest storage in CouchDB failed!")
        self.redirect("/")
        return 
        
handlers = [
            (r"/",MainHandler),
            (r"/addcontest",AddContestHandler),
            (r"/contest/([a-zA-Z0-9_-]+)",ContestViewHandler),
            (r"/contest/([a-zA-Z0-9_-]+)/edit",EditContestHandler)
           ]
           
admin_parameters={
            "login_url": "/" ,
            "template_path": "./templates/admin",
            "cookie_secret": "DsEwRxZER06etXcqgfowEJuM6rZjwk1JvknlbngmNck=",
            "static_path": os.path.join(os.path.dirname(__file__), "static"),
           }

application = tornado.web.Application( handlers, **admin_parameters)
FSL = FileStorageLib()
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

if __name__ == "__main__":
    Utils.set_service("administration web server")
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8889);

    Utils.log("Administration Web Server started...")
    upsince = time.time()
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        Utils.log("Administration Web Server stopped.")
