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

"""Script to automate testing of solutions via CMS API.

The script expects a JSON file containing a list of solution checks.
Each check should be an object with the following fields:
- path: path to the solution file.
- min_score: minimum expected score.
- max_score: maximum expected score.
- checks: optional list of expected subtask outcomes, where each
  element can be:
  - null (no assertion on this subtask)
  - "Accepted" (full score on this subtask)
  - "Zero" (0 score on this subtask)
  - "PartialScore" (score > 0 and < max_score on this subtask)
  - "WrongAnswer" (at least one testcase produced a wrong answer)
  - "TimeLimitExceeded" (at least one testcase exceeded CPU time limit)
  - "WallTimeLimitExceeded" (at least one testcase exceeded wall time limit)
  - "RuntimeError" (at least one testcase failed due to runtime error)

Such a file can be generated with `task-maker-rust export-solution-checks`.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class RedAlertFormatter(logging.Formatter):
    RED = "\x1b[31;1m"
    YELLOW = "\x1b[33;1m"
    RSET = "\x1b[0m"

    BASE_FORMAT = "%(levelname)8s %(message)s"

    RED_FORMAT = RED + "%(levelname)8s" + RSET + " %(message)s"

    YELLOW_FORMAT = YELLOW + "%(levelname)8s" + RSET + " %(message)s"

    FORMATS = {
        logging.DEBUG: BASE_FORMAT,
        logging.INFO: BASE_FORMAT,
        logging.WARNING: YELLOW_FORMAT,
        logging.ERROR: RED_FORMAT,
        logging.CRITICAL: RED_FORMAT,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.BASE_FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class SolutionChecker:
    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        admin_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.admin_token = admin_token
        self.session = requests.Session()
        self.auth_header: dict[str, str] = {}

    @staticmethod
    def _extract_error_message(err: requests.exceptions.HTTPError) -> str:
        if err.response is not None:
            try:
                json_data = err.response.json()
                if "error" in json_data:
                    return json_data["error"]
            except Exception:
                pass
            if err.response.text:
                return err.response.text.strip()
        return str(err)

    def login(self):
        if self.admin_token is not None:
            if self.username is None:
                raise ValueError(
                    "Admin token requires --username to specify user to impersonate."
                )
            login_url = f"{self.base_url}/api/login"
            data = {"admin_token": self.admin_token, "username": self.username}
            if self.password is not None:
                data["password"] = self.password
            try:
                response = self.session.post(login_url, data=data)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                err_msg = self._extract_error_message(e)
                raise RuntimeError(
                    f"Login with admin token failed: {err_msg}"
                ) from None

            res_data = response.json()
            self.auth_header = {"X-CMS-Authorization": res_data["login_data"]}
            logger.info("Successfully logged in with admin token as %s.", self.username)
            return

        if self.username is None and self.password is None:
            logger.info("No credentials provided, assuming IP autologin.")
            return

        if self.username is None and self.password is not None:
            raise ValueError(
                "Password provided without username. Please specify --username."
            )

        if self.username is not None and self.password is None:
            raise ValueError(
                f"Username '{self.username}' provided without password. "
                f"Please specify --password or use --admin-token."
            )

        login_url = f"{self.base_url}/api/login"
        try:
            response = self.session.post(
                login_url,
                data={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            err_msg = self._extract_error_message(e)
            raise RuntimeError(
                f"Login failed for user '{self.username}': {err_msg}"
            ) from None

        data = response.json()
        self.auth_header = {"X-CMS-Authorization": data["login_data"]}
        logger.info("Successfully logged in as %s.", self.username)

    def submit(self, task_name: str, file_path: str) -> str:
        task_list_url = f"{self.base_url}/api/task_list"
        response = self.session.get(task_list_url, headers=self.auth_header)
        response.raise_for_status()
        tasks = response.json().get("tasks", [])
        submission_format = []
        for t in tasks:
            if t["name"] == task_name:
                submission_format = t.get("submission_format", [])
                break
        assert submission_format, f"Task {task_name} not found in task list"

        submit_url = f"{self.base_url}/api/{task_name}/submit"
        filename = os.path.basename(file_path)
        files = {}
        for fmt in submission_format:
            files[fmt] = (filename, open(file_path, "rb"))

        response = self.session.post(
            submit_url,
            files=files,
            headers=self.auth_header,
        )
        response.raise_for_status()
        return response.json().get("id")

    def poll_status(
        self, task_name: str, filename: str, submission_id: str
    ) -> dict[str, Any]:
        status_url = f"{self.base_url}/tasks/{task_name}/submissions/{submission_id}"
        while True:
            response = self.session.get(status_url, headers=self.auth_header)
            response.raise_for_status()
            data = response.json()
            # status 5 is SCORED, 2 is COMPILATION_FAILED
            if data.get("status") in [2, 5]:
                return data
            time.sleep(2)

    def get_time_limit(self, task_name: str) -> float:
        url = f"{self.base_url}/tasks/{task_name}/description"
        response = self.session.get(url, headers=self.auth_header)
        response.raise_for_status()
        match = re.search(r"Time limit</th>\s*<td[^>]*>([\d.]+)\s*s", response.text)
        assert match, "Could not find time limit in task description"
        return float(match.group(1))

    def get_submission_details(
        self, task_name: str, submission_id: str
    ) -> list[dict[str, Any]] | None:
        endpoint = "full_details" if self.admin_token is not None else "details"
        url = (
            f"{self.base_url}/api/{task_name}/submissions/"
            f"{submission_id}/{endpoint}"
        )
        response = self.session.get(url, headers=self.auth_header)
        response.raise_for_status()
        return response.json().get("details")

    def has_slow_testcases(
        self, details: list[dict[str, Any]] | None, time_limit: float
    ) -> bool:
        if not details:
            return False

        has_times = False
        for item in details:
            testcases = item.get("testcases")
            if testcases is not None:
                # Subtask structure
                score = item.get("score", 0.0)
                score_fraction = item.get("score_fraction", 0.0)
                check_slow = (score is not None and score > 0) or (
                    score_fraction is not None and score_fraction > 0
                )
                for tc in testcases:
                    t = tc.get("time")
                    if t is not None:
                        has_times = True
                        if check_slow and float(t) > time_limit * 0.5:
                            return True
            else:
                # Flat testcase structure (e.g. Sum)
                t = item.get("time")
                if t is not None:
                    has_times = True
                    if float(t) > time_limit * 0.5:
                        return True

        if not has_times and not self.admin_token:
            logger.warning(
                "No testcase times found. Ensure feedback levels are "
                "configured correctly or use --admin-token"
            )
        return False

    @staticmethod
    def get_testcase_status(tc: dict[str, Any]) -> str:
        outcome = tc.get("outcome")
        text_list = tc.get("text", [])
        text_str = (
            text_list[0]
            if isinstance(text_list, list) and text_list
            else str(text_list)
        )
        if "wall clock" in text_str.lower():
            return "WallTimeLimitExceeded"
        if tc.get("time_limit_was_exceeded", False) or "timed out" in text_str.lower():
            return "TimeLimitExceeded"
        if (
            "signal" in text_str.lower()
            or "return code" in text_str.lower()
            or "memory limit" in text_str.lower()
        ):
            return "RuntimeError"
        if outcome == "Correct" or "output is correct" in text_str.lower():
            return "Accepted"
        if outcome == "Partially correct":
            return "PartialScore"
        if (
            outcome == "Not correct"
            or "output isn't correct" in text_str.lower()
            or "wrong answer" in text_str.lower()
        ):
            return "WrongAnswer"
        return "Unknown"

    def check_single_subtask(
        self, st: dict[str, Any] | None, st_idx: int, check: str | None
    ) -> str | None:
        if check is None:
            return None
        if st is None:
            return f"subtask {st_idx}: not found in submission details"

        score_fraction = st.get("score_fraction")
        score = st.get("score")
        max_score = st.get("max_score")
        testcases = st.get("testcases", [])
        statuses = {
            self.get_testcase_status(tc)
            for tc in testcases
            if "outcome" in tc or "text" in tc
        }
        statuses_list = sorted(statuses)

        if check == "Accepted":
            if (
                (statuses and not statuses <= {"Accepted"})
                or (score_fraction is not None and score_fraction < 1.0 - 1e-7)
                or (
                    score is not None
                    and max_score is not None
                    and score < max_score - 1e-7
                )
            ):
                return (
                    f"subtask {st_idx}: expected Accepted, got statuses "
                    f"{statuses_list}"
                )

        elif check == "Zero":
            if (score_fraction is not None and score_fraction > 1e-7) or (
                score is not None and score > 1e-7
            ):
                return (
                    f"subtask {st_idx}: expected Zero, got score "
                    f"{score}/{max_score} and statuses {statuses_list}"
                )

        elif check == "PartialScore":
            is_partial = False
            if score_fraction is not None and 1e-7 < score_fraction < 1.0 - 1e-7:
                is_partial = True
            elif (
                score is not None
                and max_score is not None
                and 1e-7 < score < max_score - 1e-7
            ):
                is_partial = True
            elif "PartialScore" in statuses or (
                "Accepted" in statuses and len(statuses - {"Accepted"}) > 0
            ):
                is_partial = True

            if not is_partial:
                return (
                    f"subtask {st_idx}: expected PartialScore, got score "
                    f"{score}/{max_score} and statuses {statuses_list}"
                )

        elif check in [
            "WrongAnswer",
            "TimeLimitExceeded",
            "WallTimeLimitExceeded",
            "RuntimeError",
        ]:
            if check not in statuses:
                return (
                    f"subtask {st_idx}: expected {check}, got statuses "
                    f"{statuses_list}"
                )

        else:
            return f"subtask {st_idx}: unknown check type '{check}'"

        return None

    def check_subtasks(
        self, details: list[dict[str, Any]] | None, checks: list[str | None]
    ) -> list[str]:
        if details is None:
            return ["Submission details unavailable for subtask checks."]

        errors = []
        subtasks_by_idx = {st.get("idx", i): st for i, st in enumerate(details)}

        for st_idx, check in enumerate(checks):
            st = subtasks_by_idx.get(st_idx)
            err = self.check_single_subtask(st, st_idx, check)
            if err is not None:
                errors.append(err)

        return errors

    @staticmethod
    def is_subtask_slow(st: dict[str, Any], time_limit: float) -> bool:
        if not st:
            return False
        score = st.get("score", 0.0)
        score_fraction = st.get("score_fraction", 0.0)
        check_slow = (score is not None and score > 0) or (
            score_fraction is not None and score_fraction > 0
        )
        if not check_slow:
            return False
        for tc in st.get("testcases", []):
            t = tc.get("time")
            if t is not None and float(t) > time_limit * 0.5:
                return True
        return False

    STATUS_SHORT_CODES = {
        "Accepted": "AC",
        "WrongAnswer": "WA",
        "TimeLimitExceeded": "TLE",
        "WallTimeLimitExceeded": "WTL",
        "RuntimeError": "RTE",
        "PartialScore": "PS",
        "Zero": "0",
        None: "-",
    }

    def format_report_table(
        self,
        results: list[dict[str, Any]],
        time_limit: float,
        use_color: bool = True,
    ) -> str:
        if not results:
            return ""

        RED = "\x1b[31;1m" if use_color else ""
        GREEN = "\x1b[32;1m" if use_color else ""
        YELLOW = "\x1b[33;1m" if use_color else ""
        RSET = "\x1b[0m" if use_color else ""

        num_subtasks = 0
        for r in results:
            crit_checks = r.get("criteria", {}).get("checks")
            if crit_checks:
                num_subtasks = max(num_subtasks, len(crit_checks))
            details = r.get("details")
            if isinstance(details, list):
                num_subtasks = max(num_subtasks, len(details))

        rows = []
        for r in results:
            sol_name = r["name"]
            criteria = r.get("criteria", {})
            checks = criteria.get("checks", [])
            details = r.get("details")
            compilation_failed = r.get("compilation_failed", False)
            subtasks_by_idx = {}
            if isinstance(details, list):
                subtasks_by_idx = {st.get("idx", i): st for i, st in enumerate(details)}

            row_cells = [(sol_name, "")]

            for i in range(num_subtasks):
                expected = checks[i] if i < len(checks) else None
                cell_text = self.STATUS_SHORT_CODES.get(
                    expected, str(expected) if expected is not None else "-"
                )
                cell_color = GREEN

                if compilation_failed:
                    cell_color = RED
                else:
                    st = subtasks_by_idx.get(i)
                    if expected is not None:
                        err = self.check_single_subtask(st, i, expected)
                        if err is not None:
                            cell_color = RED
                        elif self.is_subtask_slow(st, time_limit):
                            cell_color = YELLOW
                        else:
                            cell_color = GREEN
                    else:
                        if st and self.is_subtask_slow(st, time_limit):
                            cell_color = YELLOW
                        else:
                            cell_color = GREEN

                row_cells.append((cell_text, cell_color))

            if compilation_failed:
                score_text = "CE"
                expected_str = ""
                total_color = RED
            else:
                score = r.get("score", 0.0)
                min_score = criteria.get("min_score", 0.0)
                max_score = criteria.get("max_score", 100.0)
                score_unexpected = score < min_score - 1e-7 or score > max_score + 1e-7

                score_text = f"{score:g}"
                if score_unexpected:
                    if abs(min_score - max_score) < 1e-7:
                        expected_note = f"expected {min_score:g}"
                    else:
                        expected_note = f"expected {min_score:g}-{max_score:g}"
                    expected_str = f" ({expected_note})"
                else:
                    expected_str = ""

                if r.get("failed", False):
                    total_color = RED
                elif r.get("slow", False):
                    total_color = YELLOW
                else:
                    total_color = GREEN

            rows.append((row_cells, score_text, expected_str, total_color))

        num_subtask_cols = num_subtasks + 1  # sol_name + subtasks
        col_widths = [0] * num_subtask_cols
        score_col_width = 0

        for row_cells, score_text, _, _ in rows:
            for col_idx, (text, _) in enumerate(row_cells):
                col_widths[col_idx] = max(col_widths[col_idx], len(text))
            score_col_width = max(score_col_width, len(score_text))

        lines = []
        for row_cells, score_text, expected_str, total_color in rows:
            row_strs = []
            for col_idx, (text, color) in enumerate(row_cells):
                w = col_widths[col_idx]
                align_fmt = f"{text:<{w}}" if col_idx == 0 else f"{text:>{w}}"
                if color:
                    row_strs.append(f"{color}{align_fmt}{RSET}")
                else:
                    row_strs.append(align_fmt)

            aligned_score = f"{score_text:>{score_col_width}}{expected_str}"
            if total_color:
                row_strs.append(f"{total_color}{aligned_score}{RSET}")
            else:
                row_strs.append(aligned_score)

            lines.append("  ".join(row_strs))

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="CMS Solution Checker")
    parser.add_argument(
        "--checks-json",
        "-c",
        required=True,
        help="Path to solution_checks.json",
    )
    parser.add_argument(
        "--url",
        "-u",
        required=True,
        help="CMS contest URL (e.g. http://localhost:8888/contest)",
    )
    parser.add_argument("--task", "-t", required=True, help="Task name")
    parser.add_argument("--username", "-U", help="CMS username")
    parser.add_argument("--password", "-p", help="CMS password")
    parser.add_argument(
        "--admin-token", "-a", help="CMS contest admin token for full details"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Disable non-warnings"
    )

    args = parser.parse_args()

    logger.setLevel(logging.WARNING if args.quiet else logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(RedAlertFormatter())
    logger.addHandler(ch)

    if not os.path.exists(args.checks_json):
        logger.error("%s not found.", args.checks_json)
        return 1

    with open(args.checks_json, "r") as f:
        checks = json.load(f)

    try:
        checker = SolutionChecker(
            args.url,
            args.username,
            args.password,
            admin_token=args.admin_token,
        )
        checker.login()

        time_limit = checker.get_time_limit(args.task)

        submissions = {}
        logger.info("Submitting %d solutions...", len(checks))
        for criteria in checks:
            sol_path = criteria.get("path")
            sub_id = checker.submit(args.task, sol_path)
            submissions[sol_path] = (sub_id, criteria)
            logger.info("Submitted %s: %s", sol_path.split("/")[-1], sub_id)

        results = []
        has_failures = False
        logger.info("Waiting for evaluations...")
        for sol_path, (sub_id, criteria) in submissions.items():
            sol_name = sol_path.split("/")[-1]
            status = checker.poll_status(args.task, sol_name, sub_id)
            failed = False
            compilation_failed = False
            errors = []
            score = 0.0
            details = None
            slow = False

            if status:
                if status.get("status") == 2:
                    failed = True
                    compilation_failed = True
                    errors.append("Compilation failed.")
                else:
                    score = status.get("public_score", 0.0)
                    min_score = criteria.get("min_score", 0.0)
                    max_score = criteria.get("max_score", 100.0)
                    if score < min_score - 1e-7 or score > max_score + 1e-7:
                        failed = True
                        errors.append(
                            f"score {score} is not in range "
                            f"[{min_score}, {max_score}]"
                        )

                    details = checker.get_submission_details(args.task, sub_id)

                    if "checks" in criteria and criteria["checks"]:
                        subtask_errors = checker.check_subtasks(
                            details, criteria["checks"]
                        )
                        if subtask_errors:
                            failed = True
                            errors.extend(subtask_errors)

                    if checker.has_slow_testcases(details, time_limit):
                        slow = True
            else:
                failed = True
                errors.append("Evaluation failed.")

            if not failed:
                logger.info("%20s: check successful", sol_name)
                if slow:
                    logger.warning(
                        "%20s: some testcases took > 50%% of time limit",
                        sol_name,
                    )
            else:
                has_failures = True
                for err in errors:
                    logger.error("%20s: %s", sol_name, err)

            results.append(
                {
                    "name": sol_name,
                    "criteria": criteria,
                    "score": score,
                    "compilation_failed": compilation_failed,
                    "details": details,
                    "failed": failed,
                    "slow": slow,
                }
            )

        # Print report table
        table_str = checker.format_report_table(
            results, time_limit, use_color=sys.stdout.isatty()
        )
        print("\n" + table_str)

        return 1 if has_failures else 0

    except (ValueError, RuntimeError) as e:
        logger.error("%s", e)
        return 1
    except requests.exceptions.HTTPError as e:
        err_msg = SolutionChecker._extract_error_message(e)
        status_code = e.response.status_code if e.response is not None else "unknown"
        logger.error("API error (%s): %s", status_code, err_msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
