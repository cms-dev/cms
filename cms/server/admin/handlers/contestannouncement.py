#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Announcement-related handlers for AWS for a specific contest.

"""

import tornado.web

from cms.db import Contest, Announcement
from cmscommon.datetime import make_datetime
from .base import BaseHandler, require_permission


class AddAnnouncementHandler(BaseHandler):
    """Called to actually add an announcement

    """
    @require_permission(BaseHandler.PERMISSION_MESSAGING)
    def post(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            ann = Announcement(make_datetime(), subject, text,
                               contest=self.contest, admin=self.current_user)
            self.sql_session.add(ann)
            self.try_commit()
        else:
            self.service.add_notification(
                make_datetime(), "Subject is mandatory.", "")
        self.redirect(self.url("contest", contest_id, "announcements"))


class AnnouncementHandler(BaseHandler):
    """Called to remove an announcement.

    """
    # No page to show a single attachment.

    @require_permission(BaseHandler.PERMISSION_MESSAGING)
    def delete(self, contest_id, ann_id):
        ann = self.safe_get_item(Announcement, ann_id)
        self.contest = self.safe_get_item(Contest, contest_id)

        # Protect against URLs providing incompatible parameters.
        if self.contest is not ann.contest:
            raise tornado.web.HTTPError(404)

        self.sql_session.delete(ann)
        self.try_commit()

        # Page to redirect to.
        self.write("announcements")
