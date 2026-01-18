#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2017 Valentin Rosca <rosca.valentin2012@gmail.com>
# Copyright © 2021 Manuel Gundlach <manuel.gundlach@gmail.com>
# Copyright © 2026 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2026 Chuyang Wang <mail@chuyang-wang.de>
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

"""User-related handlers for AWS.

"""

from cms.db import Contest, Participation, Submission, Team, Group, User
from cmscommon.datetime import make_datetime

from .base import BaseHandler, SimpleContestHandler, SimpleHandler, \
    require_permission


class UserHandler(BaseHandler):
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, user_id):
        user = self.safe_get_item(User, user_id)

        self.r_params = self.render_params()
        self.r_params["user"] = user
        self.r_params["participations"] = \
            self.sql_session.query(Participation)\
                .filter(Participation.user == user)\
                .all()
        self.r_params["unassigned_contests"] = \
            self.sql_session.query(Contest)\
                .filter(Contest.id.notin_(
                    self.sql_session.query(Participation.contest_id)
                        .filter(Participation.user == user)
                        .all()))\
                .all()
        self.render("user.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, user_id):
        fallback_page = self.url("user", user_id)

        user = self.safe_get_item(User, user_id)

        try:
            attrs = user.get_attrs()

            self.get_string(attrs, "first_name")
            self.get_string(attrs, "last_name")
            self.get_string(attrs, "username", empty=None)

            self.get_password(attrs, user.password, False)

            self.get_string(attrs, "email", empty=None)
            self.get_string_list(attrs, "preferred_languages")
            self.get_string(attrs, "timezone", empty=None)

            assert attrs.get("username") is not None, \
                "No username specified."

            # Update the user.
            user.set_attrs(attrs)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # Update the user on RWS.
            self.service.proxy_service.reinitialize()
        self.redirect(fallback_page)


class UserListHandler(SimpleHandler("users.html")):
    """Get returns the list of all users, post perform operations on
    a specific user (removing them from CMS).

    """

    REMOVE = "Remove"

    @require_permission(BaseHandler.AUTHENTICATED)
    def post(self):
        user_id: str = self.get_argument("user_id")
        operation: str = self.get_argument("operation")

        if operation == self.REMOVE:
            asking_page = self.url("users", user_id, "remove")
            self.redirect(asking_page)
        else:
            self.service.add_notification(
                make_datetime(), "Invalid operation %s" % operation, "")
            self.redirect(self.url("contests"))


class TeamListHandler(SimpleHandler("teams.html")):
    """Get returns the list of all teams, post perform operations on
    a specific team (removing them from CMS).

    """

    REMOVE = "Remove"

    @require_permission(BaseHandler.AUTHENTICATED)
    def post(self):
        team_id: str = self.get_argument("team_id")
        operation: str = self.get_argument("operation")

        if operation == self.REMOVE:
            asking_page = self.url("teams", team_id, "remove")
            self.redirect(asking_page)
        else:
            self.service.add_notification(
                make_datetime(), "Invalid operation %s" % operation, ""
            )
            self.redirect(self.url("contests"))


class RemoveUserHandler(BaseHandler):
    """Get returns a page asking for confirmation, delete actually removes
    the user from CMS.

    """

    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, user_id):
        user = self.safe_get_item(User, user_id)
        submission_query = self.sql_session.query(Submission)\
            .join(Submission.participation)\
            .filter(Participation.user == user)
        participation_query = self.sql_session.query(Participation)\
            .filter(Participation.user == user)

        self.render_params_for_remove_confirmation(submission_query)
        self.r_params["user"] = user
        self.r_params["participation_count"] = participation_query.count()
        self.render("user_remove.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, user_id):
        user = self.safe_get_item(User, user_id)

        self.sql_session.delete(user)
        if self.try_commit():
            self.service.proxy_service.reinitialize()

        # Maybe they'll want to do this again (for another user)
        self.write("../../users")


class RemoveTeamHandler(BaseHandler):
    """Get returns a page asking for confirmation, delete actually removes
    the team from CMS.

    """

    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, team_id):
        team = self.safe_get_item(Team, team_id)
        participation_query = self.sql_session.query(Participation).filter(
            Participation.team == team
        )

        self.r_params = self.render_params()
        self.r_params["team"] = team
        self.r_params["participation_count"] = participation_query.count()
        self.render("team_remove.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, team_id):
        team = self.safe_get_item(Team, team_id)
        try:

            # Remove associations
            self.sql_session.query(Participation).filter(
                Participation.team_id == team_id
            ).update({Participation.team_id: None})

            # delete the team
            self.sql_session.delete(team)
            if self.try_commit():
                self.service.proxy_service.reinitialize()
        except Exception as fallback_error:
            self.service.add_notification(
                make_datetime(), "Error removing team", repr(fallback_error)
            )

        # Maybe they'll want to do this again (for another team)
        self.write("../../teams")


class TeamHandler(BaseHandler):
    """Manage a single team.

    If referred by GET, this handler will return a pre-filled HTML form.
    If referred by POST, this handler will sync the team data with the form's.
    """
    def get(self, team_id):
        team = self.safe_get_item(Team, team_id)

        self.r_params = self.render_params()
        self.r_params["team"] = team
        self.render("team.html", **self.r_params)

    def post(self, team_id):
        fallback_page = self.url("team", team_id)

        team = self.safe_get_item(Team, team_id)

        try:
            attrs = team.get_attrs()

            self.get_string(attrs, "code")
            self.get_string(attrs, "name")

            assert attrs.get("code") is not None, \
                "No team code specified."

            # Update the team.
            team.set_attrs(attrs)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # Update the team on RWS.
            self.service.proxy_service.reinitialize()
        self.redirect(fallback_page)


class AddTeamHandler(SimpleHandler("add_team.html", permission_all=True)):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = self.url("teams", "add")

        try:
            attrs = dict()

            self.get_string(attrs, "code")
            self.get_string(attrs, "name")

            assert attrs.get("code") is not None, \
                "No team code specified."

            # Create the team.
            team = Team(**attrs)
            self.sql_session.add(team)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # Create the team on RWS.
            self.service.proxy_service.reinitialize()

        # In case other teams need to be added.
        self.redirect(fallback_page)


class AddUserHandler(SimpleHandler("add_user.html", permission_all=True)):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = self.url("users", "add")

        try:
            attrs = dict()

            self.get_string(attrs, "first_name")
            self.get_string(attrs, "last_name")
            self.get_string(attrs, "username", empty=None)

            self.get_password(attrs, None, False)

            self.get_string(attrs, "email", empty=None)

            assert attrs.get("username") is not None, \
                "No username specified."

            self.get_string(attrs, "timezone", empty=None)

            self.get_string_list(attrs, "preferred_languages")

            # Create the user.
            user = User(**attrs)
            self.sql_session.add(user)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # Create the user on RWS.
            self.service.proxy_service.reinitialize()
            self.redirect(self.url("user", user.id))
        else:
            self.redirect(fallback_page)


class AddParticipationHandler(BaseHandler):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, user_id):
        fallback_page = self.url("user", user_id)

        user = self.safe_get_item(User, user_id)

        try:
            group_id: str = self.get_argument("group_id")
            assert group_id != "null", "Please select a valid group"
        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        group = self.safe_get_item(Group, group_id)
        self.contest = group.contest

        attrs = {}
        self.get_bool(attrs, "hidden")
        self.get_bool(attrs, "unrestricted")

        # Create the participation.
        participation = Participation(contest=self.contest,
                                      user=user,
                                      hidden=attrs["hidden"],
                                      unrestricted=attrs["unrestricted"])
        self.sql_session.add(participation)

        if self.try_commit():
            # Create the user on RWS.
            self.service.proxy_service.reinitialize()

        # Maybe they'll want to do this again (for another contest).
        self.redirect(fallback_page)


