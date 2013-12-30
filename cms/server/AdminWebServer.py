#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import base64
import json
import logging
import os
import pkg_resources
import re
import traceback
from datetime import datetime, timedelta

from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

import tornado.web
import tornado.locale

from cms import config
from cms.log import initialize_logging
from cms.io.WebGeventLibrary import WebService
from cms.io import ServiceCoord, get_service_shards, get_service_address
from cms.db import Session, Contest, User, Announcement, Question, Message, \
    Submission, SubmissionResult, File, Task, Dataset, Attachment, Manager, \
    Testcase, SubmissionFormatElement, Statement
from cms.db.filecacher import FileCacher
from cms.grading import compute_changes_for_dataset
from cms.grading.tasktypes import get_task_type_class
from cms.server import file_handler_gen, get_url_root, \
    CommonRequestHandler
from cmscommon.datetime import make_datetime, make_timestamp


logger = logging.getLogger(__name__)


def try_commit(session, handler):
    """Try to commit the session, if not successful display a warning
    in the webpage.

    session (Session): the session to commit.
    handler (BaseHandler): just to extract the information about AWS.

    return (bool): True if commit was successful, False otherwise.

    """
    try:
        session.commit()
    except IntegrityError as error:
        handler.application.service.add_notification(
            make_datetime(),
            "Operation failed.", str(error))
        return False
    else:
        handler.application.service.add_notification(
            make_datetime(),
            "Operation successful.", "")
        return True


def valid_ip(ip_address):
    """Return True if ip_address is a valid IPv4 address.

    ip_address (string): the ip to validate.

    return (bool): True iff valid.

    """
    ip_address, sep, subnet = ip_address.partition("/")
    if sep != "":
        try:
            subnet = int(subnet)
        except ValueError:
            return False
        if not 0 <= subnet < 32:
            return False
    fields = ip_address.split(".")
    if len(fields) != 4:
        return False
    for field in fields:
        try:
            num = int(field)
        except ValueError:
            return False
        if not 0 <= num < 256:
            return False
    return True


def sanity_check_time_limit(time_limit):
    if time_limit == "":
        time_limit = None
    else:
        time_limit = float(time_limit)
        assert 0 <= time_limit < float("+inf"), \
            "Time limit out of range."
    return time_limit


def sanity_check_memory_limit(memory_limit):
    if memory_limit == "":
        memory_limit = None
    else:
        memory_limit = int(memory_limit)
        assert 0 < memory_limit, "Invalid memory limit."
    return memory_limit


def sanity_check_task_type_class(task_type):
    # Look for a task type with the specified name.
    try:
        task_type_class = get_task_type_class(task_type)
    except KeyError:
        # Task type not found.
        raise ValueError("Task type not recognized: %s." % task_type)
    return task_type_class


