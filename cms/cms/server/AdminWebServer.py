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

import os
import pickle
import xmlrpclib
import time

import BusinessLayer
import cms.util.Configuration as Configuration
import cms.util.WebConfig as WebConfig
import cms.util.Utils

from functools import wraps

def contestRequired(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        if args[0].c != None:
          return f(*args, **kwds)
        else:
          raise tornado.web.HTTPError(404)
    return wrapper


class BaseHandler(tornado.web.RequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.
    """

    def prepare(self):
        """This method is executed at the beginning of each request.
        """
        # Attempt to update the contest and all its references
        # If this fails, the request terminates.
        self.set_header("Cache-Control", "no-cache, must-revalidate")
        
        self.c = None
        # Retrieve the selected contest.
        selected_contest = self.get_argument("selected_contest",None)
        
        if selected_contest == "null":
          self.clear_cookie("selected_contest")
          self.redirect("/")
          return

        if selected_contest != None:
          try:
            # TODO: Change retrieval mode
            self.c = CouchObject.from_couch(selected_contest, True)
            if self.c != None:
              # If we're here, the selected contest exists. Set the cookie.
              self.set_secure_cookie("selected_contest", selected_contest)
              self.redirect("/contest")
          except couchdb.client.ResourceNotFound:
            # The selected contest isn't valid.
            pass
          except Exception as e:
            Utils.log("CouchDB exception:" + repr(e),
                      Utils.Logger.SEVERITY_CRITICAL)
            self.write("Can't connect to CouchDB Server")
            self.finish()
            return
        if self.c == None:
          # No (valid) contest specified: either it was never specified,
          # or it was already specified in the cookies.
          cookie_contest = self.get_secure_cookie("selected_contest")
          if cookie_contest != None:
            try:
            # TODO: Change retrieval mode
              self.c = CouchObject.from_couch(cookie_contest, True)
            except couchdb.client.ResourceNotFound:
              # The contest is invalid. Unset the cookie.
              print "Unset cookie."
              self.clear_cookie("selected_contest")
              self.c = None
            except Exception as e:
              Utils.log("CouchDB exception:" + repr(e),
                        Utils.Logger.SEVERITY_CRITICAL)
              self.write("Can't connect to CouchDB Server")
              self.finish()
              return


    def get_current_user(self):
        """Gets the current user logged in from the cookies

        If a valid cookie is retrieved, returns a User object with the
        username specified in the cookie. Otherwise, returns None.
        """
        if self.get_secure_cookie("login") == None:
            return None
        try:
            username, cookie_time = \
                pickle.loads(self.get_secure_cookie("login"))
        except:
            return None
        if cookie_time == None or cookie_time < upsince:
            return None
        return BusinessLayer.get_user_by_username(c, username)

    def render_params(self):
        r = {}
        r["timestamp"] = time.time()
        r["contest"] = self.c
        if(self.c != None):
          r["phase"] = BusinessLayer.contest_phase(**r)
        r["contest_list"] = Utils.get_contest_list()
        r["cookie"] = str(self.cookies)
        return r

    def valid_phase(self, r_param):
        if r_param["phase"] != 0:
            self.redirect("/")
            return False
        return True


class MainHandler(BaseHandler):
    """Home page handler.
    """

    def get(self):
        # Retrieve the contest list
        r_params = self.render_params()
        try:
            r_params["workers_status"] = BusinessLayer.get_workers_status()
        except Exception as e:
            Utils.log("Worker status unavailable: %s" % e,
                      Utils.logger.SEVERITY_IMPORTANT)
            r_params["workers_status"] = None
        try:
            r_params["queue_status"] = BusinessLayer.get_queue_status()
        except Exception as e:
            Utils.log("Queue status unavailable: %s" % e,
                      Utils.logger.SEVERITY_IMPORTANT)
            r_params["queue_status"] = None
        self.render("welcome.html", **r_params)


class ContestViewHandler(BaseHandler):
    @contestRequired
    def get(self):
        r_params = self.render_params()
        self.render("contest.html", **r_params)

class AnnouncementsHandler(BaseHandler):
    @contestRequired
    def get(self):
        r_params = self.render_params()
        self.render("announcements.html", **r_params)

class SubmissionReevaluateHandler(BaseHandler):
    """Re-evaluate the specified submission and go back to the details
    of the user.
    """
    @contestRequired
    def get(self, submission_id):
        # search the submission in the contest
        s = BusinessLayer.get_submission(self.c, submission_id)
        if s == None:
            raise tornado.web.HTTPError(404)
        BusinessLayer.reevaluate_submission(s)
        self.redirect("/user/%s" % s.user.username)


class UserReevaluateHandler(BaseHandler):
    """Re-evaluate the submissions of the specified user and go back
    to the details of the user.
    """
    @contestRequired
    def get(self, user_id):
        BusinessLayer.update_users(self.c)
        BusinessLayer.update_submissions(self.c)
        u = BusinessLayer.get_user_by_username(self.c, user_id)
        if u == None:
            raise tornado.web.HTTPError(404)
        submissions = BusinessLayer.get_submissions_by_username(self.c, user_id)
        for submission in submissions:
            BusinessLayer.reevaluate_submission(submission)
        self.redirect("/user/%s" % user_id)


class EditContestHandler(BaseHandler):
    def post(self):

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
          return
        timearguments = ["_hour","_minute"]

        token_min_interval = \
            int(self.get_argument("min_interval_hour","0")) * 60 + \
            int(self.get_argument("min_interval_minute","0"))
        token_gen_time = int(self.get_argument("token_gen_hour","0")) * 60 + \
                             int(self.get_argument("token_gen_minute","0"))

        datetimearguments = ["_year","_month","_day","_hour","_minute"]
        try:
          start = time.mktime(time.strptime(
                  self.get_argument("start",""),
                  "%d/%m/%Y %H:%M:%S" ))
          stop = time.mktime(time.strptime(
                  self.get_argument("end",""),
                  "%d/%m/%Y %H:%M:%S" ))
        except Exception as e:
          self.write("Invalid date(s)." + repr(e))
          return
        if start > stop :
          self.write("Contest ends before it starts")
          return
        self.c.name = name
        self.c.description = description
        self.c.token_initial = token_initial
        self.c.token_max = token_max
        self.c.token_total = token_total
        self.c.token_min_interval = token_min_interval
        self.c.token_gen_time = token_gen_time
        self.c.start = start
        self.c.stop = stop
        # FIXME - Shouldn't just fail if to_couch() fails; instead, it
        # should update the document and try again
        try:
          self.c.to_couch()
        except:
          self.write("Contest storage in CouchDB failed!")
          return
        self.redirect("/contest")
        return

class AddContestHandler(BaseHandler):
    def get(self):
        r_params = self.render_params()
        self.render("addcontest.html",**r_params)
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
          return
        timearguments = ["_hour","_minute"]

        token_min_interval = \
            int(self.get_argument("min_interval_hour","0")) * 60 + \
            int(self.get_argument("min_interval_minute","0"))
        token_gen_time = int(self.get_argument("token_gen_hour","0")) * 60 + \
                             int(self.get_argument("token_gen_minute","0"))

        datetimearguments = ["_year","_month","_day","_hour","_minute"]
        try:
          time_start = time.mktime(time.strptime(
                  self.get_argument("start",""),
                  "%d/%m/%Y %H:%M:%S" ))
          time_stop = time.mktime(time.strptime(
                  self.get_argument("end",""),
                  "%d/%m/%Y %H:%M:%S" ))
        except Exception as e:
          self.write("Invalid date(s)." + repr(e))
          return
        if time_start > time_stop :
          self.write("Contest ends before it starts")
          return
        
        c = BusinessLayer.add_contest(name,description,[],[],
                      token_initial, token_max, token_total,
                      token_min_interval, token_gen_time,
                      start = time_start, stop = time_stop )
        if c == None:
          self.write("Contest creation failed!")
          return
        self.set_secure_cookie("selected_contest", c.couch_id)
        self.redirect("/contest")
        return


class SubmissionDetailHandler(BaseHandler):
    """Shows additional details for the specified submission.
    """
    @contestRequired
    def get(self, submission_id):
        BusinessLayer.update_submissions(self.c)
        r_params = self.render_params()

        # search the submission in the contest
        s = BusinessLayer.get_submission(self.c, submission_id)
        if s == None:
            raise tornado.web.HTTPError(404)
        r_params["submission"] = s
        r_params["task"] = s.task
        self.render("submission_detail.html", **r_params)


class SubmissionFileHandler(BaseHandler):
    """Shows a submission file.
    """
    @contestRequired
    def get(self, submission_id, filename):
        submission = BusinessLayer.get_submission(self.c, submission_id)
        # search the submission in the contest
        file_content = BusinessLayer.get_file_from_submission(submission,
                                                              filename)
        if file_content == None:
            raise tornado.web.HTTPError(404)

        # FIXME - Set the right headers
        self.set_header("Content-Type", "text/plain")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s-%s\"" %
                        (submission.couch_id, filename))
        self.write(file_content)


class AddAnnouncementHandler(BaseHandler):
    @contestRequired
    def post(self):
        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            BusinessLayer.add_announcement(self.c, subject, text)
        self.redirect("/announcements")


class RemoveAnnouncementHandler(BaseHandler):
    @contestRequired
    def post(self):
        index = self.get_argument("index", "-1")
        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        try:
            index = int(index)
            announcement = self.c.announcements[index]
        except:
            raise tornado.web.HTTPError(404)
        if announcement['subject'] == subject and \
                announcement['text'] == text:
            BusinessLayer.remove_announcement(self.c, index)
        self.redirect("/announcements")


class UserViewHandler(BaseHandler):
    @contestRequired
    def get(self, user_id):
        BusinessLayer.update_users(self.c)
        BusinessLayer.update_submissions(self.c)
        r_params = self.render_params()
        user = BusinessLayer.get_user_by_username(self.c, user_id)
        submissions = BusinessLayer.get_submissions_by_username(self.c, user_id)
        if user == None:
            raise tornado.web.HTTPError(404)

        r_params["selected_user"] = user
        r_params["submissions"] = submissions
        self.render("user.html", **r_params)


class UserListHandler(BaseHandler):
    @contestRequired
    def get(self):
        BusinessLayer.update_users(self.c)
        r_params = self.render_params()
        self.render("userlist.html", **r_params)


class MessageHandler(BaseHandler):
    @contestRequired
    def post(self, user_name):
        BusinessLayer.update_users(self.c)
        r_params = self.render_params()

        user = BusinessLayer.get_user_by_username(self.c, user_name)
        if user == None:
            raise tornado.web.HTTPError(404)
        r_params["selected_user"] = user

        message_subject = self.get_argument("send_message_subject", "")
        message_quick_answer = self.get_argument("send_message_quick_answer",
                                                 "")
        message_text = self.get_argument("send_message_text", "")

        # Ignore invalid answers
        if message_quick_answer not in WebConfig.quick_answers:
            message_quick_answer = None

        # Abort if the subject is empty
        if message_subject == "":
            self.redirect("/user/%s?notext=true" % user_name)
            return

        BusinessLayer.add_user_message(user, time.time(), \
                message_subject, message_quick_answer, message_text)
        Utils.log("Message submitted to user %s." % user_name,
                  Utils.logger.SEVERITY_NORMAL)
        self.render("successfulMessage.html", **r_params)


class QuestionReplyHandler(BaseHandler):
    @contestRequired
    def post(self, user_name):
        BusinessLayer.update_users(self.c)
        r_params = self.render_params()

        user = BusinessLayer.get_user_by_username(self.c, user_name)
        if user == None:
            raise tornado.web.HTTPError(404)
        r_params["selected_user"] = user

        message_index = self.get_argument("reply_question_index", None)
        message_quick_answer = self.get_argument("reply_question_quick_answer",
                                                 "")
        message_text = self.get_argument("reply_question_text", "")

        if message_index == None:
            raise tornado.web.HTTPError(404)
        message_index = int(message_index)

        # Ignore invalid answers
        if message_quick_answer not in WebConfig.quick_answers:
            message_quick_answer = None

        BusinessLayer.reply_question(user, message_index, time.time(), \
                 message_quick_answer, message_text)
        Utils.log("Reply sent to user %s for question '%s'."
                  % (user_name, user.questions[message_index]["subject"]),
                  Utils.logger.SEVERITY_NORMAL)
        self.render("successfulMessage.html", **r_params)

handlers = [
            (r"/", \
                 MainHandler),
            (r"/announcements", \
                 AnnouncementsHandler),
            (r"/addcontest", \
                 AddContestHandler),
            (r"/contest", \
                 ContestViewHandler),
            (r"/contest/edit", \
                 EditContestHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)", \
                 SubmissionDetailHandler),
            (r"/reevaluate/submission/([a-zA-Z0-9_-]+)", \
                 SubmissionReevaluateHandler),
            (r"/reevaluate/user/([a-zA-Z0-9_-]+)", \
                 UserReevaluateHandler),
            (r"/add_announcement", \
                 AddAnnouncementHandler),
            (r"/remove_announcement", \
                 RemoveAnnouncementHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", \
                 SubmissionFileHandler),
            (r"/user/([a-zA-Z0-9_-]+)", \
                 UserViewHandler),
            (r"/user", \
                 UserListHandler),
            (r"/message/([a-zA-Z0-9_-]+)", \
                 MessageHandler),
            (r"/question/([a-zA-Z0-9_-]+)", \
                 QuestionReplyHandler),
           ]

application = tornado.web.Application(handlers, **WebConfig.admin_parameters)
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

if __name__ == "__main__":
    Utils.set_service("administration web server")
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(WebConfig.admin_listen_port)

    Utils.log("Administration Web Server started...")

    upsince = time.time()
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        Utils.log("Administration Web Server stopped.")
