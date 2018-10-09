#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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

"""Submission-related handlers for AWS.

"""

import logging

from cms.db import Dataset, File, Submission
from cms.grading.languagemanager import get_language
from cmscommon.datetime import make_datetime
from .base import BaseHandler, FileHandler, require_permission


logger = logging.getLogger(__name__)


class SubmissionHandler(BaseHandler):
    """Shows the details of a submission. All data is already present
    in the list of the submissions of the task or of the user, but we
    need a place where to link messages like 'Submission 42 failed to
    compile please check'.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
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
    # We cannot use FileFromDigestHandler as it does not know how to
    # set the proper name (i.e., converting %l to the language).
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, file_id):
        sub_file = self.safe_get_item(File, file_id)
        submission = sub_file.submission

        real_filename = sub_file.filename
        if submission.language is not None:
            real_filename = real_filename.replace(
                ".%l", get_language(submission.language).source_extension)
        digest = sub_file.digest

        self.sql_session.close()
        self.fetch(digest, "text/plain", real_filename)


class SubmissionCommentHandler(BaseHandler):
    """Called when the admin comments on a submission.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, submission_id, dataset_id=None):
        submission = self.safe_get_item(Submission, submission_id)

        try:
            attrs = {"comment": submission.comment}
            self.get_string(attrs, "comment")
            submission.set_attrs(attrs)

        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))

        else:
            self.try_commit()

        if dataset_id is None:
            self.redirect(self.url("submission", submission_id))
        else:
            self.redirect(self.url("submission", submission_id, dataset_id))


class SubmissionOfficialStatusHandler(BaseHandler):
    """Called when the admin changes the official status of a submission."""
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, submission_id, dataset_id=None):
        submission = self.safe_get_item(Submission, submission_id)

        should_make_official = self.get_argument("official", "yes") == "yes"

        submission.official = should_make_official
        if self.try_commit():
            logger.info("Submission '%s' by user %s in contest %s has "
                        "been made %s",
                        submission.id,
                        submission.participation.user.username,
                        submission.participation.contest.name,
                        "official" if should_make_official else "unofficial")

        if dataset_id is None:
            self.redirect(self.url("submission", submission_id))
        else:
            self.redirect(self.url("submission", submission_id, dataset_id))
