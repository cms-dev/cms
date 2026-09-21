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

"""Unit tests for SolutionChecker."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from cmscontrib.SolutionChecker import SolutionChecker


class TestSolutionChecker(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.checker = SolutionChecker(
            base_url="http://localhost:8888/contest",
            username="user",
            password="pwd",
        )

    def test_check_subtasks_accepted(self):
        # Full score -> pass
        details = [
            {
                "idx": 0,
                "score": 20.0,
                "max_score": 20.0,
                "score_fraction": 1.0,
                "testcases": [{"outcome": "Correct"}],
            }
        ]
        self.assertEqual(self.checker.check_subtasks(details, ["Accepted"]), [])

        # Partial score -> fail
        details_partial = [
            {
                "idx": 0,
                "score": 10.0,
                "max_score": 20.0,
                "score_fraction": 0.5,
                "testcases": [{"outcome": "Partially correct"}],
            }
        ]
        errors = self.checker.check_subtasks(details_partial, ["Accepted"])
        self.assertEqual(len(errors), 1)
        self.assertIn("expected Accepted", errors[0])

    def test_check_subtasks_zero(self):
        # 0 score -> pass
        details = [
            {
                "idx": 0,
                "score": 0.0,
                "max_score": 20.0,
                "score_fraction": 0.0,
                "testcases": [{"outcome": "Not correct"}],
            }
        ]
        self.assertEqual(self.checker.check_subtasks(details, ["Zero"]), [])

        # Positive score -> fail
        details_pos = [
            {
                "idx": 0,
                "score": 5.0,
                "max_score": 20.0,
                "score_fraction": 0.25,
                "testcases": [{"outcome": "Partially correct"}],
            }
        ]
        errors = self.checker.check_subtasks(details_pos, ["Zero"])
        self.assertEqual(len(errors), 1)
        self.assertIn("expected Zero", errors[0])

    def test_check_subtasks_partial_score(self):
        details = [
            {
                "idx": 0,
                "score": 10.0,
                "max_score": 20.0,
                "score_fraction": 0.5,
            }
        ]
        self.assertEqual(self.checker.check_subtasks(details, ["PartialScore"]), [])

        # 0 score -> fail
        details_zero = [
            {
                "idx": 0,
                "score": 0.0,
                "max_score": 20.0,
                "score_fraction": 0.0,
            }
        ]
        self.assertEqual(
            len(self.checker.check_subtasks(details_zero, ["PartialScore"])), 1
        )

        # Full score -> fail
        details_full = [
            {
                "idx": 0,
                "score": 20.0,
                "max_score": 20.0,
                "score_fraction": 1.0,
            }
        ]
        self.assertEqual(
            len(self.checker.check_subtasks(details_full, ["PartialScore"])), 1
        )

    def test_check_subtasks_wrong_answer(self):
        details = [
            {
                "idx": 0,
                "score": 0.0,
                "max_score": 20.0,
                "testcases": [
                    {"outcome": "Correct", "text": ["Output is correct"]},
                    {
                        "outcome": "Not correct",
                        "text": ["Output isn't correct"],
                    },
                ],
            }
        ]
        self.assertEqual(self.checker.check_subtasks(details, ["WrongAnswer"]), [])

        # All correct -> fail, reports got statuses ['Accepted']
        details_correct = [
            {
                "idx": 0,
                "score": 20.0,
                "max_score": 20.0,
                "testcases": [
                    {"outcome": "Correct", "text": ["Output is correct"]},
                ],
            }
        ]
        errors = self.checker.check_subtasks(details_correct, ["WrongAnswer"])
        self.assertEqual(len(errors), 1)
        self.assertIn("expected WrongAnswer, got statuses ['Accepted']", errors[0])

    def test_check_subtasks_time_limit_exceeded(self):
        details = [
            {
                "idx": 0,
                "testcases": [
                    {
                        "outcome": "Not correct",
                        "text": ["Execution timed out"],
                        "time_limit_was_exceeded": True,
                    }
                ],
            }
        ]
        self.assertEqual(
            self.checker.check_subtasks(details, ["TimeLimitExceeded"]), []
        )

        # No TLE -> fail, reports got statuses ['WrongAnswer']
        details_no_tle = [
            {
                "idx": 0,
                "testcases": [
                    {
                        "outcome": "Not correct",
                        "text": ["Output isn't correct"],
                    }
                ],
            }
        ]
        errors = self.checker.check_subtasks(details_no_tle, ["TimeLimitExceeded"])
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "expected TimeLimitExceeded, got statuses ['WrongAnswer']",
            errors[0],
        )

    def test_check_subtasks_wall_time_limit_exceeded(self):
        details = [
            {
                "idx": 0,
                "testcases": [
                    {
                        "outcome": "Not correct",
                        "text": ["Execution timed out (wall clock limit exceeded)"],
                    }
                ],
            }
        ]
        self.assertEqual(
            self.checker.check_subtasks(details, ["WallTimeLimitExceeded"]), []
        )

    def test_check_subtasks_runtime_error(self):
        details_signal = [
            {
                "idx": 0,
                "testcases": [
                    {
                        "outcome": "Not correct",
                        "text": ["Execution killed by signal"],
                    }
                ],
            }
        ]
        self.assertEqual(
            self.checker.check_subtasks(details_signal, ["RuntimeError"]), []
        )

        details_returncode = [
            {
                "idx": 0,
                "testcases": [
                    {
                        "outcome": "Not correct",
                        "text": [
                            "Execution failed because the return code was " "nonzero"
                        ],
                    }
                ],
            }
        ]
        self.assertEqual(
            self.checker.check_subtasks(details_returncode, ["RuntimeError"]),
            [],
        )

    def test_check_subtasks_multiple_statuses(self):
        # Subtask with multiple different testcase failures
        details = [
            {
                "idx": 0,
                "score": 0.0,
                "max_score": 20.0,
                "testcases": [
                    {"outcome": "Correct", "text": ["Output is correct"]},
                    {
                        "outcome": "Not correct",
                        "text": ["Execution killed by signal 11"],
                    },
                    {
                        "outcome": "Not correct",
                        "text": ["Output isn't correct"],
                    },
                ],
            }
        ]
        # Expecting RuntimeError -> pass (since RuntimeError is in the set)
        self.assertEqual(self.checker.check_subtasks(details, ["RuntimeError"]), [])
        # Expecting WrongAnswer -> pass (since WrongAnswer is in the set)
        self.assertEqual(self.checker.check_subtasks(details, ["WrongAnswer"]), [])
        # Expecting TimeLimitExceeded -> fail, reports actual statuses
        errors = self.checker.check_subtasks(details, ["TimeLimitExceeded"])
        self.assertEqual(len(errors), 1)
        self.assertIn(
            "expected TimeLimitExceeded, got statuses "
            "['Accepted', 'RuntimeError', 'WrongAnswer']",
            errors[0],
        )

    def test_check_subtasks_null_and_unknown(self):
        details = [{"idx": 0, "score": 10.0}]
        # null / None check -> pass
        self.assertEqual(self.checker.check_subtasks(details, [None]), [])

        # Unknown check -> fail
        errors = self.checker.check_subtasks(details, ["InvalidCheckType"])
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown check type", errors[0])

    def test_has_slow_testcases(self):
        time_limit = 1.0
        # Testcase took 0.6s (> 0.5 * time_limit) on positive subtask -> True
        details_slow = [
            {
                "idx": 0,
                "score": 10.0,
                "testcases": [{"time": 0.6}],
            }
        ]
        self.assertTrue(self.checker.has_slow_testcases(details_slow, time_limit))

        # Testcase took 0.4s (<= 0.5 * time_limit) -> False
        details_fast = [
            {
                "idx": 0,
                "score": 10.0,
                "testcases": [{"time": 0.4}],
            }
        ]
        self.assertFalse(self.checker.has_slow_testcases(details_fast, time_limit))

        # Testcase took 0.8s on a 0-score subtask -> False
        details_zero_score = [
            {
                "idx": 0,
                "score": 0.0,
                "score_fraction": 0.0,
                "testcases": [{"time": 0.8}],
            }
        ]
        self.assertFalse(
            self.checker.has_slow_testcases(details_zero_score, time_limit)
        )
        # Test that user's 0-score / sample subtask with times does not warn
        details_sample = [
            {
                "idx": 0,
                "score_fraction": 1.0,
                "score": 0.0,
                "max_score": 0.0,
                "testcases": [
                    {
                        "idx": "000",
                        "outcome": "Correct",
                        "text": ["Output is correct"],
                        "time": 0.001,
                        "time_limit": 1.0,
                        "time_limit_was_exceeded": False,
                        "memory": 262144,
                    }
                ],
            }
        ]
        self.assertFalse(self.checker.has_slow_testcases(details_sample, time_limit))

        # Truly missing times -> warns
        details_no_times = [
            {
                "idx": 0,
                "score": 10.0,
                "testcases": [{"outcome": "Correct"}],
            }
        ]
        with self.assertLogs("cmscontrib.SolutionChecker", level="WARNING") as cm:
            self.assertFalse(
                self.checker.has_slow_testcases(details_no_times, time_limit)
            )
        self.assertTrue(any("No testcase times found" in msg for msg in cm.output))

        # Flat testcase structure (e.g. Sum score type)
        details_flat = [{"idx": 0, "time": 0.8}]
        self.assertTrue(self.checker.has_slow_testcases(details_flat, time_limit))

    def test_login_validations(self):
        # Password without username
        c1 = SolutionChecker(base_url="http://localhost:8888", password="pwd")
        with self.assertRaises(ValueError) as ctx:
            c1.login()
        self.assertIn("Password provided without username", str(ctx.exception))

        # Username without password (no admin token)
        c2 = SolutionChecker(base_url="http://localhost:8888", username="user")
        with self.assertRaises(ValueError) as ctx:
            c2.login()
        self.assertIn("provided without password", str(ctx.exception))

        # Admin token without username
        c3 = SolutionChecker(base_url="http://localhost:8888", admin_token="admintoken")
        with self.assertRaises(ValueError) as ctx:
            c3.login()
        self.assertIn("Admin token requires --username", str(ctx.exception))

        # No credentials -> IP autologin
        c4 = SolutionChecker(base_url="http://localhost:8888")
        c4.login()
        self.assertEqual(c4.auth_header, {})

    @patch("requests.Session.post")
    def test_login_admin_token(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"login_data": "signed_cookie"}
        mock_post.return_value = mock_response

        checker = SolutionChecker(
            base_url="http://localhost:8888",
            username="marago",
            admin_token="admintoken",
        )
        checker.login()
        self.assertEqual(checker.auth_header, {"X-CMS-Authorization": "signed_cookie"})
        mock_post.assert_called_with(
            "http://localhost:8888/api/login",
            data={"admin_token": "admintoken", "username": "marago"},
        )

    @patch("requests.Session.post")
    def test_login_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Invalid credentials"}
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        checker = SolutionChecker(
            base_url="http://localhost:8888",
            username="user",
            password="wrong_password",
        )
        with self.assertRaises(RuntimeError) as ctx:
            checker.login()
        self.assertIn("Invalid credentials", str(ctx.exception))

    def test_extract_error_message(self):
        # JSON response with error field
        r1 = MagicMock()
        r1.json.return_value = {"error": "The contest is not open"}
        err1 = requests.exceptions.HTTPError(response=r1)
        self.assertEqual(
            SolutionChecker._extract_error_message(err1),
            "The contest is not open",
        )

        # Plain text response
        r2 = MagicMock()
        r2.json.side_effect = Exception("Not JSON")
        r2.text = "Forbidden"
        err2 = requests.exceptions.HTTPError(response=r2)
        self.assertEqual(SolutionChecker._extract_error_message(err2), "Forbidden")

    @patch("requests.Session.get")
    def test_get_submission_details_endpoints(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"details": [{"idx": 0}]}
        mock_get.return_value = mock_response

        # Without admin token -> calls /details
        checker_user = SolutionChecker(
            base_url="http://localhost:8888/contest",
            username="u",
            password="p",
        )
        res = checker_user.get_submission_details("task1", "123")
        self.assertEqual(res, [{"idx": 0}])
        mock_get.assert_called_with(
            "http://localhost:8888/contest/api/task1/submissions/123/details",
            headers={},
        )

        # With admin token -> calls /full_details
        checker_admin = SolutionChecker(
            base_url="http://localhost:8888/contest",
            username="u",
            admin_token="admintoken",
        )
        res_admin = checker_admin.get_submission_details("task1", "123")
        self.assertEqual(res_admin, [{"idx": 0}])
        mock_get.assert_called_with(
            "http://localhost:8888/contest/api/task1/submissions/" "123/full_details",
            headers={},
        )

    def test_is_subtask_slow(self):
        time_limit = 1.0
        # Positive score and slow testcase (> 0.5 * 1.0) -> True
        st_slow = {
            "score": 10.0,
            "testcases": [{"time": 0.6}],
        }
        self.assertTrue(SolutionChecker.is_subtask_slow(st_slow, time_limit))

        # Positive score and fast testcase -> False
        st_fast = {
            "score": 10.0,
            "testcases": [{"time": 0.4}],
        }
        self.assertFalse(SolutionChecker.is_subtask_slow(st_fast, time_limit))

        # Zero score with slow testcase -> False
        st_zero = {
            "score": 0.0,
            "score_fraction": 0.0,
            "testcases": [{"time": 0.8}],
        }
        self.assertFalse(SolutionChecker.is_subtask_slow(st_zero, time_limit))

    def test_check_single_subtask(self):
        st_ac = {
            "idx": 1,
            "score": 20.0,
            "max_score": 20.0,
            "score_fraction": 1.0,
            "testcases": [{"outcome": "Correct"}],
        }
        self.assertIsNone(self.checker.check_single_subtask(st_ac, 1, "Accepted"))
        self.assertIsNotNone(self.checker.check_single_subtask(st_ac, 1, "WrongAnswer"))
        self.assertIsNone(self.checker.check_single_subtask(st_ac, 1, None))

    def test_format_report_table(self):
        time_limit = 1.0
        results = [
            {
                "name": "sol_correct.cpp",
                "criteria": {
                    "checks": ["Accepted", "Accepted"],
                    "min_score": 100.0,
                    "max_score": 100.0,
                },
                "score": 100.0,
                "compilation_failed": False,
                "details": [
                    {
                        "idx": 0,
                        "score": 50.0,
                        "max_score": 50.0,
                        "testcases": [{"outcome": "Correct", "time": 0.1}],
                    },
                    {
                        "idx": 1,
                        "score": 50.0,
                        "max_score": 50.0,
                        "testcases": [{"outcome": "Correct", "time": 0.1}],
                    },
                ],
                "failed": False,
                "slow": False,
            },
            {
                "name": "sol_slow.cpp",
                "criteria": {
                    "checks": ["Accepted", "Accepted"],
                    "min_score": 100.0,
                    "max_score": 100.0,
                },
                "score": 100.0,
                "compilation_failed": False,
                "details": [
                    {
                        "idx": 0,
                        "score": 50.0,
                        "max_score": 50.0,
                        "testcases": [{"outcome": "Correct", "time": 0.1}],
                    },
                    {
                        "idx": 1,
                        "score": 50.0,
                        "max_score": 50.0,
                        "testcases": [{"outcome": "Correct", "time": 0.7}],
                    },
                ],
                "failed": False,
                "slow": True,
            },
            {
                "name": "sol_failed.cpp",
                "criteria": {
                    "checks": ["Accepted", "WrongAnswer"],
                    "min_score": 50.0,
                    "max_score": 50.0,
                },
                "score": 100.0,
                "compilation_failed": False,
                "details": [
                    {
                        "idx": 0,
                        "score": 50.0,
                        "max_score": 50.0,
                        "testcases": [{"outcome": "Correct", "time": 0.1}],
                    },
                    {
                        "idx": 1,
                        "score": 50.0,
                        "max_score": 50.0,
                        "testcases": [{"outcome": "Correct", "time": 0.1}],
                    },
                ],
                "failed": True,
                "slow": False,
            },
            {
                "name": "sol_compile_err.cpp",
                "criteria": {
                    "checks": ["Accepted", "Accepted"],
                    "min_score": 100.0,
                    "max_score": 100.0,
                },
                "score": 0.0,
                "compilation_failed": True,
                "details": None,
                "failed": True,
                "slow": False,
            },
            {
                "name": "arcari.cpp",
                "criteria": {
                    "checks": [None, "Accepted", "Accepted"],
                    "min_score": 110.0,
                    "max_score": 120.0,
                },
                "score": 71.0,
                "compilation_failed": False,
                "details": [
                    {
                        "idx": 0,
                        "score": 0.0,
                        "max_score": 0.0,
                        "testcases": [{"outcome": "Correct", "time": 0.001}],
                    },
                    {
                        "idx": 1,
                        "score": 20.0,
                        "max_score": 20.0,
                        "testcases": [{"outcome": "Correct", "time": 0.001}],
                    },
                    {
                        "idx": 2,
                        "score": 51.0,
                        "max_score": 100.0,
                        "testcases": [{"outcome": "Correct", "time": 0.001}],
                    },
                ],
                "failed": True,
                "slow": False,
            },
        ]

        # Formatted with color
        table_colored = self.checker.format_report_table(
            results, time_limit, use_color=True
        )
        self.assertIn("sol_correct.cpp", table_colored)
        self.assertIn("sol_slow.cpp", table_colored)
        self.assertIn("sol_failed.cpp", table_colored)
        self.assertIn("sol_compile_err.cpp", table_colored)
        self.assertIn("arcari.cpp", table_colored)
        # Verify expected score format
        self.assertIn("71 (expected 110-120)", table_colored)
        self.assertIn("100 (expected 50)", table_colored)
        # Verify short status codes
        self.assertIn("AC", table_colored)
        self.assertIn("WA", table_colored)
        self.assertIn("CE", table_colored)
        # Verify ANSI colors
        self.assertIn("\x1b[32;1m", table_colored)  # Green
        self.assertIn("\x1b[33;1m", table_colored)  # Yellow
        self.assertIn("\x1b[31;1m", table_colored)  # Red

        # Formatted plain text (no ANSI codes)
        table_plain = self.checker.format_report_table(
            results, time_limit, use_color=False
        )
        self.assertNotIn("\x1b[", table_plain)
        self.assertIn("CE", table_plain)
        self.assertIn("71 (expected 110-120)", table_plain)
        self.assertIn("100", table_plain)

        # Empty results -> empty string
        self.assertEqual(self.checker.format_report_table([], time_limit), "")


if __name__ == "__main__":
    unittest.main()
