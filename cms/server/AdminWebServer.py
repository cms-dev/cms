#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import base64
import json
import logging
import os
import pkg_resources
import re
import traceback
from datetime import datetime, timedelta
from StringIO import StringIO
import zipfile

from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

import tornado.web
import tornado.locale

from cms import config, ServiceCoord, get_service_shards, get_service_address
from cms.io import WebService
from cms.db import Session, Contest, User, Announcement, Question, Message, \
    Submission, File, Task, Dataset, Attachment, Manager, Testcase, \
    SubmissionFormatElement, Statement
from cms.db.filecacher import FileCacher
from cms.grading import compute_changes_for_dataset
from cms.grading.tasktypes import get_task_type_class
from cms.grading.scoretypes import get_score_type_class
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
            "Operation failed.", "%s" % error)
        return False
    else:
        handler.application.service.add_notification(
            make_datetime(),
            "Operation successful.", "")
        return True


def argument_reader(func, empty=None):
    """Return an helper method for reading and parsing form values.

    func (function): the parser and validator for the value.
    empty (object): the value to store if an empty string is retrieved.

    return (function): a function to be used as a method of a
        RequestHandler.

    """
    def helper(self, dest, name, empty=empty):
        """Read the argument called "name" and save it in "dest".

        self (RequestHandler): a thing with a get_argument method.
        dest (dict): a place to store the obtained value.
        name (string): the name of the argument and of the item.
        empty (object): overrides the default empty value.

        """
        value = self.get_argument(name, None)
        if value is None:
            return
        if value == "":
            dest[name] = empty
        else:
            dest[name] = func(value)
    return helper


def parse_int(value):
    """Parse and validate an integer."""
    try:
        return int(value)
    except:
        raise ValueError("Can't cast %s to int." % value)


def parse_timedelta_sec(value):
    """Parse and validate a timedelta (as number of seconds)."""
    try:
        return timedelta(seconds=float(value))
    except:
        raise ValueError("Can't cast %s to timedelta." % value)


def parse_timedelta_min(value):
    """Parse and validate a timedelta (as number of minutes)."""
    try:
        return timedelta(minutes=float(value))
    except:
        raise ValueError("Can't cast %s to timedelta." % value)


def parse_datetime(value):
    """Parse and validate a datetime (in pseudo-ISO8601)."""
    if '.' not in value:
        value += ".0"
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
    except:
        raise ValueError("Can't cast %s to datetime." % value)


