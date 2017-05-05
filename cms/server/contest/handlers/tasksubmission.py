#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
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

"""Submission-related handlers for CWS for a specific task.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import pickle
import re

import tornado.web

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from cms import config
from cms.db import File, Submission, SubmissionResult, Task, Token
from cms.grading.languagemanager import get_language
from cms.grading.scoretypes import get_score_type
from cms.grading.tasktypes import get_task_type
from cms.server import actual_phase_required, multi_contest
from cmscommon.archive import Archive
from cmscommon.crypto import encrypt_number
from cmscommon.datetime import make_timestamp
from cmscommon.mimetypes import get_type_for_file_name

from .contest import ContestHandler, FileHandler, NOTIFICATION_ERROR, \
    NOTIFICATION_SUCCESS, NOTIFICATION_WARNING


logger = logging.getLogger(__name__)


class SubmitHandler(ContestHandler):
    """Handles the received submissions.

    """

    def _send_error(self, subject, text):
        """Shorthand for sending a notification and redirecting."""
        logger.warning("Sent error: `%s' - `%s'", subject, text)
        self.application.service.add_notification(
            self.current_user.user.username,
            self.timestamp,
            subject,
            text,
            NOTIFICATION_ERROR)
        self.redirect(self.contest_url(*self.fallback_page))

    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def post(self, task_name):
        participation = self.current_user
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        self.fallback_page = ["tasks", task.name, "submissions"]

        # Alias for easy access
        contest = self.contest

        # Enforce maximum number of submissions
        try:
            if contest.max_submission_number is not None:
                submission_c = self.sql_session\
                    .query(func.count(Submission.id))\
                    .join(Submission.task)\
                    .filter(Task.contest == contest)\
                    .filter(Submission.participation == participation)\
                    .scalar()
                if submission_c >= contest.max_submission_number and \
                        not self.current_user.unrestricted:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d submissions among all tasks.") %
                        contest.max_submission_number)
            if task.max_submission_number is not None:
                submission_t = self.sql_session\
                    .query(func.count(Submission.id))\
                    .filter(Submission.task == task)\
                    .filter(Submission.participation == participation)\
                    .scalar()
                if submission_t >= task.max_submission_number and \
                        not self.current_user.unrestricted:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d submissions on this task.") %
                        task.max_submission_number)
        except ValueError as error:
            self._send_error(
                self._("Too many submissions!"), error.message)
            return

        # Enforce minimum time between submissions
        try:
            if contest.min_submission_interval is not None:
                last_submission_c = self.sql_session.query(Submission)\
                    .join(Submission.task)\
                    .filter(Task.contest == contest)\
                    .filter(Submission.participation == participation)\
                    .order_by(Submission.timestamp.desc())\
                    .first()
                if last_submission_c is not None and \
                        self.timestamp - last_submission_c.timestamp < \
                        contest.min_submission_interval and \
                        not self.current_user.unrestricted:
                    raise ValueError(
                        self._("Among all tasks, you can submit again "
                               "after %d seconds from last submission.") %
                        contest.min_submission_interval.total_seconds())
            # We get the last submission even if we may not need it
            # for min_submission_interval because we may need it later,
            # in case this is a ALLOW_PARTIAL_SUBMISSION task.
            last_submission_t = self.sql_session.query(Submission)\
                .filter(Submission.task == task)\
                .filter(Submission.participation == participation)\
                .order_by(Submission.timestamp.desc())\
                .first()
            if task.min_submission_interval is not None:
                if last_submission_t is not None and \
                        self.timestamp - last_submission_t.timestamp < \
                        task.min_submission_interval and \
                        not self.current_user.unrestricted:
                    raise ValueError(
                        self._("For this task, you can submit again "
                               "after %d seconds from last submission.") %
                        task.min_submission_interval.total_seconds())
        except ValueError as error:
            self._send_error(
                self._("Submissions too frequent!"), error.message)
            return

        # Required files from the user.
        required = set([sfe.filename for sfe in task.submission_format])

        # Ensure that the user did not submit multiple files with the
        # same name.
        if any(len(filename) != 1 for filename in self.request.files.values()):
            self._send_error(
                self._("Invalid submission format!"),
                self._("Please select the correct files."))
            return

        # If the user submitted an archive, extract it and use content
        # as request.files. But only valid for "output only" (i.e.,
        # not for submissions requiring a programming language
        # identification).
        if len(self.request.files) == 1 and \
                self.request.files.keys()[0] == "submission":
            if any(filename.endswith(".%l") for filename in required):
                self._send_error(
                    self._("Invalid submission format!"),
                    self._("Please select the correct files."),
                    task)
                return
            archive_data = self.request.files["submission"][0]
            del self.request.files["submission"]

            # Create the archive.
            archive = Archive.from_raw_data(archive_data["body"])

            if archive is None:
                self._send_error(
                    self._("Invalid archive format!"),
                    self._("The submitted archive could not be opened."))
                return

            # Extract the archive.
            unpacked_dir = archive.unpack()
            for name in archive.namelist():
                filename = os.path.basename(name)
                body = open(os.path.join(unpacked_dir, filename), "r").read()
                self.request.files[filename] = [{
                    'filename': filename,
                    'body': body
                }]

            archive.cleanup()

        # This ensure that the user sent one file for every name in
        # submission format and no more. Less is acceptable if task
        # type says so.
        task_type = get_task_type(dataset=task.active_dataset)
        provided = set(self.request.files.keys())
        if not (required == provided or (task_type.ALLOW_PARTIAL_SUBMISSION
                                         and required.issuperset(provided))):
            self._send_error(
                self._("Invalid submission format!"),
                self._("Please select the correct files."))
            return

        # Add submitted files. After this, files is a dictionary indexed
        # by *our* filenames (something like "output01.txt" or
        # "taskname.%l", and whose value is a couple
        # (user_assigned_filename, content).
        files = {}
        for uploaded, data in self.request.files.iteritems():
            files[uploaded] = (data[0]["filename"], data[0]["body"])

        # Read the submission language provided in the request; we
        # integrate it with the language fetched from the previous
        # submission (if we use it) and later make sure it is
        # recognized and allowed.
        submission_lang = self.get_argument("language", None)
        need_lang = any(our_filename.find(".%l") != -1
                        for our_filename in files)

        # If we allow partial submissions, we implicitly recover the
        # non-submitted files from the previous submission (if it has
        # the same programming language of the current one), and put
        # them in file_digests (since they are already in FS).
        file_digests = {}
        if task_type.ALLOW_PARTIAL_SUBMISSION and \
                last_submission_t is not None and \
                (submission_lang is None or
                 submission_lang == last_submission_t.language):
            submission_lang = last_submission_t.language
            for filename in required.difference(provided):
                if filename in last_submission_t.files:
                    file_digests[filename] = \
                        last_submission_t.files[filename].digest

        # Throw an error if task needs a language, but we don't have
        # it or it is not allowed / recognized.
        if need_lang:
            error = None
            if submission_lang is None:
                error = self._("Cannot recognize the submission language.")
            elif submission_lang not in contest.languages:
                error = self._("Language %s not allowed in this contest.") \
                    % submission_lang
            if error is not None:
                self._send_error(self._("Invalid submission!"), error)
                return

        # Check if submitted files are small enough.
        if any([len(f[1]) > config.max_submission_length
                for f in files.values()]):
            self._send_error(
                self._("Submission too big!"),
                self._("Each source file must be at most %d bytes long.") %
                config.max_submission_length)
            return

        # All checks done, submission accepted.

        # Attempt to store the submission locally to be able to
        # recover a failure.
        if config.submit_local_copy:
            try:
                path = os.path.join(
                    config.submit_local_copy_path.replace("%s",
                                                          config.data_dir),
                    participation.user.username)
                if not os.path.exists(path):
                    os.makedirs(path)
                # Pickle in ASCII format produces str, not unicode,
                # therefore we open the file in binary mode.
                with io.open(
                        os.path.join(path,
                                     "%d" % make_timestamp(self.timestamp)),
                        "wb") as file_:
                    pickle.dump((self.contest.id,
                                 participation.user.id,
                                 task.id,
                                 files), file_)
            except Exception as error:
                logger.warning("Submission local copy failed.", exc_info=True)

        # We now have to send all the files to the destination...
        try:
            for filename in files:
                digest = self.application.service.file_cacher.put_file_content(
                    files[filename][1],
                    "Submission file %s sent by %s at %d." % (
                        filename, participation.user.username,
                        make_timestamp(self.timestamp)))
                file_digests[filename] = digest

        # In case of error, the server aborts the submission
        except Exception as error:
            logger.error("Storage failed! %s", error)
            self._send_error(
                self._("Submission storage failed!"),
                self._("Please try again."))
            return

        # All the files are stored, ready to submit!
        logger.info("All files stored for submission sent by %s",
                    participation.user.username)

        # Only set the official bit when the user can compete and we are not in
        # analysis mode.
        official = self.r_params["actual_phase"] == 0

        submission = Submission(self.timestamp,
                                submission_lang,
                                task=task,
                                participation=participation,
                                official=official)

        for filename, digest in file_digests.items():
            self.sql_session.add(File(filename, digest, submission=submission))
        self.sql_session.add(submission)
        self.sql_session.commit()
        self.application.service.evaluation_service.new_submission(
            submission_id=submission.id)
        self.application.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Submission received"),
            self._("Your submission has been received "
                   "and is currently being evaluated."),
            NOTIFICATION_SUCCESS)

        # The argument (encripted submission id) is not used by CWS
        # (nor it discloses information to the user), but it is useful
        # for automatic testing to obtain the submission id).
        self.redirect(self.contest_url(
            *self.fallback_page, submission_id=encrypt_number(submission.id)))


class TaskSubmissionsHandler(ContestHandler):
    """Shows the data of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name):
        participation = self.current_user

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submissions = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)\
            .filter(Submission.task == task)\
            .options(joinedload(Submission.token))\
            .options(joinedload(Submission.results))\
            .all()

        submissions_left_contest = None
        if self.contest.max_submission_number is not None:
            submissions_c = self.sql_session\
                .query(func.count(Submission.id))\
                .join(Submission.task)\
                .filter(Task.contest == self.contest)\
                .filter(Submission.participation == participation)\
                .scalar()
            submissions_left_contest = \
                self.contest.max_submission_number - submissions_c

        submissions_left_task = None
        if task.max_submission_number is not None:
            submissions_left_task = \
                task.max_submission_number - len(submissions)

        submissions_left = submissions_left_contest
        if submissions_left_task is not None and \
            (submissions_left_contest is None or
             submissions_left_contest > submissions_left_task):
            submissions_left = submissions_left_task

        # Make sure we do not show negative value if admins changed
        # the maximum
        if submissions_left is not None:
            submissions_left = max(0, submissions_left)

        self.render("task_submissions.html",
                    task=task, submissions=submissions,
                    submissions_left=submissions_left,
                    submissions_download_allowed=
                        self.contest.submissions_download_allowed,
                    **self.r_params)


