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

"""Simple web service example.

"""

from functools import wraps
import os
import time

import tornado.web

from cms.async.AsyncLibrary import logger, rpc_callback
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord

from cms.db.SQLAlchemyAll import Base, Session, metadata, Contest, User, Announcement, Question, Submission, File

import cms.util.WebConfig as WebConfig
import cms.server.BusinessLayer as BusinessLayer

def contestRequired(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        if args[0].contest != None:
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

        self.sql_session = Session()
        self.contest = None
        # Retrieve the selected contest.
        selected_contest = self.get_argument("selected_contest",None)

        if selected_contest == "null":
          self.clear_cookie("selected_contest")
          self.redirect("/")
          return

        if selected_contest != None:
          self.contest = self.sql_session.query(Contest).filter_by(id=selected_contest).first()
          if self.contest != None:
            # If we're here, the selected contest exists. Set the cookie.
            self.set_secure_cookie("selected_contest", selected_contest)
            self.redirect("/contest")

        if self.contest == None:
          # No (valid) contest specified: either it was never specified,
          # or it was already specified in the cookies.
          cookie_contest = self.get_secure_cookie("selected_contest")
          if cookie_contest != None:
            self.contest = self.sql_session.query(Contest).filter_by(id=cookie_contest).first()
            if self.contest == None:
              self.clear_cookie("selected_contest")

    def render_params(self):
        r = {}
        r["timestamp"] = time.time()
        r["contest"] = self.contest
        if(self.contest != None):
          r["phase"] = BusinessLayer.contest_phase(**r)
        r["contest_list"] = self.sql_session.query(Contest).all()
        r["cookie"] = str(self.cookies)
        return r

    def finish(self, *args, **kwds):
        """ Finishes this response, ending the HTTP request.

        We override this method in order to properly close the database.
        """
        logger.debug("Closing SQL connection.")
        self.sql_session.close()
        tornado.web.RequestHandler.finish(self, *args, **kwds)

class FileHandler(BaseHandler):
    def fetch(self, digest, content_type, file_name):
        """Sends the RPC to the FS.

        """
        service = ServiceCoord("FileStorage", 0)
        if service not in self.application.service.remote_services or \
               not self.application.service.remote_services[service].connected:
            # TODO: Signal the user

            self.finish()
            return

        self.application.service.remote_services[service].get_file(\
            callback=self._fetch_callback,
            plus=[content_type, file_name],
            digest = digest)

    @rpc_callback
    def _fetch_callback(self, caller, data, plus, error=None):
        """This is the callback for the RPC method called from a web
        page, that just collects the response.

        """

        if data == None:
            self.finish()
            return

        (content_type, file_name) = plus

        self.set_header("Content-Type", content_type)
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s\"" % (file_name) )
        self.write(data)
        self.finish()

