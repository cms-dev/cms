#!/usr/bin/env python2
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
import cmstestsuite.tasks.batch_fileio as batch_fileio
import cmstestsuite.tasks.batch_fileio_managed as batch_fileio_managed
import cmstestsuite.tasks.communication as communication
import cmstestsuite.tasks.twostep_multisubmit as twostep_multisubmit
from cmstestsuite.Test import Test, CheckOverallScore, CheckCompilationFail, \
     CheckTimeout, CheckSignal, CheckNonzeroReturn


all_languages = ('c', 'cpp', 'pas')

ALL_TESTS = [

Test('correct-stdio',
     task=batch_stdio, files=['correct-stdio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(100, 100)]),

Test('incorrect-stdio',
     task=batch_stdio, files=['incorrect-stdio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(0, 100)]),

Test('half-correct-stdio',
     task=batch_stdio, files=['half-correct-stdio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(50, 100)]),

Test('correct-freopen',
     task=batch_fileio, files=['correct-freopen.%l'],
     languages=('c',),
     checks=[CheckOverallScore(100, 100)]),

Test('correct-fileio',
     task=batch_fileio, files=['correct-fileio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(100, 100)]),

Test('incorrect-fileio',
     task=batch_fileio, files=['incorrect-fileio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(0, 100)]),

Test('half-correct-fileio',
     task=batch_fileio, files=['half-correct-fileio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(50, 100)]),

Test('incorrect-fileio-nooutput',
     task=batch_fileio, files=['incorrect-fileio-nooutput.%l'],
     languages=('c',),
     checks=[CheckOverallScore(0, 100)]),

Test('incorrect-fileio-emptyoutput',
     task=batch_fileio, files=['incorrect-fileio-emptyoutput.%l'],
     languages=('c',),
     checks=[CheckOverallScore(0, 100)]),

Test('incorrect-readstdio',
     task=batch_fileio, files=['correct-stdio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(0, 100)]),

Test('compile-fail',
     task=batch_fileio, files=['compile-fail.%l'],
     languages=all_languages,
     checks=[CheckCompilationFail()]),

Test('timeout-cputime',
     task=batch_stdio, files=['timeout-cputime.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(0, 100), CheckTimeout()]),

Test('timeout-pause',
     task=batch_stdio, files=['timeout-pause.%l'],
     languages=('cpp',),
     checks=[CheckOverallScore(0, 100), CheckTimeout()]),

Test('timeout-sleep',
     task=batch_stdio, files=['timeout-sleep.%l'],
     languages=('cpp',),
     checks=[CheckOverallScore(0, 100), CheckTimeout()]),

Test('timeout-sigstop',
     task=batch_stdio, files=['timeout-sigstop.%l'],
     languages=('cpp',),
     checks=[CheckOverallScore(0, 100), CheckTimeout()]),

Test('timeout-select',
     task=batch_stdio, files=['timeout-select.%l'],
     languages=('cpp',),
     checks=[CheckOverallScore(0, 100), CheckTimeout()]),

Test('nonzero-return-stdio',
     task=batch_stdio, files=['nonzero-return-stdio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(0, 100), CheckNonzeroReturn()]),

Test('nonzero-return-fileio',
     task=batch_fileio, files=['nonzero-return-fileio.%l'],
     languages=all_languages,
     checks=[CheckOverallScore(0, 100), CheckNonzeroReturn()]),

Test('managed-correct',
     task=batch_fileio_managed, files=['managed-correct.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(100, 100)]),

Test('managed-incorrect',
     task=batch_fileio_managed, files=['managed-incorrect.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(0, 100)]),

Test('communication-correct',
     task=communication, files=['managed-correct.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(100, 100)]),

Test('communication-incorrect',
     task=communication, files=['managed-incorrect.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(0, 100)]),

Test('twostepmultisubmit-correct',
     task=twostep_multisubmit,
     files=['twostep-correct-partA.%l', 'twostep-correct-partB.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(100, 100)]),

Test('twostepmultisubmit-incorrect',
     task=twostep_multisubmit,
     files=['twostep-incorrect-partA.%l', 'twostep-incorrect-partB.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(0, 100)]),

Test('twostepmultisubmit-only-partA-correct',
     task=twostep_multisubmit,
     files=['twostep-correct-partA.%l', 'twostep-incorrect-partB.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(0, 100)]),

Test('twostepmultisubmit-only-partB-correct',
     task=twostep_multisubmit,
     files=['twostep-incorrect-partA.%l', 'twostep-correct-partB.%l'],
     languages=('c', 'cpp'), # TODO: Pascal.
     checks=[CheckOverallScore(0, 100)]),

]
