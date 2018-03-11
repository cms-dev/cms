#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

task_info = {
    "name": "batch",
    "title": "Test Batch Task",
    "official_language": "",
    "submission_format_choice": "other",
    "submission_format": "[\"batch.%l\"]",
    "time_limit_{{dataset_id}}": "0.5",
    "memory_limit_{{dataset_id}}": "125",
    "task_type_{{dataset_id}}": "Batch",
    "TaskTypeOptions_{{dataset_id}}_Batch_compilation": "alone",
    "TaskTypeOptions_{{dataset_id}}_Batch_io_0_inputfile": "",
    "TaskTypeOptions_{{dataset_id}}_Batch_io_1_outputfile": "",
    "TaskTypeOptions_{{dataset_id}}_Batch_output_eval": "diff",
    "score_type_{{dataset_id}}": "Sum",
    "score_type_parameters_{{dataset_id}}": "1",
}

test_cases = [
    ("0.in", "0.out", True),
    ("1.in", "1.out", True),
    ("2.in", "2.out", True),
    ("3.in", "3.out", True),
    ("4.in", "4.out", True),
    ("5.in", "5.out", True),
    ("6.in", "6.out", True),
    ("7.in", "7.out", True),
    ("8.in", "8.out", True),
    ("9.in", "9.out", True),
    ("10.in", "10.out", True),
    ("11.in", "11.out", True),
    ("12.in", "12.out", True),
    ("13.in", "13.out", True),
    ("14.in", "14.out", True),
    ("15.in", "15.out", True),
    ("16.in", "16.out", True),
    ("17.in", "17.out", True),
    ("18.in", "18.out", True),
    ("19.in", "19.out", True),
    ("20.in", "20.out", True),
    ("21.in", "21.out", True),
    ("22.in", "22.out", True),
    ("23.in", "23.out", True),
    ("24.in", "24.out", True),
    ("25.in", "25.out", True),
    ("26.in", "26.out", True),
    ("27.in", "27.out", True),
    ("28.in", "28.out", True),
    ("29.in", "29.out", True),
    ("30.in", "30.out", True),
    ("31.in", "31.out", True),
    ("32.in", "32.out", True),
    ("33.in", "33.out", True),
    ("34.in", "34.out", True),
    ("35.in", "35.out", True),
    ("36.in", "36.out", True),
    ("37.in", "37.out", True),
    ("38.in", "38.out", True),
    ("39.in", "39.out", True),
    ("40.in", "40.out", True),
    ("41.in", "41.out", True),
    ("42.in", "42.out", True),
    ("43.in", "43.out", True),
    ("44.in", "44.out", True),
    ("45.in", "45.out", True),
    ("46.in", "46.out", True),
    ("47.in", "47.out", True),
    ("48.in", "48.out", True),
    ("49.in", "49.out", True),
]
