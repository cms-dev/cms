#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Pasit Sangprachathanarak <ouipingpasit@gmail.com>
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

"""Skip Subtask Logic for CMS.

This module handles the logic for skipping remaining testcases in a subtask
when one testcase fails and the task has skip_failed_subtask enabled.
"""

import logging
from typing import Set, Dict, List, Optional
import re

logger = logging.getLogger(__name__)


class SubtaskSkipper:
    """Manages skipping logic for subtasks based on failed testcases."""

    def __init__(self, task, submission_result):
        """Initialize the subtask skipper.

        task: The Task object with skip_failed_subtask setting
        submission_result: The SubmissionResult being evaluated
        """
        self.task = task
        self.submission_result = submission_result
        self.dataset = submission_result.dataset if submission_result else None
        self.skip_enabled = getattr(task, 'skip_failed_subtask', True)
        self._subtask_groups = None
        self._failed_subtasks = set()
        self._skipped_testcases = set()

    def should_skip_testcase(self, testcase_codename: str) -> bool:
        """Check if a testcase should be skipped due to subtask failure.

        testcase_codename: The codename of the testcase to check

        Returns: True if the testcase should be skipped, False otherwise
        """
        if not self.skip_enabled or not self.dataset:
            return False

        # Only skip for GroupMin and GroupMul score types
        score_type = self.dataset.score_type
        if score_type not in ['GroupMin', 'GroupMul']:
            return False

        subtask_idx = self._get_subtask_for_testcase(testcase_codename)
        if subtask_idx is None:
            return False

        return subtask_idx in self._failed_subtasks

    def mark_testcase_failed(self, testcase_codename: str, outcome: float):
        """Mark a testcase as failed and potentially skip remaining testcases in the subtask.

        testcase_codename: The codename of the failed testcase
        outcome: The outcome/score of the testcase (0.0 means failed)
        """
        if not self.skip_enabled or not self.dataset:
            return

        # Only handle for GroupMin and GroupMul score types
        score_type = self.dataset.score_type
        if score_type not in ['GroupMin', 'GroupMul']:
            return

        # Check if this testcase failed (outcome is 0.0 for failed)
        if outcome > 0.0:
            return

        subtask_idx = self._get_subtask_for_testcase(testcase_codename)
        if subtask_idx is None:
            return

        # Mark this subtask as failed
        self._failed_subtasks.add(subtask_idx)
        logger.info(f"Marking subtask {subtask_idx} as failed due to testcase {testcase_codename}")

        # Get all testcases in this subtask and mark remaining ones as skipped
        subtask_testcases = self._get_testcases_in_subtask(subtask_idx)
        for tc_codename in subtask_testcases:
            if tc_codename != testcase_codename:  # Skip the failing testcase itself
                # Check if this testcase hasn't been evaluated yet
                if not self._is_testcase_evaluated(tc_codename):
                    self._skipped_testcases.add(tc_codename)
                    logger.info(f"Marking testcase {tc_codename} as skipped in subtask {subtask_idx}")

    def get_skipped_testcases(self) -> Set[str]:
        """Get the set of testcase codenames that should be skipped."""
        return self._skipped_testcases.copy()

    def _get_subtask_groups(self) -> Optional[Dict[int, List[str]]]:
        """Parse subtask groups from score type parameters.

        Returns: Dictionary mapping subtask index to list of testcase codenames
        """
        if self._subtask_groups is not None:
            return self._subtask_groups

        if not self.dataset:
            return None

        try:
            score_type_obj = self.dataset.score_type_object
            parameters = self.dataset.score_type_parameters

            if not hasattr(score_type_obj, 'parameters') or not parameters:
                return None

            self._subtask_groups = {}
            testcase_names = sorted(self.dataset.testcases.keys())

            for subtask_idx, parameter in enumerate(parameters):
                if len(parameter) < 2:
                    continue

                max_score, target = parameter[0], parameter[1]

                if isinstance(target, int):
                    # Number-based grouping: first N testcases
                    start_idx = sum(param[1] for param in parameters[:subtask_idx] if isinstance(param[1], int))
                    end_idx = start_idx + target
                    group_testcases = testcase_names[start_idx:end_idx]
                elif isinstance(target, str):
                    # Regex-based grouping
                    pattern = re.compile(target)
                    group_testcases = [tc for tc in testcase_names if pattern.match(tc)]
                else:
                    continue

                self._subtask_groups[subtask_idx] = group_testcases

        except Exception as e:
            logger.warning(f"Failed to parse subtask groups: {e}")
            self._subtask_groups = {}

        return self._subtask_groups

    def _get_subtask_for_testcase(self, testcase_codename: str) -> Optional[int]:
        """Get the subtask index for a given testcase.

        testcase_codename: The codename of the testcase

        Returns: The subtask index, or None if not found
        """
        subtask_groups = self._get_subtask_groups()
        if not subtask_groups:
            return None

        for subtask_idx, testcases in subtask_groups.items():
            if testcase_codename in testcases:
                return subtask_idx

        return None

    def _get_testcases_in_subtask(self, subtask_idx: int) -> List[str]:
        """Get all testcases in a specific subtask.

        subtask_idx: The subtask index

        Returns: List of testcase codenames in the subtask
        """
        subtask_groups = self._get_subtask_groups()
        if not subtask_groups:
            return []

        return subtask_groups.get(subtask_idx, [])

    def _is_testcase_evaluated(self, testcase_codename: str) -> bool:
        """Check if a testcase has already been evaluated.

        testcase_codename: The codename of the testcase

        Returns: True if the testcase has been evaluated, False otherwise
        """
        if not self.submission_result:
            return False

        for evaluation in self.submission_result.evaluations:
            if evaluation.codename == testcase_codename:
                return True

        return False
