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


task_info = {
    "name": "interactive",
    "title": "Test Interactive Task",
    "official_language": "",
    "submission_format_choice": "other",
    "submission_format": "interactive.%l",
    "time_limit_{{dataset_id}}": "1.0",
    "memory_limit_{{dataset_id}}": "128",
    "task_type_{{dataset_id}}": "Interactive",
    "TaskTypeOptions_{{dataset_id}}_Interactive_compilation": "stub",
    "TaskTypeOptions_{{dataset_id}}_Interactive_process_limit": "200",
    "TaskTypeOptions_{{dataset_id}}_Interactive_concurrent": "true",
    "TaskTypeOptions_{{dataset_id}}_Interactive_controller_time_limit": "1.0",
    "TaskTypeOptions_{{dataset_id}}_Interactive_controller_wall_limit": "5.0",
    "TaskTypeOptions_{{dataset_id}}_Interactive_controller_memory_limit": "128.0",
    "score_type_{{dataset_id}}": "Sum",
    "score_type_parameters_{{dataset_id}}": "50",
}

managers = [
    "controller",
    "stub.cpp",
    "stub.py",
]

test_cases = [
    ("input0.txt", "input0.out", True),
    ("input1.txt", "input1.out", True),
]