class BaseHandler(CommonRequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """

    def safe_get_item(self, cls, ident, session=None):
        """Get item from database of class cls and id ident, using
        session if given, or self.sql_session if not given. If id is
        not found, raise a 404.

        cls (type): class of object to retrieve.
        ident (string): id of object.
        session (Session|None): session to use.

        return (object): the object with the given id.

        raise (HTTPError): 404 if not found.

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

        if config.installed:
            localization_dir = os.path.join("/", "usr", "local", "share",
                                            "locale")
        else:
            localization_dir = os.path.join(os.path.dirname(__file__), "mo")
        if os.path.exists(localization_dir):
            tornado.locale.load_gettext_translations(localization_dir, "cms")

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        params = {}
        params["timestamp"] = make_datetime()
        params["contest"] = self.contest
        params["url_root"] = get_url_root(self.request.path)
        if self.contest is not None:
            params["phase"] = self.contest.phase(params["timestamp"])
            # Keep "== None" in filter arguments. SQLAlchemy does not
            # understand "is None".
            params["unanswered"] = self.sql_session.query(Question)\
                .join(User)\
                .filter(User.contest_id == self.contest.id)\
                .filter(Question.reply_timestamp == None)\
                .filter(Question.ignored == False)\
                .count()  # noqa
        params["contest_list"] = self.sql_session.query(Contest).all()
        params["cookie"] = str(self.cookies)
        return params

    def finish(self, *args, **kwds):
        """Finish this response, ending the HTTP request.

        We override this method in order to properly close the database.

        TODO - Now that we have greenlet support, this method could be
        refactored in terms of context manager or something like
        that. So far I'm leaving it to minimize changes.

        """
        self.sql_session.close()
        try:
            tornado.web.RequestHandler.finish(self, *args, **kwds)
        except IOError:
            # When the client closes the connection before we reply,
            # Tornado raises an IOError exception, that would pollute
            # our log with unnecessarily critical messages
            logger.debug("Connection closed before our reply.")

    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs and \
                kwargs["exc_info"][0] != tornado.web.HTTPError:
            exc_info = kwargs["exc_info"]
            logger.error(
                "Uncaught exception (%r) while processing a request: %s" %
                (exc_info[1], ''.join(traceback.format_exception(*exc_info))))

        # Most of the handlers raise a 404 HTTP error before r_params
        # is defined. If r_params is not defined we try to define it
        # here, and if it fails we simply return a basic textual error notice.
        if hasattr(self, 'r_params'):
            self.render("error.html", status_code=status_code, **self.r_params)
        else:
            try:
                self.r_params = self.render_params()
                self.render("error.html", status_code=status_code,
                            **self.r_params)
            except:
                self.write("A critical error has occurred :-(")
                self.finish()

    def get_non_negative_int(self, argument_name, default, allow_empty=True):
        """ Get a non-negative integer from the arguments.

        Use default if the argument is missing; If allow_empty=False,
        Empty values such as "" and None are not permitted (unless,
        for "", if allow_empty is true.

        argument_name (string): the name of the argument to query.
        default (int): what to return if the argument is missing
        allow_empty (bool): whether to return raise or not in case of
            an empty argument.

        return (int): the converted argument.

        raise (ValueError): if the argument can't be converted into a
            non-negative integer.

        """
        argument = self.get_argument(argument_name, None)
        if argument is None:
            return default
        if allow_empty and argument == "":
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
        initialize_logging("AdminWebServer", shard)

        # A list of pending notifications.
        self.notifications = []

        parameters = {
            "login_url": "/",
            "template_path": pkg_resources.resource_filename(
                "cms.server", "templates/admin"),
            "static_path": pkg_resources.resource_filename(
                "cms.server", "static"),
            "cookie_secret": base64.b64encode(config.secret_key),
            "debug": config.tornado_debug,
        }
        WebService.__init__(self,
                            config.admin_listen_port,
                            _aws_handlers,
                            parameters,
                            shard=shard,
                            listen_address=config.admin_listen_address)
        self.file_cacher = FileCacher(self)
        self.evaluation_service = self.connect_to(
            ServiceCoord("EvaluationService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))
        self.proxy_service = self.connect_to(
            ServiceCoord("ProxyService", 0))
        self.resource_services = []
        for i in xrange(get_service_shards("ResourceService")):
            self.resource_services.append(self.connect_to(
                ServiceCoord("ResourceService", i)))
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
                              "workers_status",
                              "invalidate_submission"]

        elif service == ServiceCoord("ScoringService", 0):
            return method in ["invalidate_submission"]

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

        timestamp (datetime): the time of the notification.
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

        self.r_params = self.render_params()
        self.render("welcome.html", **self.r_params)


def SimpleContestHandler(page):
    class Cls(BaseHandler):
        def get(self, contest_id):
            self.contest = self.safe_get_item(Contest, contest_id)

            self.r_params = self.render_params()
            self.render(page, **self.r_params)
    return Cls


class ResourcesListHandler(BaseHandler):
    def get(self, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.r_params["resource_addresses"] = {}
        services = get_service_shards("ResourceService")
        for i in xrange(services):
            self.r_params["resource_addresses"][i] = get_service_address(
                ServiceCoord("ResourceService", i)).ip
        self.render("resourceslist.html", **self.r_params)


class ResourcesHandler(BaseHandler):
    def get(self, shard=None, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)
            contest_address = "/%s" % contest_id
        else:
            contest_address = ""

        if shard is None:
            shard = "all"

        self.r_params = self.render_params()
        self.r_params["resource_shards"] = \
            get_service_shards("ResourceService")
        self.r_params["resource_addresses"] = {}
        if shard == "all":
            for i in xrange(self.r_params["resource_shards"]):
                self.r_params["resource_addresses"][i] = get_service_address(
                    ServiceCoord("ResourceService", i)).ip
        else:
            shard = int(shard)
            try:
                address = get_service_address(
                    ServiceCoord("ResourceService", shard))
            except KeyError:
                self.redirect("/resourceslist%s" % contest_address)
                return
            self.r_params["resource_addresses"][shard] = address.ip

        self.render("resources.html", **self.r_params)


class AddContestHandler(BaseHandler):
    """Adds a new contest.

    """
    def get(self):
        self.r_params = self.render_params()
        self.render("add_contest.html", **self.r_params)

    def post(self):
        try:
            name = self.get_argument("name", "")
            assert name != "", "No contest name specified."

            description = self.get_argument("description", "")

            languages = self.get_arguments("languages", [])

            token_initial = self.get_non_negative_int(
                "token_initial",
                None)
            token_max = self.get_non_negative_int(
                "token_max",
                None)
            token_total = self.get_non_negative_int(
                "token_total",
                None)
            token_min_interval = timedelta(
                seconds=self.get_non_negative_int(
                    "token_min_interval",
                    0,
                    allow_empty=False))
            token_gen_time = timedelta(
                minutes=self.get_non_negative_int(
                    "token_gen_time",
                    0,
                    allow_empty=False))
            token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                0,
                allow_empty=False)

            max_submission_number = self.get_non_negative_int(
                "max_submission_number",
                None)
            max_user_test_number = self.get_non_negative_int(
                "max_user_test_number",
                None)
            min_submission_interval = self.get_non_negative_int(
                "min_submission_interval",
                None)
            if min_submission_interval is not None:
                min_submission_interval = \
                    timedelta(seconds=min_submission_interval)
            min_user_test_interval = self.get_non_negative_int(
                "min_user_test_interval",
                None)
            if min_user_test_interval is not None:
                min_user_test_interval = \
                    timedelta(seconds=min_user_test_interval)

            start = self.get_argument("start", "")
            if start == "":
                start = None
            else:
                if '.' not in start:
                    start += ".0"
                start = datetime.strptime(start, "%Y-%m-%d %H:%M:%S.%f")

            stop = self.get_argument("stop", "")
            if stop == "":
                stop = None
            else:
                if '.' not in stop:
                    stop += ".0"
                stop = datetime.strptime(stop, "%Y-%m-%d %H:%M:%S.%f")

            assert start <= stop, "Contest ends before it starts."

            timezone = self.get_argument("timezone", "")
            if timezone == "":
                timezone = None

            per_user_time = self.get_non_negative_int(
                "per_user_time",
                None)
            if per_user_time is not None:
                per_user_time = timedelta(seconds=per_user_time)

            score_precision = self.get_non_negative_int(
                "score_precision",
                0,
                allow_empty=False)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid field(s)",
                repr(error))
            self.redirect("/contest/add")
            return

        contest = Contest(name, description, languages, token_initial,
                          token_max, token_total, token_min_interval,
                          token_gen_time, token_gen_number, start, stop,
                          timezone, per_user_time,
                          max_submission_number, max_user_test_number,
                          min_submission_interval, min_user_test_interval,
                          score_precision)
        self.sql_session.add(contest)

        if try_commit(self.sql_session, self):
            # Create the contest on RWS.
            self.application.service.proxy_service.reinitialize()
            self.redirect("/contest/%s" % contest.id)
        else:
            self.redirect("/contest/add")


class ContestHandler(BaseHandler):
    def get(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.render("contest.html", **self.r_params)

    def post(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)

        try:
            contest.name = self.get_argument("name", contest.name)
            assert contest.name != "", "No contest name specified."

            contest.description = self.get_argument("description",
                                                    contest.description)

            contest.languages = self.get_arguments("languages", [])

            contest.token_initial = self.get_non_negative_int(
                "token_initial",
                contest.token_initial)
            contest.token_max = self.get_non_negative_int(
                "token_max",
                contest.token_max)
            contest.token_total = self.get_non_negative_int(
                "token_total",
                contest.token_total)
            contest.token_min_interval = timedelta(
                seconds=self.get_non_negative_int(
                    "token_min_interval",
                    contest.token_min_interval.total_seconds(),
                    allow_empty=False))
            contest.token_gen_time = timedelta(
                minutes=self.get_non_negative_int(
                    "token_gen_time",
                    contest.token_gen_time.total_seconds(),
                    allow_empty=False))
            contest.token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                contest.token_gen_number,
                allow_empty=False)

            contest.max_submission_number = self.get_non_negative_int(
                "max_submission_number",
                contest.max_submission_number)
            contest.max_user_test_number = self.get_non_negative_int(
                "max_user_test_number",
                contest.max_user_test_number)
            contest.min_submission_interval = self.get_non_negative_int(
                "min_submission_interval",
                contest.min_submission_interval.total_seconds() if
                contest.min_submission_interval is not None else None)
            if contest.min_submission_interval is not None:
                contest.min_submission_interval = \
                    timedelta(seconds=contest.min_submission_interval)
            contest.min_user_test_interval = self.get_non_negative_int(
                "min_user_test_interval",
                contest.min_user_test_interval.total_seconds() if
                contest.min_user_test_interval is not None else None)
            if contest.min_user_test_interval is not None:
                contest.min_user_test_interval = \
                    timedelta(seconds=contest.min_user_test_interval)

            contest.start = self.get_argument(
                "start",
                str(contest.start) if contest.start is not None else "")
            if contest.start == "":
                contest.start = None
            else:
                if '.' not in contest.start:
                    contest.start += ".0"
                contest.start = datetime.strptime(contest.start,
                                                  "%Y-%m-%d %H:%M:%S.%f")

            contest.stop = self.get_argument(
                "stop",
                str(contest.stop) if contest.stop is not None else "")
            if contest.stop == "":
                contest.stop = None
            else:
                if '.' not in contest.stop:
                    contest.stop += ".0"
                contest.stop = datetime.strptime(contest.stop,
                                                 "%Y-%m-%d %H:%M:%S.%f")

            assert contest.start <= contest.stop, \
                "Contest ends before it starts."

            contest.timezone = self.get_argument(
                "timezone",
                contest.timezone if contest.timezone is not None else "")
            if contest.timezone == "":
                contest.timezone = None

            contest.per_user_time = self.get_non_negative_int(
                "per_user_time",
                contest.per_user_time.total_seconds() if
                contest.per_user_time is not None else None)
            if contest.per_user_time is not None:
                contest.per_user_time = \
                    timedelta(seconds=contest.per_user_time)

            contest.score_precision = self.get_non_negative_int(
                "score_precision",
                contest.score_precision,
                allow_empty=False)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid field(s).",
                repr(error))
            self.redirect("/contest/%s" % contest_id)
            return

        if try_commit(self.sql_session, self):
            # Update the contest on RWS.
            self.application.service.proxy_service.reinitialize()
        self.redirect("/contest/%s" % contest_id)