class SubmissionStatusHandler(ContestHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name, submission_num):
        participation = self.current_user

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1)\
            .first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        sr = submission.get_result(task.active_dataset)
        data = dict()

        if sr is None:
            # implicit compiling state while result is not created
            data["status"] = SubmissionResult.COMPILING
        else:
            data["status"] = sr.get_status()

        if data["status"] == SubmissionResult.COMPILING:
            data["status_text"] = self._("Compiling...")
        elif data["status"] == SubmissionResult.COMPILATION_FAILED:
            data["status_text"] = "%s <a class=\"details\">%s</a>" % (
                self._("Compilation failed"), self._("details"))
        elif data["status"] == SubmissionResult.EVALUATING:
            data["status_text"] = self._("Evaluating...")
        elif data["status"] == SubmissionResult.SCORING:
            data["status_text"] = self._("Scoring...")
        elif data["status"] == SubmissionResult.SCORED:
            data["status_text"] = "%s <a class=\"details\">%s</a>" % (
                self._("Evaluated"), self._("details"))

            score_type = get_score_type(dataset=task.active_dataset)
            if score_type.max_public_score > 0:
                data["max_public_score"] = \
                    round(score_type.max_public_score, task.score_precision)
                data["public_score"] = \
                    round(sr.public_score, task.score_precision)
                data["public_score_message"] = score_type.format_score(
                    sr.public_score, score_type.max_public_score,
                    sr.public_score_details, task.score_precision, self._)
            if submission.token is not None:
                data["max_score"] = \
                    round(score_type.max_score, task.score_precision)
                data["score"] = \
                    round(sr.score, task.score_precision)
                data["score_message"] = score_type.format_score(
                    sr.score, score_type.max_score,
                    sr.score_details, task.score_precision, self._)

        self.write(data)


