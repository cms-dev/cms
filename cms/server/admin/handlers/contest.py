#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Contest-related handlers for AWS.

"""

from cms import ServiceCoord, get_service_shards, get_service_address
from cms.db import Contest, Participation, Submission
from cmscommon.datetime import make_datetime

from .base import BaseHandler, SimpleContestHandler, SimpleHandler, \
    require_permission


class AddContestHandler(
        SimpleHandler("add_contest.html", permission_all=True)):
    """Adds a new contest.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = self.url("contests", "add")

        try:
            attrs = dict()

            self.get_string(attrs, "name", empty=None)
            assert attrs.get("name") is not None, "No contest name specified."
            attrs["description"] = attrs["name"]

            # Create the contest.
            contest = Contest(**attrs)
            self.sql_session.add(contest)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # Create the contest on RWS.
            self.service.proxy_service.reinitialize()
            self.redirect(self.url("contest", contest.id))
        else:
            self.redirect(fallback_page)


class ContestHandler(SimpleContestHandler("contest.html")):
    @require_permission(BaseHandler.PERMISSION_ALL)
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
                     if x != "" and not x.isspace()]
            else:
                attrs["allowed_localizations"] = []

            attrs["languages"] = self.get_arguments("languages")

            self.get_bool(attrs, "submissions_download_allowed")
            self.get_bool(attrs, "allow_questions")
            self.get_bool(attrs, "allow_user_tests")
            self.get_bool(attrs, "block_hidden_participations")
            self.get_bool(attrs, "allow_password_authentication")
            self.get_bool(attrs, "ip_restriction")
            self.get_bool(attrs, "ip_autologin")

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

            self.get_bool(attrs, "analysis_enabled")
            self.get_datetime(attrs, "analysis_start")
            self.get_datetime(attrs, "analysis_stop")

            # Update the contest.
            contest.set_attrs(attrs)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s).", repr(error))
            self.redirect(self.url("contest", contest_id))
            return

        if self.try_commit():
            # Update the contest on RWS.
            self.service.proxy_service.reinitialize()
        self.redirect(self.url("contest", contest_id))


class OverviewHandler(BaseHandler):
    """Home page handler, with queue and workers statuses.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.render("overview.html", **self.r_params)


class ResourcesListHandler(BaseHandler):
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.r_params["resource_addresses"] = {}
        services = get_service_shards("ResourceService")
        for i in range(services):
            self.r_params["resource_addresses"][i] = get_service_address(
                ServiceCoord("ResourceService", i)).ip
        self.render("resourceslist.html", **self.r_params)


class ContestListHandler(SimpleHandler("contests.html")):
    """Get returns the list of all contests, post perform operations on
    a specific contest (removing them from CMS).

    """

    REMOVE = "Remove"

    @require_permission(BaseHandler.AUTHENTICATED)
    def post(self):
        contest_id = self.get_argument("contest_id")
        operation = self.get_argument("operation")

        if operation == self.REMOVE:
            asking_page = self.url("contests", contest_id, "remove")
            # Open asking for remove page
            self.redirect(asking_page)
        else:
            self.service.add_notification(
                make_datetime(), "Invalid operation %s" % operation, "")
            self.redirect(self.url("contests"))


class RemoveContestHandler(BaseHandler):
    """Get returns a page asking for confirmation, delete actually removes
    the contest from CMS.

    """

    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)
        submission_query = self.sql_session.query(Submission)\
            .join(Submission.participation)\
            .filter(Participation.contest == contest)

        self.contest = contest
        self.render_params_for_remove_confirmation(submission_query)
        self.render("contest_remove.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)

        self.sql_session.delete(contest)
        if self.try_commit():
            self.service.proxy_service.reinitialize()

        # Maybe they'll want to do this again (for another contest)
        self.write("../../contests")
