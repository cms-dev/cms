#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
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

import cmstestsuite.tasks.batch_stdio as batch_stdio
from Test import Test, CheckOverallScore


all_languages = ('c', 'cpp', 'pas')

ALL_TESTS = [

Test(task=batch_stdio, filename='correct.%l', languages=all_languages,
    checks=[CheckOverallScore(100, 100)]),

Test(task=batch_stdio, filename='incorrect.%l', languages=all_languages,
    checks=[CheckOverallScore(0, 100)]),

Test(task=batch_stdio, filename='half-correct.%l', languages=all_languages,
    checks=[CheckOverallScore(50, 100)]),

]