class AddStatementHandler(BaseHandler):
    """Add a statement to a task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.render("add_statement.html", **self.r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        language = self.get_argument("language", None)
        if language is None:
            self.application.service.add_notification(
                make_datetime(),
                "No language code specified",
                "The language code can be any string.")
            self.redirect("/add_statement/%s" % task_id)
            return
        statement = self.request.files["statement"][0]
        if not statement["filename"].endswith(".pdf"):
            self.application.service.add_notification(
                make_datetime(),
                "Invalid task statement",
                "The task statement must be a .pdf file.")
            self.redirect("/add_statement/%s" % task_id)
            return
        task_name = task.name
        self.sql_session.close()

        try:
            digest = self.application.service.file_cacher.put_file_content(
                statement["body"],
                "Statement for task %s (lang: %s)" % (task_name, language))
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Task statement storage failed",
                repr(error))
            self.redirect("/add_statement/%s" % task_id)
            return

        # TODO verify that there's no other Statement with that language
        # otherwise we'd trigger an IntegrityError for constraint violation

        self.sql_session = Session()
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        statement = Statement(language, digest, task=task)
        self.sql_session.add(statement)

        if try_commit(self.sql_session, self):
            self.redirect("/task/%s" % task_id)
        else:
            self.redirect("/add_statement/%s" % task_id)


class DeleteStatementHandler(BaseHandler):
    """Delete a statement.

    """
    def get(self, statement_id):
        statement = self.safe_get_item(Statement, statement_id)
        task = statement.task
        self.contest = task.contest

        self.sql_session.delete(statement)

        try_commit(self.sql_session, self)
        self.redirect("/task/%s" % task.id)


class AddAttachmentHandler(BaseHandler):
    """Add an attachment to a task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.render("add_attachment.html", **self.r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        attachment = self.request.files["attachment"][0]
        task_name = task.name
        self.sql_session.close()

        try:
            digest = self.application.service.file_cacher.put_file_content(
                attachment["body"],
                "Task attachment for %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Attachment storage failed",
                repr(error))
            self.redirect("/add_attachment/%s" % task_id)
            return

        # TODO verify that there's no other Attachment with that filename
        # otherwise we'd trigger an IntegrityError for constraint violation

        self.sql_session = Session()
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        attachment = Attachment(attachment["filename"], digest, task=task)
        self.sql_session.add(attachment)

        if try_commit(self.sql_session, self):
            self.redirect("/task/%s" % task_id)
        else:
            self.redirect("/add_attachment/%s" % task_id)


class DeleteAttachmentHandler(BaseHandler):
    """Delete an attachment.

    """
    def get(self, attachment_id):
        attachment = self.safe_get_item(Attachment, attachment_id)
        task = attachment.task
        self.contest = task.contest

        self.sql_session.delete(attachment)

        try_commit(self.sql_session, self)
        self.redirect("/task/%s" % task.id)


class AddManagerHandler(BaseHandler):
    """Add a manager to a dataset.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["dataset"] = dataset
        self.render("add_manager.html", **self.r_params)

    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        manager = self.request.files["manager"][0]
        task_name = task.name
        self.sql_session.close()

        try:
            digest = self.application.service.file_cacher.put_file_content(
                manager["body"],
                "Task manager for %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Manager storage failed",
                repr(error))
            self.redirect("/add_manager/%s" % dataset_id)
            return

        self.sql_session = Session()
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        manager = Manager(manager["filename"], digest, dataset=dataset)
        self.sql_session.add(manager)

        if try_commit(self.sql_session, self):
            self.redirect("/task/%s" % task.id)
        else:
            self.redirect("/add_manager/%s" % dataset_id)


class DeleteManagerHandler(BaseHandler):
    """Delete a manager.

    """
    def get(self, manager_id):
        manager = self.safe_get_item(Manager, manager_id)
        task = manager.dataset.task
        self.contest = task.contest

        self.sql_session.delete(manager)

        try_commit(self.sql_session, self)
        self.redirect("/task/%s" % task.id)


# TODO: Move this somewhere more appropriate?
def copy_dataset(
        new_dataset, old_dataset, clone_results, clone_managers, sql_session):
    """Copy an existing dataset's test cases, and optionally
    submission results and managers.

    new_dataset (Dataset): target dataset to copy into.
    old_dataset (Dataset): original dataset to copy from.
    clone_results (bool): copy submission results.
    clone_managers (bool): copy dataset managers.
    sql_session (Session): the session to commit.

    """
    new_testcases = dict()
    for old_t in old_dataset.testcases.itervalues():
        new_t = old_t.clone()
        new_t.dataset = new_dataset
        new_testcases[new_t.codename] = new_t

    if clone_managers:
        for old_m in old_dataset.managers.itervalues():
            new_m = old_m.clone()
            new_m.dataset = new_dataset

    sql_session.flush()

    new_results = list()
    if clone_results:
        # We issue this query manually to optimize it: we load all
        # executables and evaluations at once instead of having SA
        # lazy-load them when we access them for each SubmissionResult,
        # one at a time. We need them because we want to copy them too,
        # recursively.
        old_results = \
            sql_session.query(SubmissionResult)\
                       .filter(SubmissionResult.dataset == old_dataset)\
                       .options(joinedload(SubmissionResult.submission))\
                       .options(joinedload(SubmissionResult.executables))\
                       .options(joinedload(SubmissionResult.evaluations)).all()

        for old_sr in old_results:
            # Create the submission result.
            new_sr = old_sr.clone()
            new_sr.submission = old_sr.submission
            new_sr.dataset = new_dataset

            # Create executables.
            for old_e in old_sr.executables.itervalues():
                new_e = old_e.clone()
                new_e.submission_result = new_sr

            # Create evaluations.
            for old_e in old_sr.evaluations:
                new_e = old_e.clone()
                new_e.submission_result = new_sr
                new_e.testcase = new_testcases[old_e.codename]

            # We need to keep a reference to the object to prevent it
            # from being deleted (as SQLAlchemy's Session holds just a
            # weak reference...).
            new_results += [new_sr]

    sql_session.flush()

    return new_results


class AddDatasetHandler(BaseHandler):
    """Add a dataset to a task.

    """
    def get(self, task_id, dataset_id_to_copy):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        # We can either clone an existing dataset, or '-' for a new one.
        if dataset_id_to_copy == '-':
            original_dataset = None
            description = "Default"
        else:
            try:
                original_dataset = \
                    self.safe_get_item(Dataset, dataset_id_to_copy)
                description = "Copy of %s" % original_dataset.description
            except ValueError:
                raise tornado.web.HTTPError(404)

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["clone_id"] = dataset_id_to_copy
        self.r_params["original_dataset"] = original_dataset
        self.r_params["original_dataset_task_type_parameters"] = \
            json.loads(original_dataset.task_type_parameters) \
            if original_dataset is not None else None
        self.r_params["default_description"] = description
        self.render("add_dataset.html", **self.r_params)

    def post(self, task_id, dataset_id_to_copy):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        # We can either clone an existing dataset, or '-' for a new one.
        if dataset_id_to_copy == '-':
            original_dataset = None
        else:
            try:
                original_dataset = \
                    self.safe_get_item(Dataset, dataset_id_to_copy)
            except ValueError:
                raise tornado.web.HTTPError(404)

        description = self.get_argument("description", "")

        # Ensure description is unique.
        for d in task.datasets:
            if d.description == description:
                self.application.service.add_notification(
                    make_datetime(),
                    "Dataset name \"%s\" is already taken." % description,
                    "Please choose a unique name for this dataset.")
                self.redirect("/add_dataset/%s/%s" % (task_id,
                                                      dataset_id_to_copy))
                return

        try:
            time_limit = sanity_check_time_limit(
                self.get_argument("time_limit", ""))
            memory_limit = sanity_check_memory_limit(
                self.get_argument("memory_limit", ""))
            task_type = self.get_argument("task_type", "")
            task_type_class = sanity_check_task_type_class(task_type)
            task_type_parameters = json.dumps(
                task_type_class.parse_handler(
                    self, "TaskTypeOptions_%s_" % task_type))
            score_type = self.get_argument("score_type", "")
            score_type_parameters = self.get_argument("score_type_parameters",
                                                      "")

        except Exception as error:
            logger.warning("Invalid field: %s" % (traceback.format_exc()))
            self.application.service.add_notification(
                make_datetime(),
                "Invalid field(s)",
                repr(error))
            self.redirect("/add_dataset/%s/%s" % (task_id,
                                                  dataset_id_to_copy))
            return

        # Add new dataset.
        autojudge = False
        dataset = Dataset(
            description, autojudge,
            time_limit, memory_limit,
            task_type, task_type_parameters,
            score_type, score_type_parameters,
            task=task)
        self.sql_session.add(dataset)

        if original_dataset is not None:
            # If we were cloning the dataset, copy all testcases across
            # too. If the user insists, clone all evaluation
            # information too.
            clone_results = bool(self.get_argument("clone_results", False))
            clone_managers = bool(self.get_argument("clone_managers", False))
            copy_dataset(dataset, original_dataset, clone_results,
                         clone_managers, self.sql_session)

        # If the task does not yet have an active dataset, make this
        # one active.
        if task.active_dataset is None:
            task.active_dataset = dataset

        if try_commit(self.sql_session, self):
            # self.application.service.scoring_service.reinitialize()
            self.redirect("/task/%s" % task_id)
        else:
            self.redirect("/add_dataset/%s/%s" % (task_id,
                                                  dataset_id_to_copy))


class RenameDatasetHandler(BaseHandler):
    """Rename the descripton of a dataset.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["dataset"] = dataset
        self.render("rename_dataset.html", **self.r_params)

    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        description = self.get_argument("description", "")

        # Ensure description is unique.
        for d in task.datasets:
            if d is not dataset and d.description == description:
                self.application.service.add_notification(
                    make_datetime(),
                    "Dataset name \"%s\" is already taken." % description,
                    "Please choose a unique name for this dataset.")
                self.redirect("/rename_dataset/%s" % dataset_id)
                return

        dataset.description = description

        if try_commit(self.sql_session, self):
            self.redirect("/task/%s" % task.id)
        else:
            self.redirect("/rename_dataset/%s" % dataset_id)


class DeleteDatasetHandler(BaseHandler):
    """Delete a dataset from a task.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["dataset"] = dataset
        self.render("delete_dataset.html", **self.r_params)

    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.sql_session.delete(dataset)

        if try_commit(self.sql_session, self):
            # self.application.service.scoring_service.reinitialize()
            pass
        self.redirect("/task/%s" % task.id)


class ActivateDatasetHandler(BaseHandler):
    """Set a given dataset to be the active one for a task.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        changes = compute_changes_for_dataset(task.active_dataset, dataset)
        notify_users = set()

        # By default, we will notify users who's public scores have changed, or
        # their non-public scores have changed but they have used a token.
        for c in changes:
            score_changed = c.old_score is not None or c.new_score is not None
            public_score_changed = c.old_public_score is not None or \
                c.new_public_score is not None
            if public_score_changed or \
                    (c.submission.tokened() and score_changed):
                notify_users.add(c.submission.user.id)

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["dataset"] = dataset
        self.r_params["changes"] = changes
        self.r_params["default_notify_users"] = notify_users
        self.render("activate_dataset.html", **self.r_params)

    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        task.active_dataset = dataset

        if try_commit(self.sql_session, self):
            # self.application.service.scoring_service.reinitialize()
            self.application.service.proxy_service.dataset_updated(
                task_id=task.id)

            # This kicks off judging of any submissions which were previously
            # unloved, but are now part of an autojudged taskset.
            self.application.service.evaluation_service.search_jobs_not_done()
            self.application.service.scoring_service.search_jobs_not_done()

        # Now send notifications to contestants.
        datetime = make_datetime()

        r = re.compile('notify_([0-9]+)$')
        count = 0
        for k, v in self.request.arguments.iteritems():
            m = r.match(k)
            if not m:
                continue
            user = self.safe_get_item(User, m.group(1))
            message = Message(datetime,
                              self.get_argument("message_subject", ""),
                              self.get_argument("message_text", ""),
                              user=user)
            self.sql_session.add(message)
            count += 1

        if try_commit(self.sql_session, self):
            self.application.service.add_notification(
                make_datetime(),
                "Messages sent to %d users." % count, "")

        self.redirect("/task/%s" % task.id)


class ToggleAutojudgeDatasetHandler(BaseHandler):
    """Toggle whether a given dataset is judged automatically or not.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        dataset.autojudge = not dataset.autojudge

        if try_commit(self.sql_session, self):
            # self.application.service.scoring_service.reinitialize()

            # This kicks off judging of any submissions which were previously
            # unloved, but are now part of an autojudged taskset.
            self.application.service.evaluation_service.search_jobs_not_done()
            self.application.service.scoring_service.search_jobs_not_done()

        self.redirect("/task/%s" % dataset.task_id)


class AddTestcaseHandler(BaseHandler):
    """Add a testcase to a dataset.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["dataset"] = dataset
        self.render("add_testcase.html", **self.r_params)

    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        codename = self.get_argument("codename")

        try:
            input_ = self.request.files["input"][0]
            output = self.request.files["output"][0]
        except KeyError:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid data",
                "Please fill both input and output.")
            self.redirect("/add_testcase/%s" % dataset_id)
            return

        public = self.get_argument("public", None) is not None
        task_name = task.name
        self.sql_session.close()

        try:
            input_digest = \
                self.application.service.file_cacher.put_file_content(
                    input_["body"],
                    "Testcase input for task %s" % task_name)
            output_digest = \
                self.application.service.file_cacher.put_file_content(
                    output["body"],
                    "Testcase output for task %s" % task_name)
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Testcase storage failed",
                repr(error))
            self.redirect("/add_testcase/%s" % dataset_id)
            return

        self.sql_session = Session()
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        testcase = Testcase(
            codename, public, input_digest, output_digest, dataset=dataset)
        self.sql_session.add(testcase)

        if try_commit(self.sql_session, self):
            # max_score and/or extra_headers might have changed.
            self.application.service.proxy_service.reinitialize()
            self.redirect("/task/%s" % task.id)
        else:
            self.redirect("/add_testcase/%s" % dataset_id)


