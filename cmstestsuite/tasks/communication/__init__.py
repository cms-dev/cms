#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012-2013 Bernard Blackham <bernard@largestprime.net>
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
    "name": "communication",
    "title": "Test Communication Task",
    "time_limit": "1.0",
    "memory_limit": "64",
    "official_language": "",
    "task_type": "Communication",
    "submission_format_choice": "simple",
    "submission_format": "",
    "score_type": "Sum",
    "score_type_parameters": "50",
}

managers = [
    "stub.c",
    "stub.cpp",
    "manager",
]

test_cases = [
    ("1.in", "1.out", True),
    ("2.in", "2.out", False),
]
