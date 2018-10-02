#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Package containing high-level utilities for performing grading steps."""

from .compilation import COMPILATION_MESSAGES, compilation_step
from .evaluation import EVALUATION_MESSAGES, evaluation_step, \
    evaluation_step_after_run, evaluation_step_before_run, \
    human_evaluation_message
from .messages import HumanMessage, MessageCollection
from .stats import execution_stats, merge_execution_stats
from .trusted import checker_step, extract_outcome_and_text, trusted_step
from .whitediff import _WHITES, _white_diff, white_diff_step,\
    white_diff_fobj_step


__all__ = [
    # compilation.py
    "COMPILATION_MESSAGES", "compilation_step",
    # evaluation.py
    "EVALUATION_MESSAGES", "evaluation_step",
    "evaluation_step_after_run", "evaluation_step_before_run",
    "human_evaluation_message",
    # messages.py
    "HumanMessage", "MessageCollection",
    # stats_test.py
    "execution_stats", "merge_execution_stats",
    # trusted.py
    "checker_step", "extract_outcome_and_text", "trusted_step",
    # whitediff.py
    "_WHITES", "_white_diff", "white_diff_step", "white_diff_fobj_step"
]