class DeleteTestcaseHandler(BaseHandler):
    """Delete a testcase.

    """
    def get(self, testcase_id):
        testcase = self.safe_get_item(Testcase, testcase_id)
        task = testcase.dataset.task
        self.contest = task.contest

        self.sql_session.delete(testcase)

        if try_commit(self.sql_session, self):
            # max_score and/or extra_headers might have changed.
            self.application.service.proxy_service.reinitialize()
        self.redirect("/task/%s" % task.id)


class AddTaskHandler(BaseHandler):
    def get(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.render("add_task.html", **self.r_params)

    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        try:
            name = self.get_argument("name", "")
            assert name != "", "No task name specified."

            title = self.get_argument("title", "")

            primary_statements = self.get_argument("primary_statements", "[]")

            submission_format_choice = self.get_argument(
                "submission_format_choice", "")

            if submission_format_choice == "simple":
                submission_format = [SubmissionFormatElement("%s.%%l" % name)]
            elif submission_format_choice == "other":
                submission_format = self.get_argument("submission_format", "")
                if submission_format not in ["", "[]"]:
                    try:
                        format_list = json.loads(submission_format)
                        submission_format = []
                        for element in format_list:
                            submission_format.append(SubmissionFormatElement(
                                str(element)))
                    except Exception as error:
                        # FIXME Are the following two commands really needed?
                        self.sql_session.rollback()
                        logger.info(repr(error))
                        raise ValueError("Submission format not recognized.")
            else:
                raise ValueError("Submission format not recognized.")

            token_initial = self.get_non_negative_int(
                "token_initial",
                None)
            token_max = self.get_non_negative_int(
                "token_max",
                None)
            token_total = self.get_non_negative_int(
                "token_total",
                None)
            token_min_interval = timedelta(
                seconds=self.get_non_negative_int(
                    "token_min_interval",
                    0,
                    allow_empty=False))
            token_gen_time = timedelta(
                minutes=self.get_non_negative_int(
                    "token_gen_time",
                    0,
                    allow_empty=False))
            token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                0,
                allow_empty=False)

            max_submission_number = self.get_non_negative_int(
                "max_submission_number",
                None)
            max_user_test_number = self.get_non_negative_int(
                "max_user_test_number",
                None)
            min_submission_interval = self.get_non_negative_int(
                "min_submission_interval",
                None)
            if min_submission_interval is not None:
                min_submission_interval = \
                    timedelta(seconds=min_submission_interval)
            min_user_test_interval = self.get_non_negative_int(
                "min_user_test_interval",
                None)
            if min_user_test_interval is not None:
                min_user_test_interval = \
                    timedelta(seconds=min_user_test_interval)

            score_precision = self.get_non_negative_int(
                "score_precision",
                0,
                allow_empty=False)

            # These belong to the first dataset.
            time_limit = sanity_check_time_limit(
                self.get_argument("time_limit", ""))
            memory_limit = sanity_check_memory_limit(
                self.get_argument("memory_limit", ""))
            task_type = self.get_argument("task_type", "")
            task_type_class = sanity_check_task_type_class(task_type)
            task_type_parameters = json.dumps(
                task_type_class.parse_handler(
                    self, "TaskTypeOptions_%s_" % task_type))
            score_type = self.get_argument("score_type", "")
            score_type_parameters = self.get_argument("score_type_parameters",
                                                      "")

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid field(s)",
                repr(error))
            self.redirect("/add_task/%s" % contest_id)
            return

        task = Task(len(self.contest.tasks),
                    name, title, primary_statements,
                    token_initial, token_max, token_total,
                    token_min_interval, token_gen_time, token_gen_number,
                    max_submission_number, max_user_test_number,
                    min_submission_interval, min_user_test_interval,
                    score_precision, contest=self.contest,
                    submission_format=submission_format)
        self.sql_session.add(task)

        # Create its first dataset.
        description = 'Default'
        autojudge = True
        dataset = Dataset(
            description, autojudge,
            time_limit, memory_limit,
            task_type, task_type_parameters,
            score_type, score_type_parameters,
            task=task)
        self.sql_session.add(dataset)

        # Make the dataset active. Life works better that way.
        task.active_dataset = dataset

        if try_commit(self.sql_session, self):
            # Create the task on RWS.
            self.application.service.proxy_service.reinitialize()
            self.redirect("/task/%s" % task.id)
        else:
            self.redirect("/add_task/%s" % contest_id)


