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
        self.skip_enabled = getattr(task, "skip_failed_subtask", False)
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

        score_type = self.dataset.score_type
        if score_type not in ["GroupMin", "GroupMul"]:
            return False

        if testcase_codename in self._skipped_testcases:
            return True

        # Check if any earlier testcase in the same subtask has failed
        subtask_idx = self._get_subtask_for_testcase(testcase_codename)
        if subtask_idx is None:
            return False

        # Check if this subtask has already failed due to an earlier testcase
        if subtask_idx in self._failed_subtasks:
            subtask_testcases = self._get_testcases_in_subtask(subtask_idx)
            try:
                current_testcase_idx = subtask_testcases.index(testcase_codename)
                # Check if any earlier testcase in this subtask has failed
                for i in range(current_testcase_idx):
                    earlier_testcase = subtask_testcases[i]
                    if self._is_testcase_failed(earlier_testcase):
                        logger.info(
                            f"Skipping testcase {testcase_codename} because earlier testcase {earlier_testcase} failed in subtask {subtask_idx}"
                        )
                        return True
            except ValueError:
                pass

        return False

    def mark_testcase_failed(self, testcase_codename: str, outcome: float):
        """Mark a testcase as failed and potentially skip remaining testcases in the subtask.

        testcase_codename: The codename of the failed testcase
        outcome: The outcome/score of the testcase (0.0 means failed)
        """
        if not self.skip_enabled or not self.dataset:
            return

        score_type = self.dataset.score_type
        if score_type not in ['GroupMin', 'GroupMul']:
            return

        # Check if this testcase failed
        if outcome > 0.0:
            return

        subtask_idx = self._get_subtask_for_testcase(testcase_codename)
        if subtask_idx is None:
            logger.warning(f"Could not find subtask for testcase {testcase_codename}")
            return

        # Mark this subtask as failed
        self._failed_subtasks.add(subtask_idx)
        logger.info(f"Marking subtask {subtask_idx} as failed due to testcase {testcase_codename}")

        # Get all testcases in this subtask in order
        subtask_testcases = self._get_testcases_in_subtask(subtask_idx)
        logger.info(f"Subtask {subtask_idx} testcases in order: {subtask_testcases}")

        # Find the position of the failing testcase
        try:
            failing_testcase_idx = subtask_testcases.index(testcase_codename)
            logger.info(
                f"Failing testcase {testcase_codename} is at position {failing_testcase_idx} in subtask {subtask_idx}"
            )
        except ValueError:
            logger.warning(
                f"Failed testcase {testcase_codename} not found in subtask {subtask_idx}"
            )
            return

        # Skip only the testcases that come after the failing one in this subtask
        for i in range(failing_testcase_idx + 1, len(subtask_testcases)):
            tc_codename = subtask_testcases[i]
            # Only skip if this testcase hasn't been started yet
            if not self._is_testcase_started(tc_codename):
                self._skipped_testcases.add(tc_codename)
                logger.info(
                    f"Marking testcase {tc_codename} (position {i}) as skipped in subtask {subtask_idx} (after failure of {testcase_codename})"
                )
            else:
                logger.info(
                    f"Testcase {tc_codename} (position {i}) already started/completed, not skipping"
                )

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
            logger.debug(f"All testcase names in order: {testcase_names}")
            logger.debug(f"Score type parameters: {parameters}")

            for subtask_idx, parameter in enumerate(parameters):
                if len(parameter) < 2:
                    continue

                _, target = (
                    parameter[0],
                    parameter[1],
                )

                if isinstance(target, int):
                    start_idx = sum(param[1] for param in parameters[:subtask_idx] if isinstance(param[1], int))
                    end_idx = start_idx + target
                    group_testcases = testcase_names[start_idx:end_idx]
                    logger.debug(
                        f"Subtask {subtask_idx} (number-based): testcases {start_idx}-{end_idx - 1} = {group_testcases}"
                    )
                elif isinstance(target, str):
                    pattern = re.compile(target)
                    group_testcases = [tc for tc in testcase_names if pattern.match(tc)]
                    logger.debug(
                        f"Subtask {subtask_idx} (regex-based): pattern '{target}' = {group_testcases}"
                    )
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

    def _is_testcase_started(self, testcase_codename: str) -> bool:
        """Check if a testcase has been started (queued, running, or completed).

        This is more comprehensive than _is_testcase_evaluated as it also
        checks if the testcase is currently being evaluated.

        testcase_codename: The codename of the testcase

        Returns: True if the testcase has been started, False otherwise
        """
        # First check if it's already completed
        if self._is_testcase_evaluated(testcase_codename):
            return True

        # For now, we'll use the same logic as _is_testcase_evaluated
        # In the future, we could check if the testcase is currently
        # In the evaluation queue or being processed
        # But since we don't have easy access to the queue state here,
        # we will only skip testcases that definitely
        # haven't been touched yet.

        # TODO: Could be enhanced to check the evaluation service queue
        return self._is_testcase_evaluated(testcase_codename)

    def _is_testcase_failed(self, testcase_codename: str) -> bool:
        """Check if a testcase has failed (outcome <= 0.0).

        testcase_codename: The codename of the testcase

        Returns: True if the testcase failed, False otherwise
        """
        if not self.submission_result:
            return False

        for evaluation in self.submission_result.evaluations:
            if evaluation.codename == testcase_codename:
                try:
                    outcome = (
                        float(evaluation.outcome)
                        if evaluation.outcome != "N/A"
                        and evaluation.outcome is not None
                        else 0.0
                    )
                    return outcome <= 0.0
                except (ValueError, TypeError):
                    return True  # If we can't parse the outcome, consider it failed

        return False  # Not evaluated yet, so not failed
