#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Luca Versari <veluca93@gmail.com>
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

"""Unit tests for submission details API handlers."""

import unittest
from unittest.mock import MagicMock

from cms import FEEDBACK_LEVEL_RESTRICTED, FEEDBACK_LEVEL_FULL
from cms.server.contest.handlers.api import (
    ApiSubmissionDetailsHandler,
    ApiSubmissionFullDetailsHandler,
)


class BaseApiHandlerTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.task = MagicMock()
        self.task.name = "my_task"
        self.task.feedback_level = FEEDBACK_LEVEL_RESTRICTED

        self.score_type = MagicMock()
        self.dataset = MagicMock()
        self.dataset.score_type_object = self.score_type
        self.task.active_dataset = self.dataset

        self.submission = MagicMock()
        self.submission.opaque_id = 1
        self.submission_result = MagicMock()
        self.submission_result.scored.return_value = True
        self.submission_result.score_details = [{"idx": 0, "score": 100.0}]
        self.submission_result.public_score_details = [{"idx": 0, "score": 0.0}]
        self.submission.get_result.return_value = self.submission_result
        self.submission.tokened.return_value = False

    def create_handler(
        self, handler_cls, impersonated=False, phase=0, current_user=True
    ):
        handler = handler_cls.__new__(handler_cls)
        handler.impersonated_by_admin = impersonated
        handler.contest = MagicMock()
        handler.contest.name = "test_contest"
        handler._current_user = MagicMock() if current_user else None
        handler.request = MagicMock()
        handler.request.arguments = {}
        handler.request.headers = {}
        handler.application = MagicMock()
        handler.application.service = MagicMock()
        handler.application.service.contest_id = 1
        handler.is_multi_contest = lambda: False
        handler.r_params = {"actual_phase": phase}
        handler.json_data = None
        handler.status_code = 200

        def fake_json(data, status_code=200):
            handler.json_data = data
            handler.status_code = status_code

        handler.json = fake_json

        def fake_get_task(name):
            return self.task if name == self.task.name else None

        def fake_get_submission(task, opaque_id):
            if task == self.task and str(opaque_id) == "1":
                return self.submission
            return None

        handler.get_task = fake_get_task
        handler.get_submission = fake_get_submission
        return handler


class TestApiSubmissionDetailsHandler(BaseApiHandlerTest):

    def test_task_not_found(self):
        handler = self.create_handler(ApiSubmissionDetailsHandler)
        handler.get("unknown_task", "1")
        self.assertEqual(handler.status_code, 404)
        self.assertEqual(handler.json_data, {"error": "Task not found"})

    def test_submission_not_found(self):
        handler = self.create_handler(ApiSubmissionDetailsHandler)
        handler.get("my_task", "999")
        self.assertEqual(handler.status_code, 404)
        self.assertEqual(handler.json_data, {"error": "Submission not found"})

    def test_contestant_restricted_details(self):
        self.score_type.get_json_details.return_value = [{"idx": 0, "filtered": True}]
        handler = self.create_handler(ApiSubmissionDetailsHandler, phase=0)
        handler.get("my_task", "1")

        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.json_data, {"details": [{"idx": 0, "filtered": True}]})
        self.score_type.get_json_details.assert_called_once_with(
            self.submission_result.public_score_details,
            FEEDBACK_LEVEL_RESTRICTED,
        )

    def test_contestant_tokened_details(self):
        self.submission.tokened.return_value = True
        self.score_type.get_json_details.return_value = [{"idx": 0, "tokened": True}]
        handler = self.create_handler(ApiSubmissionDetailsHandler, phase=0)
        handler.get("my_task", "1")

        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.json_data, {"details": [{"idx": 0, "tokened": True}]})
        self.score_type.get_json_details.assert_called_once_with(
            self.submission_result.score_details, FEEDBACK_LEVEL_RESTRICTED
        )

    def test_analysis_mode_details(self):
        self.submission.tokened.return_value = False
        self.score_type.get_json_details.return_value = [{"idx": 0, "analysis": True}]
        handler = self.create_handler(ApiSubmissionDetailsHandler, phase=3)
        handler.get("my_task", "1")

        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.json_data, {"details": [{"idx": 0, "analysis": True}]})
        self.score_type.get_json_details.assert_called_once_with(
            self.submission_result.score_details, FEEDBACK_LEVEL_FULL
        )


class TestApiSubmissionFullDetailsHandler(BaseApiHandlerTest):

    def test_not_impersonated_forbidden(self):
        handler = self.create_handler(
            ApiSubmissionFullDetailsHandler, impersonated=False
        )
        handler.get("my_task", "1")
        self.assertEqual(handler.status_code, 403)
        self.assertEqual(handler.json_data, {"error": "Admin impersonation required"})

    def test_impersonated_task_not_found(self):
        handler = self.create_handler(
            ApiSubmissionFullDetailsHandler, impersonated=True
        )
        handler.get("unknown_task", "1")
        self.assertEqual(handler.status_code, 404)

    def test_impersonated_submission_not_found(self):
        handler = self.create_handler(
            ApiSubmissionFullDetailsHandler, impersonated=True
        )
        handler.get("my_task", "999")
        self.assertEqual(handler.status_code, 404)

    def test_impersonated_returns_full_details(self):
        self.score_type.get_json_details.return_value = [{"idx": 0, "full": True}]
        handler = self.create_handler(
            ApiSubmissionFullDetailsHandler, impersonated=True
        )
        handler.get("my_task", "1")

        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.json_data, {"details": [{"idx": 0, "full": True}]})
        self.score_type.get_json_details.assert_called_once_with(
            self.submission_result.score_details, FEEDBACK_LEVEL_FULL
        )


if __name__ == "__main__":
    unittest.main()