class AdminWebServer(WebService):
    """Simple web service example.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("AdminWebServer", shard))
        logger.debug("AdminWebServer.__init__")
        parameters = WebConfig.admin_parameters
        parameters["template_path"] = os.path.join(os.path.dirname(__file__),
                                  "templates", "admin")
        parameters["static_path"] = os.path.join(os.path.dirname(__file__),
                                  "static", "admin")
        WebService.__init__(self,
            WebConfig.admin_listen_port,
            handlers,
            parameters,
            shard=shard)
        self.FS = self.connect_to(ServiceCoord("FileStorage", 0))

class MainHandler(BaseHandler):
    """Home page handler.

    """
    def get(self):
        r_params = self.render_params()
        # TODO Worker status
        r_params["workers_status"] = None
        r_params["queue_status"] = None
        self.render("welcome.html", **r_params)

class ContestViewHandler(BaseHandler):
    @contestRequired
    def get(self):
        r_params = self.render_params()
        self.render("contest.html", **r_params)

class EditContestHandler(BaseHandler):
    def post(self, contest_id):

        # FIXME: Behave properly in the future...
        if self.contest == None or self.contest.id != int(contest_id):
          self.write("You changed the selected contest before editing this contest. To avoid unwanted changes, the request has been ignored.")
          return
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
        self.contest.name = name
        self.contest.description = description
        self.contest.token_initial = token_initial
        self.contest.token_max = token_max
        self.contest.token_total = token_total
        self.contest.token_min_interval = token_min_interval
        self.contest.token_gen_time = token_gen_time
        self.contest.start = start
        self.contest.stop = stop

        self.sql_session.commit()
        self.redirect("/contest")
        return

class AnnouncementsHandler(BaseHandler):
    @contestRequired
    def get(self):
        r_params = self.render_params()
        self.render("announcements.html", **r_params)

class AddAnnouncementHandler(BaseHandler):
    @contestRequired
    def post(self):
        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            ann = Announcement(time.time(), subject, text, self.contest)
            self.sql_session.add(ann)
            self.sql_session.commit()
            #BusinessLayer.add_announcement(self.c, subject, text)
        self.redirect("/announcements")

class RemoveAnnouncementHandler(BaseHandler):
    @contestRequired
    def post(self):
        ann_id = self.get_argument("id", "-1")
        ann = self.sql_session.query(Announcement).filter_by(id=ann_id).first()
        if ann == None:
            raise tornado.web.HTTPError(404)
        self.sql_session.delete(ann)
        self.sql_session.commit()
        self.redirect("/announcements")

class UserListHandler(BaseHandler):
    @contestRequired
    def get(self):
        r_params = self.render_params()
        self.render("userlist.html", **r_params)

class UserViewHandler(BaseHandler):
    @contestRequired
    def get(self, user_id):
        r_params = self.render_params()
        user = self.sql_session.query(User).filter_by(id=user_id).first()
        #user = BusinessLayer.get_user_by_username(self.c, user_id)
        #submissions = BusinessLayer.get_submissions_by_username(self.c, user_id)
        if user == None:
            raise tornado.web.HTTPError(404)
        r_params["selected_user"] = user
        # FIXME: Is tokens the list of submissions?
        r_params["submissions"] = user.tokens
        self.render("user.html", **r_params)

class SubmissionDetailHandler(BaseHandler):
    """Shows additional details for the specified submission.
    """
    @contestRequired
    def get(self, submission_id):

        r_params = self.render_params()

        # search the submission in the contest
        submission = Submission.get_from_id(submission_id, self.sql_session)

        if submission == None:
            raise tornado.web.HTTPError(404)
        r_params["submission"] = submission
        r_params["task"] = submission.task
        self.render("submission_detail.html", **r_params)

class SubmissionFileHandler(FileHandler):
    """Shows a submission file.
    """

    @tornado.web.asynchronous
    def get(self, file_id):

        sub_file = self.sql_session.query(File)\
                       .filter(File.id == file_id)\
                       .first()

        if sub_file == None:
            raise tornado.web.HTTPError(404)

        self.fetch(sub_file.digest, "text/plain", sub_file.filename)

class QuestionReplyHandler(BaseHandler):
    @contestRequired
    def post(self, question_id):

        r_params = self.render_params()

        q = self.sql_session.query(Question).filter_by(id=question_id).first()
        if q == None :
          raise tornado.web.HTTPError(404)

        q.short_reply = self.get_argument("reply_question_quick_answer","")
        q.long_reply = self.get_argument("reply_question_text", "")

        # Ignore invalid answers
        if q.short_reply not in WebConfig.quick_answers:
            q.short_reply = None

        q.reply_timestamp = time.time()

        self.sql_session.commit()

        logger.warning("Reply sent to user %s for question '%s'."
                  % (q.user.username, q.subject))
        r_params["selected_user"] = q.user
        self.render("successfulMessage.html", **r_params)

handlers = [
            (r"/", \
                 MainHandler),
            (r"/announcements", \
                 AnnouncementsHandler),
#            (r"/addcontest", \
#                 AddContestHandler),
            (r"/contest", \
                 ContestViewHandler),
            (r"/contest/edit/([0-9]+)", \
                 EditContestHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)", \
                 SubmissionDetailHandler),
#            (r"/reevaluate/submission/([a-zA-Z0-9_-]+)", \
#                 SubmissionReevaluateHandler),
#            (r"/reevaluate/user/([a-zA-Z0-9_-]+)", \
#                 UserReevaluateHandler),
            (r"/add_announcement", \
                 AddAnnouncementHandler),
            (r"/remove_announcement", \
                 RemoveAnnouncementHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)", \
                 SubmissionFileHandler),
            (r"/user/([a-zA-Z0-9_-]+)", \
                 UserViewHandler),
            (r"/user", \
                 UserListHandler),
#            (r"/message/([a-zA-Z0-9_-]+)", \
#                 MessageHandler),
            (r"/question/([a-zA-Z0-9_-]+)", \
                 QuestionReplyHandler),
           ]

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        AdminWebServer(int(sys.argv[1])).run()