class SubmissionDetailsHandler(ContestHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name, submission_num):
        participation = self.current_user

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1)\
            .first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        sr = submission.get_result(task.active_dataset)
        score_type = get_score_type(dataset=task.active_dataset)

        details = None
        if sr is not None:
            if submission.tokened():
                details = sr.score_details
            else:
                details = sr.public_score_details

            if sr.scored():
                details = score_type.get_html_details(details, self._)
            else:
                details = None

        self.render("submission_details.html",
                    sr=sr,
                    details=details)


class SubmissionFileHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name, submission_num, filename):
        if not self.contest.submissions_download_allowed:
            raise tornado.web.HTTPError(404)

        participation = self.current_user

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1)\
            .first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        # The following code assumes that submission.files is a subset
        # of task.submission_format. CWS will always ensure that for new
        # submissions, yet, if the submission_format changes during the
        # competition, this may not hold anymore for old submissions.

        # filename is the name used by the browser, hence is something
        # like 'foo.c' (and the extension is CMS's preferred extension
        # for the language). To retrieve the right file, we need to
        # decode it to 'foo.%l'.
        stored_filename = filename
        if submission.language is not None:
            extension = get_language(submission.language).source_extension
            stored_filename = re.sub(r'%s$' % extension, '.%l', filename)

        if stored_filename not in submission.files:
            raise tornado.web.HTTPError(404)

        digest = submission.files[stored_filename].digest
        self.sql_session.close()

        mimetype = get_type_for_file_name(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(digest, mimetype, filename)


class UseTokenHandler(ContestHandler):
    """Called when the user try to use a token on a submission.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def post(self, task_name, submission_num):
        participation = self.current_user

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        fallback_page = \
            self.contest_url("tasks", task.name, "submissions")

        submission = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1)\
            .first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        # Don't trust the user, check again if (s)he can really play
        # the token.
        tokens_available = self.contest.tokens_available(
            participation, task, self.timestamp)
        if tokens_available[0] == 0 or tokens_available[2] is not None:
            logger.warning("User %s tried to play a token when they "
                           "shouldn't.", participation.user.username)
            # Add "no luck" notification
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Token request discarded"),
                self._("Your request has been discarded because you have no "
                       "tokens available."),
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        if submission.token is None:
            token = Token(self.timestamp, submission=submission)
            self.sql_session.add(token)
            self.sql_session.commit()
        else:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Token request discarded"),
                self._("Your request has been discarded because you already "
                       "used a token on that submission."),
                NOTIFICATION_WARNING)
            self.redirect(fallback_page)
            return

        # Inform ProxyService and eventually the ranking that the
        # token has been played.
        self.application.service.proxy_service.submission_tokened(
            submission_id=submission.id)

        logger.info("Token played by user %s on task %s.",
                    participation.user.username, task.name)

        # Add "All ok" notification.
        self.application.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Token request received"),
            self._("Your request has been received "
                   "and applied to the submission."),
            NOTIFICATION_SUCCESS)

        self.redirect(fallback_page)
