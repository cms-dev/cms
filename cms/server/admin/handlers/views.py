#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016-2017 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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
               url,
               contest_id=None,
               submission_id=None,
               dataset_id=None,
               participation_id=None,
               user_id=None):
        """Render reevaluation buttons for the given filters.

        These are the possible configuration of not-none arguments
        received (other might work but needs to be checked):
        - contest_id: all submissions in the contest watched by ES or
          SS are invalidated (regardless of the actual id passed);
        - dataset_id: all submission for the task identified by the
          dataset are reevaluated for that dataset;
        - submission_id, dataset_id: the submission is reevaluated for
          the given dataset;
        - participation_id, user_id, contest_id: all submissions for
          the participation are reevaluated, for all datasets (user_id
          and contest_id are used only for rendering the correct
          link, as they are implied by the participation_id).

        url (function): a function that takes some URL components and
            encodes them into an URL string.
        contest_id (int|None): the id of the contest containing the
            submission results to invalidate, or None not to filter
            for contest.
        submission_id (int|None): id of the submission to invalidate,
            or None.
        dataset_id (int|None): id of the dataset to invalidate, or
            None.
        participation_id (int|None): id of the participation to
            invalidate, or None.
        user_id (int|None): id of the user (mandatory if participation_id
            is given, to write the redirect).

        """
        components = []
        invalidate_arguments = {}
        if submission_id is not None:
            # A specific submission for a specific dataset (if
            # specified) or for the live dataset.
            components += ["submission", submission_id]
            invalidate_arguments["submission_id"] = submission_id
            if dataset_id is not None:
                components += [dataset_id]
                invalidate_arguments["dataset_id"] = dataset_id
        elif participation_id is not None:
            # All submissions of the participation.
            components += ["contest", contest_id, "user", user_id, "edit"]
            invalidate_arguments["participation_id"] = participation_id
        elif dataset_id is not None:
            components += ["dataset", dataset_id]
            invalidate_arguments["dataset_id"] = dataset_id
        else:
            # Reevaluate all submission in the specified contest.
            # TODO: block request to invalidate contests different
            # from those running in ES/SS.
            components += ["contest", contest_id, "submissions"]
            invalidate_arguments["contest_id"] = contest_id

        return self.render_string(
            "views/reevaluation_buttons.html",
            url=url,
            next_page=url(*components),
            invalidate_arguments=invalidate_arguments)
