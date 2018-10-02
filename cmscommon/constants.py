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

# Task score modes.

# Maximum score amongst all submissions.
SCORE_MODE_MAX = "max"
# Sum of maximum score for each subtask over all submissions.
SCORE_MODE_MAX_SUBTASK = "max_subtask"
# Maximum score among all tokened submissions and the last submission.
SCORE_MODE_MAX_TOKENED_LAST = "max_tokened_last"
