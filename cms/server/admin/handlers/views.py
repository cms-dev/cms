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

"""UI fragments for AdminWebServer

"""


import tornado.web


class ReevaluationButtons(tornado.web.UIModule):
    def render(self,
               url_root,
               contest_id=None,
               submission_id=None,
               dataset_id=None,
               participation_id=None,
               user_id=None):
        """Render reevaluation buttons for the given filters.

        Apart from contest_id, the parameters are mutually exclusive
        (i.e., only one can be provided). The only exception is when
        providing a submission, in which case a specific dataset can
        also be passed (the live one is used by default).

        url_root (unicode): path to the root of the server.
        contest_id (int): the id of the contest containing the
            submission results to invalidate.
        submission_id (int|None): id of the submission to invalidate,
            or None.
        dataset_id (int|None): id of the dataset to invalidate, or
            None.
        participation_id (int|None): id of the participation to
            invalidate, or None.
        user_id (int|None): id of the user (mandatory if participation_id
            is given, to write the redirect).

        """
        url = "%s/" % url_root
        invalidate_arguments = {}
        if submission_id is not None:
            # A specific submission for a specific dataset (if
            # specified) or for the live dataset.
            url += "submission/%s" % submission_id
            invalidate_arguments["submission_id"] = submission_id
            if dataset_id is not None:
                url += "/%s" % dataset_id
                invalidate_arguments["dataset_id"] = dataset_id
        elif participation_id is not None:
            # All submissions of the participation of this participation
            url += "contest/%s/user/%s" % (contest_id, user_id)
            invalidate_arguments["participation_id"] = participation_id
        elif dataset_id is not None:
            url += "dataset/%s" % dataset_id
            invalidate_arguments["dataset_id"] = dataset_id
        else:
            # Reevaluate all submission in the contest that ES is
            # watching.
            url += "contest/%s/submissions" % (contest_id)

        return self.render_string(
            "views/reevaluation_buttons.html",
            url_root=url_root,
            url=url,
            contest_id=contest_id,
            invalidate_arguments=invalidate_arguments)
