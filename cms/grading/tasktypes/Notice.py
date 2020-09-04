#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Task type for notice tasks.
"""
import logging

from . import TaskType

logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Notice(TaskType):

    ACCEPTED_PARAMETERS = []
    ALLOW_SUBMISSION = False

    testable = False

    def get_compilation_commands(self, unused_submission_format):
        """See TaskType.get_compilation_commands."""
        return None

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # No compilation needed.
        job.success = True
        job.compilation_success = True
        job.text = [N_("No compilation needed")]
        job.plus = {}

    def evaluate(self, job, file_cacher):
        job.success = True
        job.outcome = "0.0"
        job.text = ""
        job.plus = {}
