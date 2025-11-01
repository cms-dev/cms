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

task_info = {
    "name": "outputonly",
    "title": "Test OutputOnly Task",
    "official_language": "",
    "submission_format_choice": "other",
    "submission_format": "output_000.txt, output_001.txt",
    "time_limit_{{dataset_id}}": "0.5",
    "memory_limit_{{dataset_id}}": "128",
    "task_type_{{dataset_id}}": "OutputOnly",
    "TaskTypeOptions_{{dataset_id}}_OutputOnly_output_eval": "diff",
    "score_type_{{dataset_id}}": "Sum",
    "score_type_parameters_{{dataset_id}}": "50",
}

managers = []

test_cases = [
    ("input_000.txt", "output_000.txt", True),
    ("input_001.txt", "output_001.txt", False),
]