class TaskHandler(BaseHandler):
    """Task handler, with a POST method to edit the task.

    """
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["submissions"] = \
            self.sql_session.query(Submission)\
                .join(Task).filter(Task.id == task_id)\
                .order_by(Submission.timestamp.desc()).all()
        self.render("task.html", **self.r_params)

    def post(self, task_id):
        task = self.safe_get_item(Task, task_id)
        self.contest = task.contest

        try:
            task.name = self.get_argument("name", task.name)
            assert task.name != "", "No task name specified."

            task.title = self.get_argument("title", task.title)

            task.primary_statements = self.get_argument(
                "primary_statements", task.primary_statements)

            # submission_format_choice == "other"
            submission_format = self.get_argument("submission_format", "")
            if submission_format not in ["", "[]"] and submission_format != \
                    json.dumps([x.filename for x in task.submission_format]):
                try:
                    format_list = json.loads(submission_format)
                    for element in task.submission_format:
                        self.sql_session.delete(element)
                    del task.submission_format[:]
                    for element in format_list:
                        self.sql_session.add(
                            SubmissionFormatElement(str(element), task=task))
                except Exception as error:
                    # FIXME Are the following two commands really needed?
                    self.sql_session.rollback()
                    logger.info(repr(error))
                    raise ValueError("Submission format not recognized.")

            for dataset in task.datasets:
                dataset.time_limit = sanity_check_time_limit(
                    self.get_argument(
                        "time_limit_%d" % dataset.id,
                        str(dataset.time_limit)
                        if dataset.time_limit is not None else ""))

                dataset.memory_limit = sanity_check_memory_limit(
                    self.get_argument(
                        "memory_limit_%d" % dataset.id,
                        str(dataset.memory_limit)
                        if dataset.memory_limit is not None else ""))

                dataset.task_type = self.get_argument(
                    "task_type_%d" % dataset.id, "")
                # Look for a task type with the specified name.
                task_type_class = \
                    sanity_check_task_type_class(dataset.task_type)

                dataset.task_type_parameters = json.dumps(
                    task_type_class.parse_handler(
                        self, "TaskTypeOptions_%s_%d_" % (
                            dataset.task_type, dataset.id)))

                dataset.score_type = self.get_argument(
                    "score_type_%d" % dataset.id, dataset.score_type)
                dataset.score_type_parameters = self.get_argument(
                    "score_type_parameters_%d" % dataset.id,
                    dataset.score_type_parameters)

                for testcase in dataset.testcases.itervalues():
                    testcase.public = bool(self.get_argument(
                        "testcase_%s_public" % testcase.id, False))

            task.token_initial = self.get_non_negative_int(
                "token_initial",
                task.token_initial)
            task.token_max = self.get_non_negative_int(
                "token_max",
                task.token_max)
            task.token_total = self.get_non_negative_int(
                "token_total",
                task.token_total)
            task.token_min_interval = timedelta(
                seconds=self.get_non_negative_int(
                    "token_min_interval",
                    task.token_min_interval.total_seconds(),
                    allow_empty=False))
            task.token_gen_time = timedelta(
                minutes=self.get_non_negative_int(
                    "token_gen_time",
                    task.token_gen_time.total_seconds(),
                    allow_empty=False))
            task.token_gen_number = self.get_non_negative_int(
                "token_gen_number",
                task.token_gen_number,
                allow_empty=False)

            task.max_submission_number = self.get_non_negative_int(
                "max_submission_number",
                task.max_submission_number)
            task.max_user_test_number = self.get_non_negative_int(
                "max_user_test_number",
                task.max_user_test_number)
            task.min_submission_interval = self.get_non_negative_int(
                "min_submission_interval",
                task.min_submission_interval.total_seconds() if
                task.min_submission_interval is not None else None)
            if task.min_submission_interval is not None:
                task.min_submission_interval = \
                    timedelta(seconds=task.min_submission_interval)
            task.min_user_test_interval = self.get_non_negative_int(
                "min_user_test_interval",
                task.min_user_test_interval.total_seconds() if
                task.min_user_test_interval is not None else None)
            if task.min_user_test_interval is not None:
                task.min_user_test_interval = \
                    timedelta(seconds=task.min_user_test_interval)

            task.score_precision = self.get_non_negative_int(
                "score_precision",
                task.score_precision,
                allow_empty=False)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid field(s)",
                repr(error))
            self.redirect("/task/%s" % task_id)
            return

        if try_commit(self.sql_session, self):
            # Update the task on RWS.
            self.application.service.proxy_service.reinitialize()
        self.redirect("/task/%s" % task_id)