def parse_ip_address_or_subnet(value):
    """Validate an IP address or subnet."""
    address, sep, subnet = value.partition("/")
    if sep != "":
        subnet = int(subnet)
        assert 0 <= subnet < 32
    fields = address.split(".")
    assert len(fields) == 4
    for field in fields:
        num = int(field)
        assert 0 <= num < 256
    return value


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
                "Uncaught exception (%r) while processing a request: %s",
                exc_info[1], ''.join(traceback.format_exception(*exc_info)))

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

    get_string = argument_reader(lambda a: a, empty="")

    # When a checkbox isn't active it's not sent at all, making it
    # impossible to distinguish between missing and False.
    def get_bool(self, dest, name):
        """Parse a boolean.

        dest (dict): a place to store the result.
        name (string): the name of the argument and of the item.

        """
        value = self.get_argument(name, False)
        try:
            dest[name] = bool(value)
        except:
            raise ValueError("Can't cast %s to bool." % value)

    get_int = argument_reader(parse_int)

    get_timedelta_sec = argument_reader(parse_timedelta_sec)

    get_timedelta_min = argument_reader(parse_timedelta_min)

    get_datetime = argument_reader(parse_datetime)

    get_ip_address_or_subnet = argument_reader(parse_ip_address_or_subnet)

    def get_submission_format(self, dest):
        """Parse the submission format.

        Using the two arguments "submission_format_choice" and
        "submission_format" set the "submission_format" item of the
        given dictionary.

        dest (dict): a place to store the result.

        """
        choice = self.get_argument("submission_format_choice", "other")
        if choice == "simple":
            filename = "%s.%%l" % dest["name"]
            format_ = [SubmissionFormatElement(filename)]
        elif choice == "other":
            value = self.get_argument("submission_format", "[]")
            if value == "":
                value = "[]"
            format_ = []
            try:
                for filename in json.loads(value):
                    format_ += [SubmissionFormatElement(filename)]
            except ValueError:
                raise ValueError("Submission format not recognized.")
        else:
            raise ValueError("Submission format not recognized.")
        dest["submission_format"] = format_

    def get_time_limit(self, dest, field):
        """Parse the time limit.

        Read the argument with the given name and use its value to set
        the "time_limit" item of the given dictionary.

        dest (dict): a place to store the result.
        field (string): the name of the argument to use.

        """
        value = self.get_argument(field, None)
        if value is None:
            return
        if value == "":
            dest["time_limit"] = None
        else:
            try:
                value = float(value)
            except:
                raise ValueError("Can't cast %s to float." % value)
            if not 0 <= value < float("+inf"):
                raise ValueError("Time limit out of range.")
            dest["time_limit"] = value

    def get_memory_limit(self, dest, field):
        """Parse the memory limit.

        Read the argument with the given name and use its value to set
        the "memory_limit" item of the given dictionary.

        dest (dict): a place to store the result.
        field (string): the name of the argument to use.

        """
        value = self.get_argument(field, None)
        if value is None:
            return
        if value == "":
            dest["memory_limit"] = None
        else:
            try:
                value = int(value)
            except:
                raise ValueError("Can't cast %s to float." % value)
            if not 0 < value:
                raise ValueError("Invalid memory limit.")
            dest["memory_limit"] = value

    def get_task_type(self, dest, name, params):
        """Parse the task type.

        Parse the arguments to get the task type and its parameters,
        and fill them in the "task_type" and "task_type_parameters"
        items of the given dictionary.

        dest (dict): a place to store the result.
        name (string): the name of the argument that holds the task
            type name.
        params (string): the prefix of the names of the arguments that
            hold the parameters.

        """
        name = self.get_argument(name, None)
        if name is None:
            raise ValueError("Task type not found.")
        try:
            class_ = get_task_type_class(name)
        except KeyError:
            raise ValueError("Task type not recognized: %s." % name)
        params = json.dumps(class_.parse_handler(self, params + name + "_"))
        dest["task_type"] = name
        dest["task_type_parameters"] = params

    def get_score_type(self, dest, name, params):
        """Parse the score type.

        Parse the arguments to get the score type and its parameters,
        and fill them in the "score_type" and "score_type_parameters"
        items of the given dictionary.

        dest (dict): a place to store the result.
        name (string): the name of the argument that holds the score
            type name.
        params (string): the name of the argument that hold the
            parameters.

        """
        name = self.get_argument(name, None)
        if name is None:
            raise ValueError("Score type not found.")
        try:
            get_score_type_class(name)
        except KeyError:
            raise ValueError("Score type not recognized: %s." % name)
        params = self.get_argument(params, None)
        if params is None:
            raise ValueError("Score type parameters not found.")
        dest["score_type"] = name
        dest["score_type_parameters"] = params


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
        parameters = {
            "login_url": "/",
            "template_path": pkg_resources.resource_filename(
                "cms.server", "templates/admin"),
            "static_path": pkg_resources.resource_filename(
                "cms.server", "static"),
            "cookie_secret": base64.b64encode(config.secret_key),
            "debug": config.tornado_debug,
            "rpc_enabled": True,
        }
        super(AdminWebServer, self).__init__(
            config.admin_listen_port,
            _aws_handlers,
            parameters,
            shard=shard,
            listen_address=config.admin_listen_address)

        # A list of pending notifications.
        self.notifications = []

        self.file_cacher = FileCacher(self)
        self.evaluation_service = self.connect_to(
            ServiceCoord("EvaluationService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        ranking_enabled = len(config.rankings) > 0
        self.proxy_service = self.connect_to(
            ServiceCoord("ProxyService", 0),
            must_be_present=ranking_enabled)

        self.resource_services = []
        for i in xrange(get_service_shards("ResourceService")):
            self.resource_services.append(self.connect_to(
                ServiceCoord("ResourceService", i)))
        self.logservice = self.connect_to(ServiceCoord("LogService", 0))

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
            attrs = dict()

            self.get_string(attrs, "name", empty=None)
            self.get_string(attrs, "description")

            assert attrs.get("name") is not None, "No contest name specified."

            allowed_localizations = \
                self.get_argument("allowed_localizations", "")
            if allowed_localizations:
                attrs["allowed_localizations"] = \
                    [x.strip() for x in allowed_localizations.split(",")
                     if len(x) > 0 and not x.isspace()]
            else:
                attrs["allowed_localizations"] = []

            attrs["languages"] = self.get_arguments("languages", [])

            self.get_string(attrs, "token_mode")
            self.get_int(attrs, "token_max_number")
            self.get_timedelta_sec(attrs, "token_min_interval")
            self.get_int(attrs, "token_gen_initial")
            self.get_int(attrs, "token_gen_number")
            self.get_timedelta_min(attrs, "token_gen_interval")
            self.get_int(attrs, "token_gen_max")

            self.get_int(attrs, "max_submission_number")
            self.get_int(attrs, "max_user_test_number")
            self.get_timedelta_sec(attrs, "min_submission_interval")
            self.get_timedelta_sec(attrs, "min_user_test_interval")

            self.get_datetime(attrs, "start")
            self.get_datetime(attrs, "stop")

            self.get_string(attrs, "timezone", empty=None)
            self.get_timedelta_sec(attrs, "per_user_time")
            self.get_int(attrs, "score_precision")

            # Create the contest.
            contest = Contest(**attrs)
            self.sql_session.add(contest)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/contest/add")
            return

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
            attrs = contest.get_attrs()

            self.get_string(attrs, "name", empty=None)
            self.get_string(attrs, "description")

            assert attrs.get("name") is not None, "No contest name specified."

            allowed_localizations = \
                self.get_argument("allowed_localizations", "")
            if allowed_localizations:
                attrs["allowed_localizations"] = \
                    [x.strip() for x in allowed_localizations.split(",")
                     if len(x) > 0 and not x.isspace()]
            else:
                attrs["allowed_localizations"] = []

            attrs["languages"] = self.get_arguments("languages", [])

            self.get_string(attrs, "token_mode")
            self.get_int(attrs, "token_max_number")
            self.get_timedelta_sec(attrs, "token_min_interval")
            self.get_int(attrs, "token_gen_initial")
            self.get_int(attrs, "token_gen_number")
            self.get_timedelta_min(attrs, "token_gen_interval")
            self.get_int(attrs, "token_gen_max")

            self.get_int(attrs, "max_submission_number")
            self.get_int(attrs, "max_user_test_number")
            self.get_timedelta_sec(attrs, "min_submission_interval")
            self.get_timedelta_sec(attrs, "min_user_test_interval")

            self.get_datetime(attrs, "start")
            self.get_datetime(attrs, "stop")

            self.get_string(attrs, "timezone", empty=None)
            self.get_timedelta_sec(attrs, "per_user_time")
            self.get_int(attrs, "score_precision")

            # Update the contest.
            contest.set_attrs(attrs)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s).", repr(error))
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

        try:
            attrs = dict()

            self.get_string(attrs, "description")

            # Ensure description is unique.
            if any(attrs["description"] == d.description
                   for d in task.datasets):
                self.application.service.add_notification(
                    make_datetime(),
                    "Dataset name %r is already taken." % attrs["description"],
                    "Please choose a unique name for this dataset.")
                self.redirect("/add_dataset/%s/%s" % (task_id,
                                                      dataset_id_to_copy))
                return

            self.get_time_limit(attrs, "time_limit")
            self.get_memory_limit(attrs, "memory_limit")
            self.get_task_type(attrs, "task_type", "TaskTypeOptions_")
            self.get_score_type(attrs, "score_type", "score_type_parameters")

            # Create the dataset.
            attrs["autojudge"] = False
            attrs["task"] = task
            dataset = Dataset(**attrs)
            self.sql_session.add(dataset)

        except Exception as error:
            logger.warning("Invalid field.", exc_info=True)
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/add_dataset/%s/%s" % (task_id, dataset_id_to_copy))
            return

        if original_dataset is not None:
            # If we were cloning the dataset, copy all managers and
            # testcases across too. If the user insists, clone all
            # evaluation information too.
            clone_results = bool(self.get_argument("clone_results", False))
            dataset.clone_from(original_dataset, True, True, clone_results)

        # If the task does not yet have an active dataset, make this
        # one active.
        if task.active_dataset is None:
            task.active_dataset = dataset

        if try_commit(self.sql_session, self):
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
        if any(description == d.description
               for d in task.datasets if d is not dataset):
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
            self.application.service.proxy_service.dataset_updated(
                task_id=task.id)

            # This kicks off judging of any submissions which were previously
            # unloved, but are now part of an autojudged taskset.
            self.application.service\
                .evaluation_service.search_operations_not_done()
            self.application.service\
                .scoring_service.search_operations_not_done()

        # Now send notifications to contestants.
        datetime = make_datetime()

        r = re.compile('notify_([0-9]+)$')
        count = 0
        for k in self.request.arguments:
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
            self.application.service\
                .evaluation_service.search_operations_not_done()
            self.application.service\
                .scoring_service.search_operations_not_done()

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


class AddTestcasesHandler(BaseHandler):
    """Add several testcases to a dataset.

    """
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        self.r_params = self.render_params()
        self.r_params["task"] = task
        self.r_params["dataset"] = dataset
        self.render("add_testcases.html", **self.r_params)

    def post(self, dataset_id):
        # TODO: this method is quite long, some splitting is needed.
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        try:
            archive = self.request.files["archive"][0]
        except KeyError:
            self.application.service.add_notification(
                make_datetime(),
                "Invalid data",
                "Please choose tests archive.")
            self.redirect("/add_testcases/%s" % dataset_id)
            return

        public = self.get_argument("public", None) is not None
        overwrite = self.get_argument("overwrite", None) is not None

        # Get input/output file names templates, or use default ones.
        input_template = self.get_argument("input_template", None)
        if not input_template:
            input_template = "input.*"
        output_template = self.get_argument("output_template", None)
        if not output_template:
            output_template = "output.*"
        input_re = re.compile(re.escape(input_template).replace("\\*",
                              "(.*)") + "$")
        output_re = re.compile(re.escape(output_template).replace("\\*",
                               "(.*)") + "$")

        task_name = task.name
        self.sql_session.close()

        fp = StringIO(archive["body"])
        try:
            with zipfile.ZipFile(fp, "r") as archive_zfp:
                tests = dict()
                # Match input/output file names to testcases' codenames.
                for filename in archive_zfp.namelist():
                    match = input_re.match(filename)
                    if match:
                        codename = match.group(1)
                        if codename not in tests:
                            tests[codename] = [None, None]
                        tests[codename][0] = filename
                    else:
                        match = output_re.match(filename)
                        if match:
                            codename = match.group(1)
                            if codename not in tests:
                                tests[codename] = [None, None]
                            tests[codename][1] = filename

                skipped_tc = []
                overwritten_tc = []
                added_tc = []
                for codename, testdata in tests.iteritems():
                    # If input or output file isn't found, skip it.
                    if not testdata[0] or not testdata[1]:
                        continue
                    self.sql_session = Session()

                    # Check, whether current testcase already exists.
                    dataset = self.safe_get_item(Dataset, dataset_id)
                    task = dataset.task
                    self.contest = task.contest
                    if codename in dataset.testcases:
                        # If we are allowed, remove existing testcase.
                        # If not - skip this testcase.
                        if overwrite:
                            testcase = dataset.testcases[codename]
                            self.sql_session.delete(testcase)

                            if not try_commit(self.sql_session, self):
                                skipped_tc.append(codename)
                                continue
                            overwritten_tc.append(codename)
                        else:
                            skipped_tc.append(codename)
                            continue

                    # Add current testcase.
                    try:
                        input_ = archive_zfp.read(testdata[0])
                        output = archive_zfp.read(testdata[1])
                    except Exception as error:
                        self.application.service.add_notification(
                            make_datetime(),
                            "Reading testcase %s failed" % codename,
                            repr(error))
                        self.redirect("/add_testcases/%s" % dataset_id)
                        return
                    try:
                        input_digest = self.application.service\
                            .file_cacher.put_file_content(
                                input_,
                                "Testcase input for task %s" % task_name)
                        output_digest = self.application.service\
                            .file_cacher.put_file_content(
                                output,
                                "Testcase output for task %s" % task_name)
                    except Exception as error:
                        self.application.service.add_notification(
                            make_datetime(),
                            "Testcase storage failed",
                            repr(error))
                        self.redirect("/add_testcases/%s" % dataset_id)
                        return
                    testcase = Testcase(codename, public, input_digest,
                                        output_digest, dataset=dataset)
                    self.sql_session.add(testcase)

                    if not try_commit(self.sql_session, self):
                        self.application.service.add_notification(
                            make_datetime(),
                            "Couldn't add test %s" % codename,
                            "")
                        self.redirect("/add_testcases/%s" % dataset_id)
                        return
                    if codename not in overwritten_tc:
                        added_tc.append(codename)
        except zipfile.BadZipfile:
            self.application.service.add_notification(
                make_datetime(),
                "The selected file is not a zip file.",
                "Please select a valid zip file.")
            self.redirect("/add_testcases/%s" % dataset_id)
            return

        self.application.service.add_notification(
            make_datetime(),
            "Successfully added %d and overwritten %d testcase(s)" %
            (len(added_tc), len(overwritten_tc)),
            "Added: %s; overwritten: %s; skipped: %s" %
            (", ".join(added_tc) if added_tc else "none",
             ", ".join(overwritten_tc) if overwritten_tc else "none",
             ", ".join(skipped_tc) if skipped_tc else "none"))
        self.application.service.proxy_service.reinitialize()
        self.redirect("/task/%s" % task.id)


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
            attrs = dict()

            self.get_string(attrs, "name", empty=None)
            self.get_string(attrs, "title")

            assert attrs.get("name") is not None, "No task name specified."

            self.get_string(attrs, "primary_statements")

            self.get_submission_format(attrs)

            self.get_string(attrs, "token_mode")
            self.get_int(attrs, "token_max_number")
            self.get_timedelta_sec(attrs, "token_min_interval")
            self.get_int(attrs, "token_gen_initial")
            self.get_int(attrs, "token_gen_number")
            self.get_timedelta_min(attrs, "token_gen_interval")
            self.get_int(attrs, "token_gen_max")

            self.get_int(attrs, "max_submission_number")
            self.get_int(attrs, "max_user_test_number")
            self.get_timedelta_sec(attrs, "min_submission_interval")
            self.get_timedelta_sec(attrs, "min_user_test_interval")

            self.get_int(attrs, "score_precision")

            self.get_string(attrs, "score_mode")

            # Create the task.
            attrs["num"] = len(self.contest.tasks)
            attrs["contest"] = self.contest
            task = Task(**attrs)
            self.sql_session.add(task)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/add_task/%s" % contest_id)
            return

        try:
            attrs = dict()

            self.get_time_limit(attrs, "time_limit")
            self.get_memory_limit(attrs, "memory_limit")
            self.get_task_type(attrs, "task_type", "TaskTypeOptions_")
            self.get_score_type(attrs, "score_type", "score_type_parameters")

            # Create its first dataset.
            attrs["description"] = "Default"
            attrs["autojudge"] = True
            attrs["task"] = task
            dataset = Dataset(**attrs)
            self.sql_session.add(dataset)

            # Make the dataset active. Life works better that way.
            task.active_dataset = dataset

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/add_task/%s" % contest_id)
            return

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
            attrs = task.get_attrs()

            self.get_string(attrs, "name", empty=None)
            self.get_string(attrs, "title")

            assert attrs.get("name") is not None, "No task name specified."

            self.get_string(attrs, "primary_statements")

            self.get_submission_format(attrs)

            self.get_string(attrs, "token_mode")
            self.get_int(attrs, "token_max_number")
            self.get_timedelta_sec(attrs, "token_min_interval")
            self.get_int(attrs, "token_gen_initial")
            self.get_int(attrs, "token_gen_number")
            self.get_timedelta_min(attrs, "token_gen_interval")
            self.get_int(attrs, "token_gen_max")

            self.get_int(attrs, "max_submission_number")
            self.get_int(attrs, "max_user_test_number")
            self.get_timedelta_sec(attrs, "min_submission_interval")
            self.get_timedelta_sec(attrs, "min_user_test_interval")

            self.get_int(attrs, "score_precision")

            self.get_string(attrs, "score_mode")

            # Update the task.
            task.set_attrs(attrs)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/task/%s" % task_id)
            return

        for dataset in task.datasets:
            try:
                attrs = dataset.get_attrs()

                self.get_time_limit(attrs, "time_limit_%d" % dataset.id)
                self.get_memory_limit(attrs, "memory_limit_%d" % dataset.id)
                self.get_task_type(attrs, "task_type_%d" % dataset.id,
                                   "TaskTypeOptions_%d_" % dataset.id)
                self.get_score_type(attrs, "score_type_%d" % dataset.id,
                                    "score_type_parameters_%d" % dataset.id)

                # Update the dataset.
                dataset.set_attrs(attrs)

            except Exception as error:
                self.application.service.add_notification(
                    make_datetime(), "Invalid field(s)", repr(error))
                self.redirect("/task/%s" % task_id)
                return

            for testcase in dataset.testcases.itervalues():
                testcase.public = bool(self.get_argument(
                    "testcase_%s_public" % testcase.id, False))

        if try_commit(self.sql_session, self):
            # Update the task and score on RWS.
            self.application.service.proxy_service.dataset_updated(
                task_id=task.id)
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


class ContestSubmissionsHandler(BaseHandler):
    """Shows all submissions for this contest.

    """
    def get(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)
        self.contest = contest

        self.r_params = self.render_params()
        self.r_params["submissions"] = \
            self.sql_session.query(Submission).join(Task)\
                            .filter(Task.contest == contest)\
                            .options(joinedload(Submission.user))\
                            .options(joinedload(Submission.files))\
                            .options(joinedload(Submission.token))\
                            .options(joinedload(Submission.results))\
                            .order_by(Submission.timestamp.desc()).all()
        self.render("contest_submissions.html", **self.r_params)


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

        try:
            attrs = user.get_attrs()

            self.get_string(attrs, "first_name")
            self.get_string(attrs, "last_name")
            self.get_string(attrs, "username", empty=None)
            self.get_string(attrs, "password")
            self.get_string(attrs, "email")

            assert attrs.get("username") is not None, \
                "No username specified."

            self.get_ip_address_or_subnet(attrs, "ip")

            self.get_string(attrs, "timezone", empty=None)
            self.get_datetime(attrs, "starting_time")
            self.get_timedelta_sec(attrs, "delay_time")
            self.get_timedelta_sec(attrs, "extra_time")

            self.get_bool(attrs, "hidden")
            self.get_string(attrs, "primary_statements")

            # Update the user.
            user.set_attrs(attrs)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/user/%s" % user_id)
            return

        if try_commit(self.sql_session, self):
            # Update the user on RWS.
            self.application.service.proxy_service.reinitialize()
        self.redirect("/user/%s" % user_id)


class AddUserHandler(SimpleContestHandler("add_user.html")):
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        try:
            attrs = dict()

            self.get_string(attrs, "first_name")
            self.get_string(attrs, "last_name")
            self.get_string(attrs, "username", empty=None)
            self.get_string(attrs, "password")
            self.get_string(attrs, "email")

            assert attrs.get("username") is not None, \
                "No username specified."

            self.get_ip_address_or_subnet(attrs, "ip")

            self.get_string(attrs, "timezone", empty=None)
            self.get_datetime(attrs, "starting_time")
            self.get_timedelta_sec(attrs, "delay_time")
            self.get_timedelta_sec(attrs, "extra_time")

            self.get_bool(attrs, "hidden")
            self.get_string(attrs, "primary_statements")

            # Create the user.
            attrs["contest"] = self.contest
            user = User(**attrs)
            self.sql_session.add(user)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/add_user/%s" % contest_id)
            return

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


class SubmissionCommentHandler(BaseHandler):
    """Called when the admin comments on a submission.

    """
    def post(self, submission_id, dataset_id=None):
        submission = self.safe_get_item(Submission, submission_id)

        try:
            attrs = {"comment": submission.comment}
            self.get_string(attrs, "comment")
            submission.set_attrs(attrs)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))

        else:
            try_commit(self.sql_session, self)

        if dataset_id is None:
            self.redirect("/submission/%s" % submission_id)
        else:
            self.redirect("/submission/%s/%s" % (submission_id,
                                                 dataset_id))


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
            logger.info("Reply sent to user %s for question with id %s.",
                        question.user.username, question_id)

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
            logger.info("Question '%s' by user %s %s",
                        question.subject, question.user.username,
                        ["unignored", "ignored"][should_ignore])

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
            logger.info("Message submitted to user %s.", user.username)

        self.redirect("/user/%s" % user_id)


class FileFromDigestHandler(FileHandler):

    def get(self, digest, filename):
        # TODO: Accept a MIME type
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
    (r"/submissions/([0-9]+)", ContestSubmissionsHandler),
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
    (r"/add_testcases/([0-9]+)", AddTestcasesHandler),
    (r"/delete_testcase/([0-9]+)", DeleteTestcaseHandler),
    (r"/user/([0-9]+)", UserViewHandler),
    (r"/add_user/([0-9]+)", AddUserHandler),
    (r"/add_announcement/([0-9]+)", AddAnnouncementHandler),
    (r"/remove_announcement/([0-9]+)", RemoveAnnouncementHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?", SubmissionViewHandler),
    (r"/submission_file/([0-9]+)", SubmissionFileHandler),
    (r"/submission_comment/([0-9]+)(?:/([0-9]+))?", SubmissionCommentHandler),
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