class EditParticipationHandler(BaseHandler):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, user_id):
        fallback_page = self.url("user", user_id)

        user = self.safe_get_item(User, user_id)

        try:
            contest_id: str = self.get_argument("contest_id")
            operation: str = self.get_argument("operation")
            assert contest_id != "null", "Please select a valid contest"
            assert operation in (
                "Remove",
            ), "Please select a valid operation"
        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        self.contest = self.safe_get_item(Contest, contest_id)

        if operation == "Remove":
            # Remove the participation.
            participation = self.sql_session.query(Participation)\
                .filter(Participation.user == user)\
                .filter(Participation.contest == self.contest)\
                .first()
            self.sql_session.delete(participation)

        if self.try_commit():
            # Create the user on RWS.
            self.service.proxy_service.reinitialize()

        # Maybe they'll want to do this again (for another contest).
        self.redirect(fallback_page)


class GroupListHandler(SimpleContestHandler("groups.html")):
    """Get returns the list of all groups.

    """

    DELETE_GROUP = "Delete selected group"
    MAKE_MAIN = "Make main group"

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, contest_id):
        fallback_page = self.url("contest", contest_id, "groups")

        try:
            group_id = self.get_argument("group_id")
            operation = self.get_argument("operation")

            contest = self.safe_get_item(Contest, contest_id)
            group = self.safe_get_item(Group, group_id)

            if operation == self.DELETE_GROUP:
                self._handle_delete_group(contest, group)
                self.redirect(fallback_page)
                return
            elif operation == self.MAKE_MAIN:
                contest.main_group_id = group.id
                self.try_commit()
                self.redirect(fallback_page)
                return
            else:
                self.service.add_notification(
                    make_datetime(), "Invalid operation", 
                    f"I do not understand the operation `{operation}'")
                self.redirect(fallback_page)
                return

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

    def _handle_delete_group(self, contest, group):
        # disallow deleting non-empty groups
        if len(group.participations) != 0:
            self.application.service.add_notification(
                make_datetime(), "Cannot delete group containing users",
                f"The group `{group.name}' contains "
                f"{len(group.participations)} users")
            return

        # disallow deleting the main_group of the contest
        if contest.main_group_id == group.id:
            self.application.service.add_notification(
                make_datetime(), f"Cannot delete a contest's main group.",
                f"To delete '{group.name}', change the main group of "
                f"the contest first to another group.")
            return

        self.sql_session.delete(group)
        self.try_commit()