class DatasetSubmissionsHandler(BaseHandler):
    """Shows all submissions for this dataset, allowing the admin to
    view the results under different datasets.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["active_dataset"] = task.active_dataset
        self.r_params["shown_dataset"] = dataset
        self.r_params["datasets"] = \
            self.sql_session.query(Dataset)\
                            .filter(Dataset.task == task)\
                            .order_by(Dataset.description).all()
        self.r_params["submissions"] = \
            self.sql_session.query(Submission)\
                            .filter(Submission.task == task)\
                            .options(joinedload(Submission.task))\
                            .options(joinedload(Submission.user))\
                            .options(joinedload(Submission.files))\
                            .options(joinedload(Submission.token))\
                            .options(joinedload(Submission.results))\
                            .order_by(Submission.timestamp.desc()).all()
        self.render("submissionlist.html", **self.r_params)


class RankingHandler(BaseHandler):
    """Shows the ranking for a contest.

    """
    def get(self, contest_id, format="online"):
        # This validates the contest id.
        self.safe_get_item(Contest, contest_id)

        # This massive joined load gets all the information which we will need
        # to generating the rankings.
        self.contest = self.sql_session.query(Contest)\
            .filter(Contest.id == contest_id)\
            .options(joinedload('users'))\
            .options(joinedload('users.submissions'))\
            .options(joinedload('users.submissions.token'))\
            .options(joinedload('users.submissions.results'))\
            .first()

        self.r_params = self.render_params()
        if format == "txt":
            self.set_header("Content-Type", "text/plain")
            self.set_header("Content-Disposition",
                            "attachment; filename=\"ranking.txt\"")
            self.render("ranking.txt", **self.r_params)
        elif format == "csv":
            self.set_header("Content-Type", "text/csv")
            self.set_header("Content-Disposition",
                            "attachment; filename=\"ranking.csv\"")
            self.render("ranking.csv", **self.r_params)
        else:
            self.render("ranking.html", **self.r_params)


class AddAnnouncementHandler(BaseHandler):
    """Called to actually add an announcement

    """
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            ann = Announcement(make_datetime(), subject, text,
                               contest=self.contest)
            self.sql_session.add(ann)
            try_commit(self.sql_session, self)
        self.redirect("/announcements/%s" % contest_id)


class RemoveAnnouncementHandler(BaseHandler):
    """Called to remove an announcement.

    """
    def get(self, ann_id):
        ann = self.safe_get_item(Announcement, ann_id)
        contest_id = ann.contest.id

        self.sql_session.delete(ann)

        try_commit(self.sql_session, self)
        self.redirect("/announcements/%s" % contest_id)


class UserViewHandler(BaseHandler):
    """Shows the details of a single user (submissions, questions,
    messages), and allows to send the latters.

    """
    def get(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest

        self.r_params = self.render_params()
        self.r_params["selected_user"] = user
        self.r_params["submissions"] = user.submissions
        self.render("user.html", **self.r_params)

    def post(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest

        user.first_name = self.get_argument("first_name", user.first_name)
        user.last_name = self.get_argument("last_name", user.last_name)
        user.username = self.get_argument("username", user.username)

        if user.username == "":
            self.application.service.add_notification(
                make_datetime(),
                "No username specified.",
                "")
            self.redirect("/user/%s" % user_id)
            return

        user.password = self.get_argument("password", user.password)
        user.email = self.get_argument("email", user.email)

        user.ip = self.get_argument("ip", None)
        if user.ip == '':
            user.ip = None
        if user.ip is not None and not valid_ip(user.ip):
            self.application.service.add_notification(
                make_datetime(),
                "Invalid ip",
                "")
            self.redirect("/user/%s" % user_id)
            return

        user.timezone = self.get_argument("timezone", None)

        starting_time = None
        if self.get_argument("starting_time", "") not in ["", "None"]:
            try:
                try:
                    starting_time = datetime.strptime(
                        self.get_argument("starting_time"),
                        "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    starting_time = datetime.strptime(
                        self.get_argument("starting_time"),
                        "%Y-%m-%d %H:%M:%S.%f")
            except Exception as error:
                self.application.service.add_notification(
                    make_datetime(),
                    "Invalid starting time(s).",
                    repr(error))
                self.redirect("/user/%s" % user_id)
                return
        user.starting_time = starting_time

        user.extra_time = self.get_argument(
            "extra_time",
            str(int(user.extra_time.total_seconds())))
        try:
            user.extra_time = timedelta(seconds=int(user.extra_time))
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid extra time.",
                repr(error))
            self.redirect("/user/%s" % user_id)
            return

        user.hidden = bool(self.get_argument("hidden", False))
        user.primary_statements = self.get_argument("primary_statements",
                                                    user.primary_statements)

        if try_commit(self.sql_session, self):
            # Update the user on RWS.
            self.application.service.proxy_service.reinitialize()
        self.redirect("/user/%s" % user_id)


class AddUserHandler(SimpleContestHandler("add_user.html")):
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        first_name = self.get_argument("first_name", "")
        last_name = self.get_argument("last_name", "")
        username = self.get_argument("username", "")

        if username == "":
            self.application.service.add_notification(
                make_datetime(),
                "No username specified.",
                "")
            self.redirect("/add_user/%s" % contest_id)
            return

        password = self.get_argument("password", "")
        email = self.get_argument("email", None)

        ip_address = self.get_argument("ip", None)
        if ip_address == '':
            ip_address = None
        if ip_address is not None and not valid_ip(ip_address):
            self.application.service.add_notification(
                make_datetime(),
                "Invalid ip",
                "")
            self.redirect("/add_user/%s" % contest_id)
            return

        timezone = self.get_argument("timezone", None)

        starting_time = None
        if self.get_argument("starting_time", "") not in ["", "None"]:
            try:
                try:
                    starting_time = datetime.strptime(
                        self.get_argument("starting_time"),
                        "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    starting_time = datetime.strptime(
                        self.get_argument("starting_time"),
                        "%Y-%m-%d %H:%M:%S.%f")
            except Exception as error:
                self.application.service.add_notification(
                    make_datetime(),
                    "Invalid starting time(s).",
                    repr(error))
                self.redirect("/add_user/%s" % contest_id)
                return

        extra_time = self.get_argument("extra_time", 0)
        try:
            extra_time = timedelta(seconds=int(extra_time))
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid extra time.",
                repr(error))
            self.redirect("/add_user/%s" % contest_id)
            return

        hidden = bool(self.get_argument("hidden", False))
        primary_statements = self.get_argument("primary_statements", "{}")

        user = User(first_name, last_name, username, password=password,
                    email=email, ip=ip_address, hidden=hidden,
                    primary_statements=primary_statements,
                    timezone=timezone, starting_time=starting_time,
                    extra_time=extra_time,
                    contest=self.contest)
        self.sql_session.add(user)

        if try_commit(self.sql_session, self):
            # Create the user on RWS.
            self.application.service.proxy_service.reinitialize()
            self.redirect("/user/%s" % user.id)
        else:
            self.redirect("/add_user/%s" % contest_id)


class SubmissionViewHandler(BaseHandler):
    """Shows the details of a submission. All data is already present
    in the list of the submissions of the task or of the user, but we
    need a place where to link messages like 'Submission 42 failed to
    compile please check'.

    """
    def get(self, submission_id, dataset_id=None):
        submission = self.safe_get_item(Submission, submission_id)
        task = submission.task
        self.contest = task.contest

        if dataset_id is not None:
            dataset = self.safe_get_item(Dataset, dataset_id)
        else:
            dataset = task.active_dataset
        assert dataset.task is task

        self.r_params = self.render_params()
        self.r_params["s"] = submission
        self.r_params["active_dataset"] = task.active_dataset
        self.r_params["shown_dataset"] = dataset
        self.r_params["datasets"] = \
            self.sql_session.query(Dataset)\
                            .filter(Dataset.task == task)\
                            .order_by(Dataset.description).all()
        self.render("submission.html", **self.r_params)


class SubmissionFileHandler(FileHandler):
    """Shows a submission file.

    """
    # FIXME: Replace with FileFromDigestHandler?
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

        self.r_params = self.render_params()
        self.r_params["questions"] = self.sql_session.query(Question)\
            .join(User).filter(User.contest_id == contest_id)\
            .order_by(Question.question_timestamp.desc())\
            .order_by(Question.id).all()
        self.render("questions.html", **self.r_params)


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

        question.reply_timestamp = make_datetime()

        if try_commit(self.sql_session, self):
            logger.info("Reply sent to user %s for question with id %s." %
                        (question.user.username, question_id))

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
        if try_commit(self.sql_session, self):
            logger.info("Question '%s' by user %s %s" %
                        (question.subject, question.user.username,
                         ["unignored", "ignored"][should_ignore]))

        self.redirect(ref)


class MessageHandler(BaseHandler):
    """Called when a message is sent to a specific user.

    """

    def post(self, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = user.contest

        message = Message(make_datetime(),
                          self.get_argument("message_subject", ""),
                          self.get_argument("message_text", ""),
                          user=user)
        self.sql_session.add(message)
        if try_commit(self.sql_session, self):
            logger.info("Message submitted to user %s."
                        % user.username)

        self.redirect("/user/%s" % user_id)


class FileFromDigestHandler(FileHandler):

    def get(self, digest, filename):
        #TODO: Accept a MIME type
        self.sql_session.close()
        self.fetch(digest, "text/plain", filename)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """
    def get(self):
        res = []
        last_notification = make_datetime(
            float(self.get_argument("last_notification", "0")))

        # Keep "== None" in filter arguments. SQLAlchemy does not
        # understand "is None".
        questions = self.sql_session.query(Question)\
            .filter(Question.reply_timestamp == None)\
            .filter(Question.question_timestamp > last_notification)\
            .all()  # noqa

        for question in questions:
            res.append({"type": "new_question",
                        "timestamp":
                        make_timestamp(question.question_timestamp),
                        "subject": question.subject,
                        "text": question.text,
                        "contest_id": question.user.contest_id})

        # Simple notifications
        for notification in self.application.service.notifications:
            res.append({"type": "notification",
                        "timestamp": make_timestamp(notification[0]),
                        "subject": notification[1],
                        "text": notification[2]})
        self.application.service.notifications = []

        self.write(json.dumps(res))


