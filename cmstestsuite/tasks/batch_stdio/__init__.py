#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

task_info = {
    "name": "batchstdio",
    "title": "Test Batch Task with stdin/stdout",
    "time_limit": "0.2",
    "memory_limit": "128",
    "official_language": "",
    "task_type": "Batch",
    "TaskTypeOptions_Batch_compilation": "alone",
    "TaskTypeOptions_Batch_io_0_inputfile": "",
    "TaskTypeOptions_Batch_io_1_outputfile": "",
    "TaskTypeOptions_Batch_output_eval": "diff",
    "submission_format_choice": "simple",
    "submission_format": "",
    "score_type": "Sum",
    "score_type_parameters": "50",
}

test_cases = [
    ("1.in", "1.out", True),
    ("2.in", "2.out", False),
]