class AddGroupHandler(BaseHandler):
    """Adds a new group.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, contest_id):
        fallback_page = self.url("contest", contest_id, "group", "add")

        try:
            attrs = dict()

            self.get_string(attrs, "name")

            assert attrs.get("name") is not None, \
                "No name specified."

            attrs["contest"] = self.safe_get_item(Contest, contest_id)

            # Create the group.
            group = Group(**attrs)
            self.sql_session.add(group)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        self.try_commit()
        self.redirect(self.url("contest", contest_id,
                               "group", group.id, "edit"))


class GroupHandler(BaseHandler):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, contest_id, group_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()

        group = self.safe_get_item(Group, group_id)
        assert group.contest_id == self.contest.id

        self.r_params["group"] = group
        self.render("group.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, contest_id, group_id):
        fallback_page = self.url("contest", contest_id,
                                 "group", group_id, "edit")

        self.contest = self.safe_get_item(Contest, contest_id)
        group = self.safe_get_item(Group, group_id)
        assert group.contest_id == self.contest.id

        try:
            attrs = group.get_attrs()

            self.get_string(attrs, "name", empty=None)

            self.get_datetime(attrs, "start")
            self.get_datetime(attrs, "stop")
            self.get_timedelta_sec(attrs, "per_user_time")

            self.get_bool(attrs, "analysis_enabled")
            self.get_datetime(attrs, "analysis_start")
            self.get_datetime(attrs, "analysis_stop")

            assert attrs.get("name") is not None, \
                "No group name specified."

            # Update the group.
            group.set_attrs(attrs)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        self.try_commit()
        self.redirect(fallback_page)