_aws_handlers = [
    (r"/", MainHandler),
    (r"/([0-9]+)", MainHandler),
    (r"/contest/([0-9]+)", ContestHandler),
    (r"/announcements/([0-9]+)", SimpleContestHandler("announcements.html")),
    (r"/userlist/([0-9]+)", SimpleContestHandler("userlist.html")),
    (r"/tasklist/([0-9]+)", SimpleContestHandler("tasklist.html")),
    (r"/contest/add", AddContestHandler),
    (r"/ranking/([0-9]+)", RankingHandler),
    (r"/ranking/([0-9]+)/([a-z]+)", RankingHandler),
    (r"/task/([0-9]+)", TaskHandler),
    (r"/dataset/([0-9]+)", DatasetSubmissionsHandler),
    (r"/add_task/([0-9]+)", AddTaskHandler),
    (r"/add_statement/([0-9]+)", AddStatementHandler),
    (r"/delete_statement/([0-9]+)", DeleteStatementHandler),
    (r"/add_attachment/([0-9]+)", AddAttachmentHandler),
    (r"/delete_attachment/([0-9]+)", DeleteAttachmentHandler),
    (r"/add_manager/([0-9]+)", AddManagerHandler),
    (r"/delete_manager/([0-9]+)", DeleteManagerHandler),
    (r"/add_dataset/([0-9]+)/(-|[0-9]+)", AddDatasetHandler),
    (r"/rename_dataset/([0-9]+)", RenameDatasetHandler),
    (r"/delete_dataset/([0-9]+)", DeleteDatasetHandler),
    (r"/activate_dataset/([0-9]+)", ActivateDatasetHandler),
    (r"/autojudge_dataset/([0-9]+)", ToggleAutojudgeDatasetHandler),
    (r"/add_testcase/([0-9]+)", AddTestcaseHandler),
    (r"/delete_testcase/([0-9]+)", DeleteTestcaseHandler),
    (r"/user/([0-9]+)", UserViewHandler),
    (r"/add_user/([0-9]+)", AddUserHandler),
    (r"/add_announcement/([0-9]+)", AddAnnouncementHandler),
    (r"/remove_announcement/([0-9]+)", RemoveAnnouncementHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?", SubmissionViewHandler),
    (r"/submission_file/([0-9]+)", SubmissionFileHandler),
    (r"/file/([a-f0-9]+)/([a-zA-Z0-9_.-]+)", FileFromDigestHandler),
    (r"/message/([0-9]+)", MessageHandler),
    (r"/question/([0-9]+)", QuestionReplyHandler),
    (r"/ignore_question/([0-9]+)", QuestionIgnoreHandler),
    (r"/questions/([0-9]+)", QuestionsHandler),
    (r"/resourceslist", ResourcesListHandler),
    (r"/resourceslist/([0-9]+)", ResourcesListHandler),
    (r"/resources", ResourcesHandler),
    (r"/resources/([0-9]+|all)", ResourcesHandler),
    (r"/resources/([0-9]+|all)/([0-9]+)", ResourcesHandler),
    (r"/notifications", NotificationsHandler),
]
