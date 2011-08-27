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

"""Web server for administration of contests.

"""

import os
import time

import tornado.web

from cms.async.AsyncLibrary import logger, rpc_callback
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord

from cms.db.SQLAlchemyAll import Session, \
     Contest, User, Announcement, Question, Message, Submission, File, Task

import cms.util.WebConfig as WebConfig
from cms.server.Utils import file_handler_gen


class BaseHandler(tornado.web.RequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """

    def retrieve_contest(self, contest_id):
        """Retrieve the contest with the specified id.

        Raise tornado.web.HTTPError(404) if the contest doesn't exist.

        """
        self.contest = Contest.get_from_id(contest_id, self.sql_session)
        if self.contest is None:
            raise tornado.web.HTTPError(404)

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        # Attempt to update the contest and all its references
        # If this fails, the request terminates.
        self.set_header("Cache-Control", "no-cache, must-revalidate")

        self.sql_session = Session()
        self.contest = None

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        r = {}
        r["timestamp"] = time.time()
        r["contest"] = self.contest
        if self.contest is not None:
            r["phase"] = self.contest.phase(r["timestamp"])
        r["contest_list"] = self.sql_session.query(Contest).all()
        r["cookie"] = str(self.cookies)
        return r

    def finish(self, *args, **kwds):
        """ Finish this response, ending the HTTP request.

        We override this method in order to properly close the database.

        """
        logger.debug("Closing SQL connection.")
        self.sql_session.close()
        tornado.web.RequestHandler.finish(self, *args, **kwds)

    def get_non_negative_int(self,argument_name, default):
        """ Get a non-negative integer from the arguments, or use the default if
        the argument is missing.

        Raise TypeError if the argument can't be converted into a non-negative
        integer.

        """
        argument = self.get_argument(argument_name, repr(default))
        argument = int(argument)
        if argument < 0:
            raise TypeError, argument_name + " is negative."
        return argument

FileHandler = file_handler_gen(BaseHandler)


class AdminWebServer(WebService):
    """Service that runs the web server serving the managers.

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
        self.ES = self.connect_to(ServiceCoord("EvaluationServer", 0))


class MainHandler(BaseHandler):
    """Home page handler, with queue and workers statuses.

    """

    def get(self, contest_id = None):
        if contest_id:
            self.retrieve_contest(contest_id)
        self.render("welcome.html", **self.render_params())

class ContestViewHandler(BaseHandler):
    """Shows information about a specific contest.

    """
    def get(self, contest_id):
        self.retrieve_contest(contest_id)
        r_params = self.render_params()
        self.render("contest.html", **r_params)

class TaskViewHandler(BaseHandler):


    def get(self, task_id):
        task = Task.get_from_id(task_id, self.sql_session)
        if task is None:
            raise tornado.web.HTTPError(404)
        self.contest = task.contest
        r_params = self.render_params()
        r_params["task"] = task
        self.render("task.html", **r_params)

    @tornado.web.asynchronous
    def post(self, task_id):
        self.task = Task.get_from_id(task_id, self.sql_session)
        if self.task is None:
            raise tornado.web.HTTPError(404)
        self.task.name = self.get_argument("name", self.task.name)
        self.task.title = self.get_argument("title", self.task.title)

        time_limit = self.get_argument("time_limit", repr(self.task.time_limit))
        try:
            time_limit = float(time_limit)
            if time_limit < 0 or time_limit > "+inf":
                raise TypeError, "Time limit out of range."
        except TypeError as e:
            self.write("Invalid time limit.")
            self.finish()
            return
        self.task.time_limit = time_limit

        try:
            self.task.memory_limit = self.get_non_negative_int("memory_limit", self.task.memory_limit)
            if self.task.memory_limit == 0:
                raise TypeError, "Memory limit is 0."
            self.task.token_initial = self.get_non_negative_int("token_initial", self.task.token_initial)
            self.task.token_max = self.get_non_negative_int("token_max", self.task.token_max)
            self.task.token_total = self.get_non_negative_int("token_total", self.task.token_total)
            self.task.token_min_interval = self.get_non_negative_int("token_min_interval", self.task.token_min_interval)
            self.task.token_gen_time = self.get_non_negative_int("token_gen_time", self.task.token_gen_time)
            self.task.token_gen_number = self.get_non_negative_int("token_gen_number", self.task.token_gen_number)
        except TypeError as e:
            self.write("Invalid fields: " + repr(e))
            self.finish()
            return

        try:
            for testcase in self.task.testcases:
                testcase.public = self.get_argument("testcase_" + str(testcase.num) + "_public", False) != False
        except TypeError as e:
            self.write("Invalid public testcase field." + repr(e))
            self.finish()
            return

        self.sql_session.commit()
        self.redirect("/task/" + str(self.task.id))

class EditContestHandler(BaseHandler):
    """Called when managers edit the information of a contest.

    """
    def post(self, contest_id):
        self.retrieve_contest(contest_id)

        name = self.get_argument("name", "")
        if name == "":
            self.write("No contest name specified")
            return

        description = self.get_argument("description", "")

        try:
            token_initial = self.get_non_negative_int("token_initial", self.contest.token_initial)
            token_max = self.get_non_negative_int("token_max", self.contest.token_max)
            token_total = self.get_non_negative_int("token_total", self.contest.token_total)
            token_min_interval = self.get_non_negative_int("token_min_interval", self.contest.token_min_interval)
            token_gen_time = self.get_non_negative_int("token_gen_time", self.contest.token_gen_time)
        except:
            self.write("Invalid token field(s): "+ repr(e))
            return


        try:
            start = time.mktime(time.strptime(self.get_argument("start", ""),
                                              "%d/%m/%Y %H:%M:%S"))
            stop = time.mktime(time.strptime(self.get_argument("end", ""),
                                             "%d/%m/%Y %H:%M:%S"))
        except Exception as e:
            self.write("Invalid date(s)." + repr(e))
            return

        if start > stop:
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
        self.redirect("/contest/"+contest_id)


class AnnouncementsHandler(BaseHandler):
    """Page to see and send messages to all the contestants.

    """
    def get(self, contest_id):
        self.retrieve_contest(contest_id)
        r_params = self.render_params()
        self.render("announcements.html", **r_params)


class AddAnnouncementHandler(BaseHandler):
    """Called to actually add an announcement

    """
    def post(self, contest_id):
        self.retrieve_contest(contest_id)
        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            ann = Announcement(time.time(), subject, text, self.contest)
            self.sql_session.add(ann)
            self.sql_session.commit()
        self.redirect("/announcements/"+contest_id)


class RemoveAnnouncementHandler(BaseHandler):
    """Called to remove an announcement.

    """
    def get(self, ann_id):
        ann = Announcement.get_from_id(ann_id,self.sql_session)
        if ann == None:
            raise tornado.web.HTTPError(404)
        contest_id = str(ann.contest.id)
        self.sql_session.delete(ann)
        self.sql_session.commit()
        self.redirect("/announcements/" + contest_id)


class UserListHandler(BaseHandler):
    """Shows the list of users participating in a contest.

    """
    def get(self, contest_id):
        self.retrieve_contest(contest_id)
        r_params = self.render_params()
        self.render("userlist.html", **r_params)


class UserViewHandler(BaseHandler):
    """Shows the details of a single user (submissions, questions,
    messages, and allows to send the latters).

    """
    def get(self, user_id):

        user = User.get_from_id(user_id, self.sql_session)
        if user == None:
            raise tornado.web.HTTPError(404)
        self.contest = user.contest
        r_params = self.render_params()
        r_params["selected_user"] = user
        r_params["submissions"] = user.submissions
        self.render("user.html", **r_params)


class SubmissionDetailHandler(BaseHandler):
    """Shows additional details for the specified submission.

    """
    def get(self, submission_id):

        # search the submission in the contest
        submission = Submission.get_from_id(submission_id, self.sql_session)

        if submission == None:
            raise tornado.web.HTTPError(404)

        # Submissions are associated to the user and to the task. We use the
        # task to get the contest.
        self.contest = submission.task.contest

        r_params = self.render_params()
        r_params["submission"] = submission
        r_params["task"] = submission.task
        self.render("submission_detail.html", **r_params)


class SubmissionFileHandler(FileHandler):
    """Shows a submission file.

    """

    # FIXME: Replace with FileFromDigestHandler?

    @tornado.web.asynchronous
    def get(self, file_id):

        sub_file = File.get_from_id(file_id, sql_session)

        if sub_file == None:
            raise tornado.web.HTTPError(404)

        self.fetch(sub_file.digest, "text/plain", sub_file.filename)


class QuestionReplyHandler(BaseHandler):
    """Called when the manager replies to a question made by a user.

    """
    def post(self, question_id):


        question = Question.get_from_id(question_id,self.sql_session)
        if question == None:
            raise tornado.web.HTTPError(404)

        question.short_reply = self.get_argument("reply_question_quick_answer",
                                                 "")
        question.long_reply = self.get_argument("reply_question_text", "")

        # Ignore invalid answers
        if question.short_reply not in WebConfig.quick_answers:
            question.short_reply = None

        question.reply_timestamp = time.time()

        self.sql_session.commit()

        logger.warning("Reply sent to user %s for question '%s'." %
                       (question.user.username, question.subject))

        self.redirect("/user/"+str(question.user.id))


class MessageHandler(BaseHandler):
    """Called when a message is sent to a specific user.

    """

    def post(self, user_id):
        r_params = self.render_params()

        user = User.get_from_id(user_id, self.sql_session)
        if user is None:
            raise tornado.web.HTTPError(404)

        message = Message(time.time(),
                            self.get_argument("message_subject", ""),
                            self.get_argument("message_text", ""),
                            user=user)
        self.sql_session.add(message)
        self.sql_session.commit()

        logger.warning("Message submitted to user %s."
                       % user)

        self.redirect("/user/" + user_id)

class SubmissionReevaluateHandler(BaseHandler):
    """Ask ES to reevaluate the specific submission.

    """

    @tornado.web.asynchronous
    def get(self, submission_id):

        submission = Submission.get_from_id(submission_id, self.sql_session)
        if submission == None:
            raise tornado.web.HTTPError(404)

        self.submission = submission
        self.contest = submission.task.contest

        submission.invalid()
        self.sql_session.commit()
        self.application.service.ES.new_submission(
            submission_id=submission.id,
            callback=self.es_notify_callback)

    @rpc_callback
    def es_notify_callback(self, data, plus, error=None):
        if error == None:
            self.redirect("/user/"+str(self.submission.user.id))
        else:
            logger.error("Notification to ES failed: %s." % repr(error))
            self.finish()

class UserReevaluateHandler(BaseHandler):

    @tornado.web.asynchronous
    def get(self, user_id):
        self.user_id = user_id
        user = User.get_from_id(user_id, self.sql_session)
        if user == None:
            raise tornado.web.HTTPError(404)

        self.contest = user.contest

        self.pending_requests = len(user.submissions)
        for s in user.submissions:
            s.invalid()
            self.sql_session.commit()
            if not self.application.service.ES.new_submission(
                submission_id=s.id,
                callback=self.es_notify_callback):
                self.es_notify_callback(None, None, error="Not connected")

    @rpc_callback
    def es_notify_callback(self, data, plus, error=None):
        self.pending_requests -= 1
        if self.pending_requests <= 0:
            self.redirect("/user/" + self.user_id)

class FileFromDigestHandler(FileHandler):

    @tornado.web.asynchronous
    def get(self, digest, filename):
        #TODO: Accept a MIME type
        self.fetch(digest, "text/plain", filename)

handlers = [(r"/",
             MainHandler),
            (r"/([0-9]+)",
             MainHandler),
            (r"/announcements/([0-9]+)",
             AnnouncementsHandler),
            # (r"/addcontest",
            #  AddContestHandler),
            (r"/contest/([0-9]+)",
             ContestViewHandler),
            (r"/contest/edit/([0-9]+)",
             EditContestHandler),
            (r"/file/([a-f0-9]+)/([a-zA-Z0-9_.-]+)",
             FileFromDigestHandler),
            (r"/task/([0-9]+)",
             TaskViewHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)",
             SubmissionDetailHandler),
            (r"/reevaluate/submission/([a-zA-Z0-9_-]+)",
             SubmissionReevaluateHandler),
            (r"/reevaluate/user/([0-9]+)",
             UserReevaluateHandler),
            (r"/add_announcement/([0-9]+)",
             AddAnnouncementHandler),
            (r"/remove_announcement/([0-9]+)",
             RemoveAnnouncementHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)",
             SubmissionFileHandler),
            (r"/user/([a-zA-Z0-9_-]+)",
             UserViewHandler),
            (r"/userlist/([0-9]+)",
             UserListHandler),
            (r"/message/([a-zA-Z0-9_-]+)",
             MessageHandler),
            (r"/question/([a-zA-Z0-9_-]+)",
             QuestionReplyHandler),
           ]

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        AdminWebServer(int(sys.argv[1])).run()
