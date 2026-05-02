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

Such a file can be generated with `task-maker-rust export-solution-checks`.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from typing import Optional, Dict, Any

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
        logging.CRITICAL: RED_FORMAT
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.BASE_FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class SolutionChecker:
    def __init__(
        self, base_url: str, username: Optional[str], password: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.auth_header = {}

    def login(self):
        if self.password is None or self.username is None:
            logger.info("No password provided, assuming IP autologin.")
            return

        login_url = f"{self.base_url}/api/login"
        response = self.session.post(
            login_url, data={"username": self.username, "password": self.password}
        )
        response.raise_for_status()
        data = response.json()
        self.auth_header = {"X-CMS-Authorization": data["login_data"]}
        logger.info("Successfully logged in.")

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

    def poll_status(self, task_name: str, filename: str, submission_id: str) -> Dict[str, Any]:
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

    def has_slow_testcases(
        self, task_name: str, submission_id: str, time_limit: float
    ) -> bool:
        url = f"{self.base_url}/tasks/{task_name}/submissions/{submission_id}/details"
        response = self.session.get(url, headers=self.auth_header)
        response.raise_for_status()

        html = response.text
        # Split by subtask. This is quite hacky and relies on subtask
        # delimiters having at least two classes (to avoid mixing it
        # up with subtask-head/subtask-body).
        subtasks = html.split('<div class="subtask ')[1:]
        for st in subtasks:
            # Check if subtask score > 0
            score_match = re.search(r'<span class="score">\s*\(\s*([\d.]+)\s*/', st)
            if score_match and float(score_match.group(1).replace(",", ".")) > 0:
                # Find all execution times in this subtask
                times = re.findall(
                    r'<td class="execution-time">\s*(?:&gt;\s*)?([\d.]+)\s*s', st
                )
                if not times:
                    logger.warning(
                        "No testcase times found. Ensure feedback levels are configured correctly"
                    )
                for t in times:
                    if float(t.replace(",", ".")) > time_limit * 0.5:
                        return True
        return False


def main():
    parser = argparse.ArgumentParser(description="CMS Solution Checker")
    parser.add_argument(
        "--checks-json", "-c", required=True, help="Path to solution_checks.json"
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

    checker = SolutionChecker(args.url, args.username, args.password)
    checker.login()

    time_limit = checker.get_time_limit(args.task)

    submissions = {}
    logger.info("Submitting %d solutions...", len(checks))
    for criteria in checks:
        sol_path = criteria.get("path")
        sub_id = checker.submit(args.task, sol_path)
        submissions[sol_path] = (sub_id, criteria)
        logger.info("Submitted %s: %s", sol_path.split("/")[-1], sub_id)

    has_failures = False
    logger.info("Waiting for evaluations...")
    for sol_path, (sub_id, criteria) in submissions.items():
        sol_name = sol_path.split("/")[-1]
        status = checker.poll_status(args.task, sol_name, sub_id)
        failed = False
        if status:
            score = status["public_score"]
            min_score = criteria["min_score"]
            max_score = criteria["max_score"]
            if score < min_score - 1e-7 or score > max_score + 1e-7:
                failed = True
                error = f"score {score} is not in range [{min_score}, {max_score}]"
        else:
            failed = True
            error = "Evaluation failed."

        if not failed:
            logger.info("%20s: check successful", sol_name)
            if checker.has_slow_testcases(args.task, sub_id, time_limit):
                logger.warning(
                    "%20s: some testcases took > 50%% of time limit",
                    sol_name,
                )
        else:
            has_failures = True
            logger.error("%20s: %s", sol_name, error)

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
