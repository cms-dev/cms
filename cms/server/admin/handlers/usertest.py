#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""User test related handlers for AWS.

"""

from cms.db import Dataset, UserTestFile, UserTest
from cms.grading.languagemanager import get_language

from .base import BaseHandler, FileHandler, require_permission


class UserTestHandler(BaseHandler):
    """Shows the details of a user test."""
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, user_test_id, dataset_id=None):
        user_test = self.safe_get_item(UserTest, user_test_id)
        task = user_test.task
        self.contest = task.contest

        if dataset_id is not None:
            dataset = self.safe_get_item(Dataset, dataset_id)
        else:
            dataset = task.active_dataset
        assert dataset.task is task

        self.r_params = self.render_params()
        self.r_params["ut"] = user_test
        self.r_params["active_dataset"] = task.active_dataset
        self.r_params["shown_dataset"] = dataset
        self.r_params["datasets"] = \
            self.sql_session.query(Dataset)\
                            .filter(Dataset.task == task)\
                            .order_by(Dataset.description).all()
        self.render("user_test.html", **self.r_params)


class UserTestFileHandler(FileHandler):
    """Shows a user test file."""
    # We cannot use FileFromDigestHandler as it does not know how to
    # set the proper name (i.e., converting %l to the language).
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, file_id):
        user_test_file = self.safe_get_item(UserTestFile, file_id)
        user_test = user_test_file.user_test

        real_filename = user_test_file.filename
        if user_test.language is not None:
            real_filename = real_filename.replace(
                ".%l", get_language(user_test.language).source_extension)
        digest = user_test_file.digest

        self.sql_session.close()
        self.fetch(digest, "text/plain", real_filename)
