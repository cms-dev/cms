#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Admin-related handlers for AWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

from cms.db import Admin
from cmscommon.crypto import hash_password
from cmscommon.datetime import make_datetime

from .base import BaseHandler, SimpleHandler, require_permission


logger = logging.getLogger(__name__)


def _admin_attrs(handler):
    """Return a dictionary with the arguments to define an admin

    handler (BaseHandler): the handler receiving the arguments.

    return (dict): a dictionary with the arguments to define an admin,
        based on those passed to handler.

    """
    attrs = {}

    handler.get_string(attrs, "username", empty=None)
    handler.get_string(attrs, "name", empty=None)

    assert attrs.get("username") is not None, "No username specified."
    assert attrs.get("name") is not None, "No admin name specified."

    # Get the password and translate it to an authentication, if present.
    handler.get_string(attrs, "password", empty=None)
    if attrs['password'] is not None:
        attrs["authentication"] = hash_password(attrs["password"])
    del attrs["password"]

    handler.get_bool(attrs, "permission_all")
    handler.get_bool(attrs, "permission_messaging")

    handler.get_bool(attrs, "enabled")

    return attrs


class AddAdminHandler(SimpleHandler("add_admin.html")):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = "/admins/add"

        try:
            attrs = _admin_attrs(self)
            assert attrs.get("authentication") is not None, \
                "Empty password not permitted."

            admin = Admin(**attrs)
            self.sql_session.add(admin)

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            self.redirect("/admins")
        else:
            self.redirect(fallback_page)


class AdminsHandler(BaseHandler):
    """Page to see all admins.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self):
        self.r_params = self.render_params()
        self.r_params["admins"] = self.sql_session.query(Admin)\
            .order_by(Admin.enabled.desc())\
            .order_by(Admin.username).all()
        self.render("admins.html", **self.r_params)


class AdminHandler(BaseHandler):
    """Admin handler, with a POST method to edit the admin.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, admin_id):
        admin = self.safe_get_item(Admin, admin_id)

        self.r_params = self.render_params()
        self.r_params["admin"] = admin
        self.render("admin.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, admin_id):
        # TODO: allow admins to edit themselves.
        admin = self.safe_get_item(Admin, admin_id)

        try:
            admin.set_attrs(_admin_attrs(self))

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect("/admin/%s" % admin_id)
            return

        if self.try_commit():
            logger.info("Admin %s updated.", admin.id)
            self.redirect("/admins")
        else:
            self.redirect("/admin/%s" % admin_id)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, admin_id):
        admin = self.safe_get_item(Admin, admin_id)

        self.sql_session.delete(admin)
        self.try_commit()

        # Page to redirect to.
        self.write("/admins")
