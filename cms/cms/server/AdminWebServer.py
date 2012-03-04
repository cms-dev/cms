#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import base64
import simplejson as json
import tornado.web
import tornado.locale

from cms import config, default_argument_parser, logger
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord, get_service_shards, get_service_address
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import Session, \
     Contest, User, Announcement, Question, Message, Submission, File, Task, \
     Attachment, Manager, Testcase, SubmissionFormatElement
from cms.grading.tasktypes import get_task_type
from cms.server import file_handler_gen, catch_exceptions


def valid_ip(ip_address):
    """Return True if ip_address is a valid IPv4 address.

    ip_address (string): the ip to validate.

    return (bool): True iff valid.

    """
    fields = ip_address.split(".")
    if len(fields) != 4:
        return
    for field in fields:
        try:
            num = int(field)
        except ValueError:
            return False
        if num < 0 or num >= 256:
            return False
    return True


class BaseHandler(tornado.web.RequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """

    def safe_get_item(self, cls, ident, session=None):
        """Get item from database of class cls and id ident, using
        session if given, or self.sql_session if not given. If id is
        not found, raise a 404.

        cls (class): class of object to retrieve.
        ident (string): id of object.
        session (session/None): session to use.

        return (object/404): the object with the given id, or 404.

        """
        if session is None:
            session = self.sql_session
        entity = cls.get_from_id(ident, session)
        if entity is None:
            raise tornado.web.HTTPError(404)
        return entity

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        # Attempt to update the contest and all its references
        # If this fails, the request terminates.
        self.set_header("Cache-Control", "no-cache, must-revalidate")

        self.sql_session = Session()
        self.sql_session.expire_all()
        self.contest = None

        localization_dir = os.path.join(os.path.dirname(__file__), "mo")
        if os.path.exists(localization_dir):
            tornado.locale.load_gettext_translations(localization_dir, "cms")

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        params = {}
        params["timestamp"] = int(time.time())
        params["contest"] = self.contest
        if self.contest is not None:
            params["phase"] = self.contest.phase(params["timestamp"])
            # Keep "== None" in filter arguments
            params["unanswered"] = self.sql_session.query(Question)\
                .join(User)\
                .filter(User.contest_id == self.contest.id)\
                .filter(Question.reply_timestamp == None)\
                .filter(Question.ignored == False)\
                .count()
        params["contest_list"] = self.sql_session.query(Contest).all()
        params["cookie"] = str(self.cookies)
        return params

    def finish(self, *args, **kwds):
        """ Finish this response, ending the HTTP request.

        We override this method in order to properly close the database.

        """
        logger.debug("Closing SQL connection.")
        self.sql_session.close()
        tornado.web.RequestHandler.finish(self, *args, **kwds)

    def get_non_negative_int(self, argument_name, default, allow_empty=True):
        """ Get a non-negative integer from the arguments.

        Use default if the argument is missing; If allow_empty=False,
        Empty values such as "" and None are not permitted.

        Raise ValueError if the argument can't be converted into a
        non-negative integer.

        """
        argument = self.get_argument(argument_name, repr(default))
        if allow_empty and \
               (argument is None or argument == "" or argument == "None"):
            return None
        try:
            argument = int(argument)
        except:
            raise ValueError("%s: can't cast %s to int." %
                             (argument_name, argument))
        if argument < 0:
            raise ValueError("%s is negative." % argument_name)
        return argument


FileHandler = file_handler_gen(BaseHandler)


class AdminWebServer(WebService):
    """Service that runs the web server serving the managers.

    """

    QUICK_ANSWERS = {
        "yes": "Yes",
        "no": "No",
        "answered": "Answered in task description",
        "invalid": "Invalid question",
        "nocomment": "No comment",
        }

    def __init__(self, shard):
        logger.initialize(ServiceCoord("AdminWebServer", shard))

        # A list of pending notifications.
        self.notifications = []

        parameters = {
            "login_url": "/",
            "template_path": os.path.join(os.path.dirname(__file__),
                                          "templates", "admin"),
            "static_path": os.path.join(os.path.dirname(__file__),
                                        "static"),
            "cookie_secret": base64.b64encode(config.secret_key),
            "debug": config.tornado_debug,
            }
        WebService.__init__(self,
                            config.admin_listen_port,
                            _aws_handlers,
                            parameters,
                            shard=shard,
                            custom_logger=logger)
        self.FC = FileCacher(self)
        self.ES = self.connect_to(ServiceCoord("EvaluationService", 0))
        self.RS = []
        for i in xrange(get_service_shards("ResourceService")):
            self.RS.append(self.connect_to(ServiceCoord("ResourceService", i)))
        self.logservice = self.connect_to(ServiceCoord("LogService", 0))

    @staticmethod
    def authorized_rpc(service, method, arguments):
        """Used by WebService to check if the browser can call a
        certain RPC method.

        service (ServiceCoord): the service called by the browser.
        method (string): the name of the method called.
        arguments (dict): the arguments of the call.
        return (bool): True if ok, False if not authorized.

        """
        if service == ServiceCoord("EvaluationService", 0):
            return method in ["submissions_status",
                              "queue_status",
                              "workers_status"]

        elif service == ServiceCoord("LogService", 0):
            return method in ["last_messages"]

        elif service.name == "ResourceService":
            return method in ["get_resources",
                              "kill_service",
                              "toggle_autorestart"]

        # Default fallback: don't authorize.
        return False

    def add_notification(self, timestamp, subject, text):
        """Store a new notification to send at the first
        opportunity (i.e., at the first request for db notifications).

        timestamp (int): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.

        """
        self.notifications.append((timestamp, subject, text))


class MainHandler(BaseHandler):
    """Home page handler, with queue and workers statuses.

    """

    def get(self, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)

        r_params = self.render_params()
        self.render("welcome.html", **r_params)


def SimpleContestHandler(page):
    class Cls(BaseHandler):
        def get(self, contest_id):
            self.contest = self.safe_get_item(Contest, contest_id)
            r_params = self.render_params()
            self.render(page, **r_params)
    return Cls


class ResourcesHandler(BaseHandler):
    def get(self, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)

        r_params = self.render_params()
        r_params["resource_shards"] = get_service_shards("ResourceService")
        r_params["resource_addresses"] = {}
        for i in xrange(r_params["resource_shards"]):
            r_params["resource_addresses"][i] = get_service_address(
                ServiceCoord("ResourceService", i)).ip

        self.render("resources.html", **r_params)


class AddContestHandler(BaseHandler):
    """Adds a new contest.

    """
    def get(self):
        r_params = self.render_params()
        self.render("add_contest.html", **r_params)

    def post(self):
        name = self.get_argument("name", "")
        if name == "":
            self.write("No contest name specified")
            return

        description = self.get_argument("description", None)

        try:
            token_initial = self.get_non_negative_int(
                "token_initial",
                0,
                allow_empty=False)
            token_max = self.get_non_negative_int(
                "token_max",
                None)
            token_total = self.get_non_negative_int(
                "token_total",
                None)
            token_min_interval = self.get_non_negative_int(
                "token_min_interval",
                None)
            token_gen_time = self.get_non_negative_int(
                "token_gen_time",
                None)
            token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                None)
        except Exception as error:
            self.write("Invalid token field(s). %r" % error)
            return

        try:
            start = time.mktime(time.strptime(self.get_argument("start", ""),
                                              "%d/%m/%Y %H:%M:%S"))
            stop = time.mktime(time.strptime(self.get_argument("end", ""),
                                             "%d/%m/%Y %H:%M:%S"))
        except Exception as error:
            self.write("Invalid date(s). %r" % error)
            return

        if start > stop:
            self.write("Contest ends before it starts")
            return

        try:
            per_user_time = self.get_non_negative_int(
                "per_user_time",
                None)
        except Exception as error:
            self.write("Invalid per user time. %r" % error)
            return

        contest = Contest(name, description, [], [], token_initial,
                          token_max, token_total, token_min_interval,
                          token_gen_time, token_gen_number, start, stop,
                          per_user_time)

        self.sql_session.add(contest)
        self.sql_session.commit()
        self.write(str(contest.id))


class AddStatementHandler(BaseHandler):
    """Add a statement to a task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        r_params = self.render_params()
        r_params["task"] = task
        self.render("add_statement.html", **r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        statement = self.request.files["statement"][0]
        if not statement["filename"].endswith(".pdf"):
            self.application.service.add_notification(int(time.time()),
                "Invalid task statement",
                "The task statement must be a .pdf file.")
            self.redirect("/add_statement/%s" % task_id)
            return
        task_name = task.name
        self.sql_session.close()

        try:
            digest = self.application.service.FC.put_file(
                binary_data=statement["body"],
                description="Task statement for %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(int(time.time()),
                "Task statement storage failed",
                repr(error))
            self.redirect("/add_statement/%s" % task_id)
            return

        self.sql_session = Session()
        task = self.safe_get_item(Task, task_id)
        task.statement = digest
        self.sql_session.commit()
        self.redirect("/task/%s" % task_id)


class AddAttachmentHandler(BaseHandler):
    """Add an attachment to a task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        r_params = self.render_params()
        r_params["task"] = task
        self.render("add_attachment.html", **r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        attachment = self.request.files["attachment"][0]
        task_name = task.name
        self.sql_session.close()

        try:
            digest = self.application.service.FC.put_file(
                binary_data=attachment["body"],
                description="Task attachment for %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(int(time.time()),
                "Attachment storage failed",
                repr(error))
            self.redirect("/add_attachment/%s" % task_id)
            return

        self.sql_session = Session()
        task = self.safe_get_item(Task, task_id)
        self.sql_session.add(Attachment(digest, attachment["filename"], task))
        self.sql_session.commit()
        self.redirect("/task/%s" % task_id)


class DeleteAttachmentHandler(BaseHandler):
    """Delete an attachment.

    """
    def get(self, attachment_id):
        attachment = self.safe_get_item(Attachment, attachment_id)
        task = attachment.task
        self.sql_session.delete(attachment)
        self.sql_session.commit()
        self.redirect("/task/%s" % task.id)


class AddManagerHandler(BaseHandler):
    """Add a manager to a task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        r_params = self.render_params()
        r_params["task"] = task
        self.render("add_manager.html", **r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        manager = self.request.files["manager"][0]
        task_name = task.name
        self.sql_session.close()

        try:
            digest = self.application.service.FC.put_file(
                binary_data=manager["body"],
                description="Task manager for %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(int(time.time()),
                "Manager storage failed",
                repr(error))
            self.redirect("/add_manager/%s" % task_id)
            return

        self.sql_session = Session()
        task = self.safe_get_item(Task, task_id)
        self.sql_session.add(Manager(digest, manager["filename"], task))
        self.sql_session.commit()
        self.redirect("/task/%s" % task_id)


class DeleteManagerHandler(BaseHandler):
    """Delete a manager.

    """
    def get(self, manager_id):
        manager = self.safe_get_item(Manager, manager_id)
        task = manager.task
        self.contest = task
        self.sql_session.delete(manager)
        self.sql_session.commit()
        self.redirect("/task/%s" % task.id)


class AddTestcaseHandler(BaseHandler):
    """Add a testcase to a task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        r_params = self.render_params()
        r_params["task"] = task
        self.render("add_testcase.html", **r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        _input = self.request.files["input"][0]
        output = self.request.files["output"][0]
        public = self.get_argument("public", None) is not None
        task_name = task.name
        self.sql_session.close()

        try:
            input_digest = self.application.service.FC.put_file(
                binary_data=_input["body"],
                description="Testcase input for task %s" % task_name)
            output_digest = self.application.service.FC.put_file(
                binary_data=output["body"],
                description="Testcase output for task %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(int(time.time()),
                "Testcase storage failed",
                repr(error))
            self.redirect("/add_testcase/%s" % task_id)
            return

        self.sql_session = Session()
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        self.sql_session.add(Testcase(
            input_digest, output_digest, len(task.testcases), public, task))
        self.sql_session.commit()
        self.redirect("/task/%s" % task_id)


class DeleteTestcaseHandler(BaseHandler):
    """Delete a testcase.

    """
    def get(self, testcase_id):
        testcase = self.safe_get_item(Testcase, testcase_id)
        task = testcase.task
        self.contest = task.contest
        self.sql_session.delete(testcase)
        self.sql_session.commit()
        self.redirect("/task/%s" % task.id)


class TaskViewHandler(BaseHandler):
    """Task handler, with a POST method to edit the task.

    """
    @catch_exceptions
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        r_params = self.render_params()
        r_params["task"] = task
        r_params["submissions"] = self.sql_session.query(Submission)\
                                  .join(Task).filter(Task.id == task_id)\
                                  .order_by(Submission.timestamp.desc())
        self.render("task.html", **r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest
        task.name = self.get_argument("name", task.name)
        task.title = self.get_argument("title", task.title)
        time_limit = self.get_argument("time_limit",
                                       repr(task.time_limit))
        try:
            time_limit = float(time_limit)
            if time_limit < 0 or time_limit >= float("+inf"):
                raise TypeError("Time limit out of range.")
        except TypeError as error:
            self.write("Invalid time limit.")
            self.finish()
            return
        task.time_limit = time_limit

        try:
            task.memory_limit = self.get_non_negative_int(
                "memory_limit",
                task.memory_limit,
                allow_empty=False)
            if task.memory_limit == 0:
                raise ValueError("Memory limit is 0.")
            task.token_initial = self.get_non_negative_int(
                "token_initial",
                task.token_initial,
                allow_empty=False)
            task.token_max = self.get_non_negative_int(
                "token_max",
                task.token_max)
            task.token_total = self.get_non_negative_int(
                "token_total",
                task.token_total)
            task.token_min_interval = self.get_non_negative_int(
                "token_min_interval",
                task.token_min_interval)
            task.token_gen_time = self.get_non_negative_int(
                "token_gen_time",
                task.token_gen_time)
            task.token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                task.token_gen_number)
        except ValueError as error:
            self.write("Invalid fields. %r" % error)
            self.finish()
            return

        for testcase in task.testcases:
            testcase.public = bool(self.get_argument("testcase_%s_public" %
                                                     testcase.num, False))

        task.task_type = self.get_argument("task_type", "")

        # Look for a task type with the specified name.
        try:
            task_type_class = get_task_type(task=task)
        except KeyError:
            # Task type not found.
            self.application.service.add_notification(
                int(time.time()),
                "Invalid field",
                "Task type not recognized: %s." % task.task_type)
            self.redirect("/task/%s" % task_id)
            return

        task_type_parameters = task_type_class.parse_handler(
            self, "TaskTypeOptions_%s_" % task.task_type)

        task.task_type_parameters = json.dumps(task_type_parameters)

        task.score_type = self.get_argument("score_type", "")

        task.score_parameters = self.get_argument("score_parameters", "")

        submission_format = self.get_argument("submission_format", "")
        if submission_format not in ["", "[]"] \
            and submission_format != json.dumps(
                [x.filename for x in task.submission_format]
                ):
            try:
                format_list = json.loads(submission_format)
                for element in task.submission_format:
                    self.sql_session.delete(element)
                del task.submission_format[:]
                for element in format_list:
                    self.sql_session.add(SubmissionFormatElement(str(element),
                                                                 task))
            except Exception as error:
                self.sql_session.rollback()
                logger.info(repr(error))
                self.application.service.add_notification(int(time.time()),
                "Invalid field",
                "Submission format not recognized.")
                self.redirect("/task/%s" % task_id)
                return

        self.sql_session.commit()
        self.redirect("/task/%s" % task_id)


class TaskStatementViewHandler(FileHandler):
    """Shows the statement file of a task in the contest.

    """
    @tornado.web.asynchronous
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        statement = task.statement
        task_name = task.name
        self.sql_session.close()
        self.fetch(statement, "application/pdf", "%s.pdf" % task_name)


class AddTaskHandler(SimpleContestHandler("add_task.html")):
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        name = self.get_argument("name", "")
        title = self.get_argument("title", "")
        time_limit = self.get_argument("time_limit", "")
        memory_limit = self.get_argument("memory_limit", "")
        task_type = self.get_argument("task_type", "")

        # Look for a task type with the specified name.
        try:
            task_type_class = get_task_type(task_type_name=task_type)
        except KeyError:
            # Task type not found.
            self.application.service.add_notification(
                int(time.time()),
                "Invalid field",
                "Task type not recognized: %s." % task_type)
            self.redirect("/add_task/%s" % contest_id)
            return

        task_type_parameters = task_type_class.parse_handler(
            self, "TaskTypeOptions_%s_" % task_type)

        task_type_parameters = json.dumps(task_type_parameters)

        submission_format_choice = self.get_argument("submission_format", "")

        if submission_format_choice == "simple":
            submission_format = [SubmissionFormatElement("%s.%%l" % name)]
        elif submission_format_choice == "other":
            submission_format = self.get_argument("submission_format_other",
                                                  "")
            if submission_format not in ["", "[]"]:
                try:
                    format_list = json.loads(submission_format)
                    submission_format = []
                    for element in format_list:
                        submission_format.append(SubmissionFormatElement(
                            str(element)))
                except Exception as error:
                    self.sql_session.rollback()
                    logger.info(repr(error))
                    self.application.service.add_notification(int(time.time()),
                    "Invalid field",
                    "Submission format not recognized.")
                    self.redirect("/add_task/%s" % contest_id)
                    return
        else:
            self.application.service.add_notification(int(time.time()),
                "Invalid field",
                "Submission format not recognized.")
            self.redirect("/add_task/%s" % contest_id)
            return

        score_type = self.get_argument("score_type", "")
        score_parameters = self.get_argument("score_parameters", "")

        attachments = {}
        statement = ""
        managers = {}
        testcases = []

        token_initial = self.get_non_negative_int(
            "token_initial",
            None,
            allow_empty=False)
        token_max = self.get_non_negative_int(
            "token_max",
            None)
        token_total = self.get_non_negative_int(
            "token_total",
            None)
        token_min_interval = self.get_non_negative_int(
            "token_min_interval",
            None)
        token_gen_time = self.get_non_negative_int(
            "token_gen_time",
            None)
        token_gen_number = self.get_non_negative_int(
            "token_gen_number",
            None)
        task = Task(name, title, attachments, statement,
                 time_limit, memory_limit,
                 task_type, task_type_parameters, submission_format, managers,
                 score_type, score_parameters, testcases,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time, token_gen_number,
                 contest=self.contest, num=len(self.contest.tasks))
        self.sql_session.add(task)
        self.sql_session.commit()
        self.redirect("/task/%s" % task.id)


class EditContestHandler(BaseHandler):
    """Called when managers edit the information of a contest.

    """
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        name = self.get_argument("name", "")
        if name == "":
            self.application.service.add_notification(int(time.time()),
                "No contest name specified", "")
            self.redirect("/contest/%s" % contest_id)
            return

        description = self.get_argument("description", None)

        try:
            token_initial = self.get_non_negative_int(
                "token_initial",
                self.contest.token_initial,
                allow_empty=False)
            token_max = self.get_non_negative_int(
                "token_max",
                self.contest.token_max,
                allow_empty=True)
            token_total = self.get_non_negative_int(
                "token_total",
                self.contest.token_total)
            token_min_interval = self.get_non_negative_int(
                "token_min_interval",
                self.contest.token_min_interval)
            token_gen_time = self.get_non_negative_int(
                "token_gen_time",
                self.contest.token_gen_time)
            token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                self.contest.token_gen_number)
        except Exception as error:
            self.application.service.add_notification(int(time.time()),
                "Invalid token field(s).", repr(error))
            self.redirect("/contest/%s" % contest_id)
            return

        try:
            start = time.mktime(time.strptime(self.get_argument("start", ""),
                                              "%d/%m/%Y %H:%M:%S"))
            stop = time.mktime(time.strptime(self.get_argument("end", ""),
                                             "%d/%m/%Y %H:%M:%S"))
        except Exception as error:
            self.application.service.add_notification(int(time.time()),
                "Invalid date(s).", repr(error))
            self.redirect("/contest/%s" % contest_id)
            return

        if start > stop:
            self.application.service.add_notification(
                int(time.time()),
                "Contest ends before it starts",
                "Please check start and stop times.")
            self.redirect("/contest/%s" % contest_id)
            return

        try:
            per_user_time = self.get_non_negative_int(
                "per_user_time",
                None)
        except Exception as error:
            self.write("Invalid per user time. %r" % error)
            self.redirect("/contest/%s" % contest_id)
            return

        self.contest.name = name
        self.contest.description = description
        self.contest.token_initial = token_initial
        self.contest.token_max = token_max
        self.contest.token_total = token_total
        self.contest.token_min_interval = token_min_interval
        self.contest.token_gen_time = token_gen_time
        self.contest.token_gen_number = token_gen_number
        self.contest.start = start
        self.contest.stop = stop
        self.contest.per_user_time = per_user_time

        self.sql_session.commit()
        self.redirect("/contest/%s" % contest_id)


class AddAnnouncementHandler(BaseHandler):
    """Called to actually add an announcement

    """
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            ann = Announcement(int(time.time()), subject, text, self.contest)
            self.sql_session.add(ann)
            self.sql_session.commit()
        self.redirect("/announcements/%s" % contest_id)


class RemoveAnnouncementHandler(BaseHandler):
    """Called to remove an announcement.

    """
    def get(self, ann_id):
        ann = self.safe_get_item(Announcement, ann_id)
        contest_id = ann.contest.id
        self.sql_session.delete(ann)
        self.sql_session.commit()
        self.redirect("/announcements/%s" % contest_id)


class UserViewHandler(BaseHandler):
    """Shows the details of a single user (submissions, questions,
    messages), and allows to send the latters.

    """
    def get(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest
        r_params = self.render_params()
        r_params["selected_user"] = user
        r_params["submissions"] = user.submissions
        self.render("user.html", **r_params)

    def post(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest
        user.first_name = self.get_argument("first_name", user.first_name)
        user.last_name = self.get_argument("last_name", user.last_name)
        username = self.get_argument("username", user.username)

        # Prevent duplicate usernames in the contest.
        for u in self.contest.users:
            if u.username != user.username and u.username == username:
                self.application.service.add_notification(int(time.time()),
                    "Duplicate username",
                    "The requested username already exists in the contest.")
                self.redirect("/user/%s" % user_id)
                return
        user.username = username

        user.password = self.get_argument("password", user.password)
        user.email = self.get_argument("email", user.email)

        user.ip = self.get_argument("ip", user.ip)
        if not valid_ip(user.ip):
            self.application.service.add_notification(
                int(time.time()), "Invalid ip", "")
            self.redirect("/user/%s" % user_id)
            return

        starting_time = None
        if self.get_argument("starting_time", "") not in ["", "None"]:
            try:
                starting_time = time.mktime(
                    time.strptime(self.get_argument("starting_time", ""),
                                  "%d/%m/%Y %H:%M:%S"))
            except Exception as error:
                self.application.service.add_notification(
                    int(time.time()),
                    "Invalid starting time(s).", repr(error))
                self.redirect("/user/%s" % user_id)
                return
        user.starting_time = starting_time

        user.hidden = bool(self.get_argument("hidden", False))

        self.sql_session.commit()
        self.application.service.add_notification(int(time.time()),
            "User updated successfully.", "")
        self.redirect("/user/%s" % user_id)


class AddUserHandler(SimpleContestHandler("add_user.html")):
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        first_name = self.get_argument("first_name", "")
        last_name = self.get_argument("last_name", "")
        username = self.get_argument("username", "")

        # Prevent duplicate usernames in the contest.
        for u in self.contest.users:
            if u.username == username:
                self.application.service.add_notification(int(time.time()),
                    "Duplicate username",
                    "The requested username already exists in the contest.")
                self.redirect("/add_user/%s" % contest_id)
                return

        password = self.get_argument("password", "")
        email = self.get_argument("email", "")

        ip = self.get_argument("ip", "0.0.0.0")
        if not valid_ip(ip):
            self.application.service.add_notification(
                int(time.time()), "Invalid ip", "")
            self.redirect("/add_user/%s" % contest_id)
            return

        starting_time = None
        if self.get_argument("starting_time", "") not in ["", "None"]:
            try:
                starting_time = time.mktime(
                    time.strptime(self.get_argument("starting_time", ""),
                                  "%d/%m/%Y %H:%M:%S"))
            except Exception as error:
                self.application.service.add_notification(
                    int(time.time()),
                    "Invalid starting time(s).", repr(error))
                self.redirect("/add_user/%s" % contest_id)
                return

        hidden = bool(self.get_argument("hidden", False))

        user = User(first_name, last_name, username, password=password,
                    email=email, ip=ip, hidden=hidden,
                    starting_time=starting_time, contest=self.contest)
        self.sql_session.add(user)
        self.sql_session.commit()
        self.application.service.add_notification(int(time.time()),
            "User added successfully.",
            "")
        self.redirect("/user/%s" % user.id)


class SubmissionViewHandler(BaseHandler):
    """Shows the details of a submission. All data is already present
    in the list of the submissions of the task or of the user, but we
    need a place where to link messages like 'Submission 42 failed to
    compile please check'.

    """
    def get(self, submission_id):
        submission = self.safe_get_item(Submission, submission_id)
        self.contest = submission.user.contest
        r_params = self.render_params()
        r_params["s"] = submission
        self.render("submission.html", **r_params)


class SubmissionFileHandler(FileHandler):
    """Shows a submission file.

    """
    # FIXME: Replace with FileFromDigestHandler?
    @tornado.web.asynchronous
    def get(self, file_id):
        sub_file = self.safe_get_item(File, file_id)
        submission = sub_file.submission
        self.contest = submission.task.contest
        real_filename = sub_file.filename
        if submission.language is not None:
            real_filename = real_filename.replace("%l", submission.language)
        digest = sub_file.digest
        self.sql_session.close()
        self.fetch(digest, "text/plain", real_filename)


class QuestionsHandler(BaseHandler):
    """Page to see and send messages to all the contestants.

    """
    def get(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        r_params = self.render_params()
        r_params["questions"] = self.sql_session.query(Question)\
            .join(User).filter(User.contest_id == contest_id)\
            .order_by(Question.question_timestamp.desc())\
            .order_by(Question.id).all()
        self.render("questions.html", **r_params)


class QuestionReplyHandler(BaseHandler):
    """Called when the manager replies to a question made by a user.

    """
    def post(self, question_id):
        ref = self.get_argument("ref", "/")
        question = self.safe_get_item(Question, question_id)
        self.contest = question.user.contest
        reply_subject_code = self.get_argument("reply_question_quick_answer",
                                               "")
        question.reply_text = self.get_argument("reply_question_text", "")

        # Ignore invalid answers
        if reply_subject_code not in AdminWebServer.QUICK_ANSWERS:
            question.reply_subject = ""
        else:
            # Quick answer given, ignore long answer.
            question.reply_subject = \
                AdminWebServer.QUICK_ANSWERS[reply_subject_code]
            question.reply_text = ""

        question.reply_timestamp = int(time.time())

        self.sql_session.commit()

        logger.warning("Reply sent to user %s for question '%s'." %
                       (question.user.username, question.subject))

        self.redirect(ref)


class QuestionIgnoreHandler(BaseHandler):
    """Called when the manager chooses to ignore or stop ignoring a
    question.

    """
    def post(self, question_id):
        ref = self.get_argument("ref", "/")

        # Fetch form data.
        question = self.safe_get_item(Question, question_id)
        self.contest = question.user.contest
        should_ignore = self.get_argument("ignore", "no") == "yes"

        # Commit the change.
        question.ignored = should_ignore
        self.sql_session.commit()

        logger.warning("Question '%s' by user %s %s" %
                (question.subject, question.user.username,
                    ["ignored", "unignored"][should_ignore]))

        self.redirect(ref)


class MessageHandler(BaseHandler):
    """Called when a message is sent to a specific user.

    """

    def post(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest

        message = Message(int(time.time()),
                          self.get_argument("message_subject", ""),
                          self.get_argument("message_text", ""),
                          user=user)
        self.sql_session.add(message)
        self.sql_session.commit()

        logger.warning("Message submitted to user %s."
                       % user.username)

        self.redirect("/user/%s" % user_id)


class SubmissionReevaluateHandler(BaseHandler):
    """Ask ES to reevaluate the specific submission.

    """

    def get(self, submission_id):
        submission = self.safe_get_item(Submission, submission_id)
        self.submission = submission
        self.contest = submission.task.contest

        submission.invalid()
        self.sql_session.commit()
        self.application.service.ES.new_submission(submission_id=submission.id)
        self.redirect("/submission/%s" % submission_id)


class UserReevaluateHandler(BaseHandler):

    def get(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest

        self.pending_requests = len(user.submissions)
        for s in user.submissions:
            s.invalid()
            self.sql_session.commit()
            self.application.service.ES.new_submission(submission_id=s.id)

        self.redirect("/user/%s" % user_id)


class TaskReevaluateHandler(BaseHandler):

    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        self.pending_requests = len(task.submissions)
        for s in task.submissions:
            s.invalid()
            self.sql_session.commit()
            self.application.service.ES.new_submission(submission_id=s.id)

        self.redirect("/task/%s" % task_id)


class FileFromDigestHandler(FileHandler):

    @tornado.web.asynchronous
    def get(self, digest, filename):
        #TODO: Accept a MIME type
        self.sql_session.close()
        self.fetch(digest, "text/plain", filename)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """
    def get(self):
        res = []
        last_notification = float(self.get_argument("last_notification", "0"))

        # Keep "== None" in filter arguments
        questions = self.sql_session.query(Question)\
            .filter(Question.reply_timestamp == None)\
            .filter(Question.question_timestamp > last_notification)\
            .all()

        for question in questions:
            res.append({"type": "new_question",
                        "timestamp": question.question_timestamp,
                        "subject": question.subject,
                        "text": question.text})

        # Simple notifications
        for notification in self.application.service.notifications:
            res.append({"type": "notification",
                        "timestamp": notification[0],
                        "subject": notification[1],
                        "text": notification[2]})
        self.application.service.notifications = []

        self.write(json.dumps(res))


_aws_handlers = [
    (r"/",         MainHandler),
    (r"/([0-9]+)", MainHandler),
    (r"/contest/([0-9]+)",       SimpleContestHandler("contest.html")),
    (r"/announcements/([0-9]+)", SimpleContestHandler("announcements.html")),
    (r"/userlist/([0-9]+)",      SimpleContestHandler("userlist.html")),
    (r"/tasklist/([0-9]+)",      SimpleContestHandler("tasklist.html")),
    (r"/contest/add",           AddContestHandler),
    (r"/contest/edit/([0-9]+)", EditContestHandler),
    (r"/task/([0-9]+)",           TaskViewHandler),
    (r"/task/([0-9]+)/statement", TaskStatementViewHandler),
    (r"/add_task/([0-9]+)",            AddTaskHandler),
    (r"/add_statement/([0-9]+)",       AddStatementHandler),
    (r"/add_attachment/([0-9]+)",      AddAttachmentHandler),
    (r"/delete_attachment/([0-9]+)",   DeleteAttachmentHandler),
    (r"/add_manager/([0-9]+)",         AddManagerHandler),
    (r"/delete_manager/([0-9]+)",      DeleteManagerHandler),
    (r"/add_testcase/([0-9]+)",        AddTestcaseHandler),
    (r"/delete_testcase/([0-9]+)",     DeleteTestcaseHandler),
    (r"/user/([a-zA-Z0-9_-]+)",   UserViewHandler),
    (r"/add_user/([0-9]+)",       AddUserHandler),
    (r"/reevaluate/task/([0-9]+)",               TaskReevaluateHandler),
    (r"/reevaluate/user/([0-9]+)",               UserReevaluateHandler),
    (r"/reevaluate/submission/([a-zA-Z0-9_-]+)", SubmissionReevaluateHandler),
    (r"/add_announcement/([0-9]+)",    AddAnnouncementHandler),
    (r"/remove_announcement/([0-9]+)", RemoveAnnouncementHandler),
    (r"/submission/([0-9]+)",                SubmissionViewHandler),
    (r"/submission_file/([a-zA-Z0-9_.-]+)",  SubmissionFileHandler),
    (r"/file/([a-f0-9]+)/([a-zA-Z0-9_.-]+)", FileFromDigestHandler),
    (r"/message/([a-zA-Z0-9_-]+)", MessageHandler),
    (r"/question/([a-zA-Z0-9_-]+)",        QuestionReplyHandler),
    (r"/ignore_question/([a-zA-Z0-9_-]+)", QuestionIgnoreHandler),
    (r"/questions/([0-9]+)",               QuestionsHandler),
    (r"/resources",                 ResourcesHandler),
    (r"/resources/([0-9]+)",        ResourcesHandler),
    (r"/notifications",             NotificationsHandler),
    ]


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Admins' web server for CMS.",
                            AdminWebServer).run()

if __name__ == "__main__":
    main()
