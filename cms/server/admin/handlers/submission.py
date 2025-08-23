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

import json
import logging
import difflib

from cms.db import Dataset, File, Submission
from cms.grading.languagemanager import safe_get_lang_filename
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

        real_filename = safe_get_lang_filename(submission.language, sub_file.filename)
        digest = sub_file.digest

        self.sql_session.close()
        self.fetch(digest, "text/plain", real_filename)


class SubmissionDiffHandler(BaseHandler):
    """Shows a diff between two submissions.
    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, old_id, new_id):
        sub_old = Submission.get_from_id(old_id, self.sql_session)
        sub_new = Submission.get_from_id(new_id, self.sql_session)

        self.set_header("Content-type", "application/json; charset=utf-8")
        resp = {
            'message': None,
            'files': []
        }

        if sub_old is None or sub_new is None:
            missing_id = old_id if sub_old is None else new_id
            resp['message'] = f"Submission ID {missing_id} not found."
            self.write(json.dumps(resp))
            return

        if sub_old.task_id == sub_new.task_id:
            files_to_compare = sub_old.task.submission_format
            old_files = sub_old.files
            new_files = sub_new.files
        elif len(sub_old.files) == 1 and len(sub_new.files) == 1:
            old_file = list(sub_old.files.values())[0]
            old_files = {"submission.%l": old_file}
            new_file = list(sub_new.files.values())[0]
            new_files = {"submission.%l": new_file}
            files_to_compare = ["submission.%l"]
        else:
            resp['message'] = "Cannot compare submissions: they are for " \
                "different tasks and have more than 1 file."
            self.write(json.dumps(resp))
            return

        result_files = []
        for fname in files_to_compare:
            if ".%l" in fname:
                if sub_old.language == sub_new.language and sub_old.language is not None:
                    real_fname = safe_get_lang_filename(sub_old.language, fname)
                else:
                    real_fname = fname.replace(".%l", ".txt")
            else:
                real_fname = fname

            def get_file(x, which):
                if fname not in x:
                    return None, f"File not present in {which} submission"
                digest = x[fname].digest
                file_bin = self.service.file_cacher.get_file_content(digest)
                if len(file_bin) > 1000000:
                    return None, f"{which} file is too big to diff".capitalize()
                file_lines = file_bin.decode(errors='replace').splitlines()
                if len(file_lines) > 5000:
                    return None, f"{which} file has too many lines to diff".capitalize()
                return file_lines, None

            old_content, old_status = get_file(old_files, "old")
            if old_status:
                result_files.append({"fname": real_fname, "status": old_status})
                continue
            new_content, new_status = get_file(new_files, "new")
            if new_status:
                result_files.append({"fname": real_fname, "status": new_status})
                continue

            if old_content == new_content:
                result_files.append({"fname": real_fname, "status": "No changes"})
            else:
                diff_iter = difflib.unified_diff(old_content, new_content, lineterm='')
                # skip the "---" and "+++" lines.
                next(diff_iter)
                next(diff_iter)
                diff = '\n'.join(diff_iter)

                result_files.append({"fname": real_fname, "diff": diff})

        resp['files'] = result_files
        self.write(json.dumps(resp))


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
