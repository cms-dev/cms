#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2014-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2016 Masaki Hara <ackie.h.gmai@gmail.com>
# Copyright © 2020 Andrey Vihrov <andrey.vihrov@gmail.com>
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

import cmstestsuite.tasks.batch_fileio as batch_fileio
import cmstestsuite.tasks.batch_fileio_managed as batch_fileio_managed
import cmstestsuite.tasks.batch_stdio as batch_stdio
import cmstestsuite.tasks.communication_fifoio_stubbed \
    as communication_fifoio_stubbed
import cmstestsuite.tasks.communication_many_fifoio_stubbed \
    as communication_many_fifoio_stubbed
import cmstestsuite.tasks.communication_many_stdio_stubbed \
    as communication_many_stdio_stubbed
import cmstestsuite.tasks.communication_stdio as communication_stdio
import cmstestsuite.tasks.communication_stdio_stubbed \
    as communication_stdio_stubbed
import cmstestsuite.tasks.outputonly as outputonly
import cmstestsuite.tasks.outputonly_comparator as outputonly_comparator
import cmstestsuite.tasks.twosteps as twosteps
import cmstestsuite.tasks.twosteps_comparator as twosteps_comparator
from cmstestsuite.Test import Test, CheckOverallScore, CheckCompilationFail, \
    CheckTimeout, CheckTimeoutWall, CheckNonzeroReturn, CheckUserTestEvaluated


LANG_CPP = "C++11 / g++"
LANG_CPP14 = "C++14 / g++"
LANG_CPP17 = "C++17 / g++"
LANG_C = "C11 / gcc"
LANG_HS = "Haskell / ghc"
LANG_JAVA = "Java / JDK"
LANG_PASCAL = "Pascal / fpc"
LANG_PHP = "PHP"
LANG_PYTHON = "Python 2 / CPython"
LANG_PYTHON3 = "Python 3 / CPython"
LANG_RUST = "Rust"
LANG_C_SHARP = "C# / Mono"
ALL_LANGUAGES = (
    LANG_CPP, LANG_CPP14, LANG_CPP17, LANG_C, LANG_HS, LANG_JAVA, LANG_PASCAL,
    LANG_PHP, LANG_PYTHON, LANG_PYTHON3, LANG_RUST, LANG_C_SHARP
)
NON_INTERPRETED_LANGUAGES = (
    LANG_C, LANG_CPP, LANG_CPP14, LANG_CPP17, LANG_PASCAL
)
COMPILED_LANGUAGES = (
    LANG_C, LANG_CPP, LANG_CPP14, LANG_CPP17, LANG_PASCAL, LANG_JAVA,
    LANG_PYTHON, LANG_PYTHON3, LANG_HS, LANG_RUST, LANG_C_SHARP
)

ALL_TESTS = [

    # Correct solutions to batch tasks.

    Test('correct-stdio',
         task=batch_stdio, filenames=['correct-stdio.%l'],
         alt_filenames={
             LANG_CPP14: ['correct-stdio-cxx14.%l'],
             LANG_CPP17: ['correct-stdio-cxx17.%l'],
         },
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(100, 100)]),

    Test('correct-freopen',
         task=batch_fileio, filenames=['correct-freopen.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(100, 100)],
         user_tests=True,
         user_checks=[CheckUserTestEvaluated()]),

    Test('correct-stdio-inner-class',
         task=batch_stdio, filenames=['correct-stdio-inner-class.%l'],
         languages=(LANG_JAVA, LANG_C_SHARP),
         checks=[CheckOverallScore(100, 100)]),

    Test('correct-fileio',
         task=batch_fileio, filenames=['correct-fileio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(100, 100)]),

    # Various incorrect solutions to batch tasks.

    Test('incorrect-stdio',
         task=batch_stdio, filenames=['incorrect-stdio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100)]),

    Test('half-correct-stdio',
         task=batch_stdio, filenames=['half-correct-stdio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(50, 100)]),

    Test('incorrect-fileio',
         task=batch_fileio, filenames=['incorrect-fileio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100)]),

    Test('half-correct-fileio',
         task=batch_fileio, filenames=['half-correct-fileio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(50, 100)]),

    Test('incorrect-fileio-nooutput',
         task=batch_fileio, filenames=['incorrect-fileio-nooutput.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('incorrect-fileio-emptyoutput',
         task=batch_fileio, filenames=['incorrect-fileio-emptyoutput.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('incorrect-fileio-with-stdio',
         task=batch_fileio, filenames=['incorrect-fileio-with-stdio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100)]),

    # OutputOnly tasks

    Test('correct-outputonly',
         task=outputonly, filenames=['correct-outputonly-000.txt',
                                     'correct-outputonly-001.txt'],
         languages=[None], checks=[CheckOverallScore(100, 100)]),

    Test('incorrect-outputonly',
         task=outputonly, filenames=['incorrect-outputonly-000.txt',
                                     'incorrect-outputonly-001.txt'],
         languages=[None], checks=[CheckOverallScore(0, 100)]),

    Test('partial-correct-outputonly',
         task=outputonly, filenames=['correct-outputonly-000.txt',
                                     'incorrect-outputonly-001.txt'],
         languages=[None], checks=[CheckOverallScore(50, 100)]),

    Test('correct-outputonly-comparator',
         task=outputonly_comparator,
         filenames=['correct-outputonly-000.txt',
                    'correct-outputonly-001.txt'],
         languages=[None], checks=[CheckOverallScore(100, 100)]),

    Test('incorrect-outputonly-comparator',
         task=outputonly_comparator,
         filenames=['incorrect-outputonly-000.txt',
                    'incorrect-outputonly-001.txt'],
         languages=[None], checks=[CheckOverallScore(0, 100)]),

    Test('partial-correct-outputonly-comparator',
         task=outputonly_comparator,
         filenames=['correct-outputonly-000.txt',
                    'incorrect-outputonly-001.txt'],
         languages=[None], checks=[CheckOverallScore(50, 100)]),

    # Failed compilation.

    Test('compile-fail',
         task=batch_fileio, filenames=['compile-fail.%l'],
         languages=COMPILED_LANGUAGES,
         checks=[CheckCompilationFail()]),

    Test('compile-timeout',
         task=batch_fileio, filenames=['compile-timeout.%l'],
         languages=(LANG_CPP,),
         checks=[CheckCompilationFail()]),

    # Various timeout conditions.

    Test('timeout-cputime',
         task=batch_stdio, filenames=['timeout-cputime.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100), CheckTimeout()]),

    Test('timeout-pause',
         task=batch_stdio, filenames=['timeout-pause.%l'],
         languages=(LANG_CPP,),
         checks=[CheckOverallScore(0, 100), CheckTimeoutWall()]),

    Test('timeout-sleep',
         task=batch_stdio, filenames=['timeout-sleep.%l'],
         languages=(LANG_CPP,),
         checks=[CheckOverallScore(0, 100), CheckTimeout()]),

    Test('timeout-sigstop',
         task=batch_stdio, filenames=['timeout-sigstop.%l'],
         languages=(LANG_CPP,),
         checks=[CheckOverallScore(0, 100), CheckTimeout()]),

    Test('timeout-select',
         task=batch_stdio, filenames=['timeout-select.%l'],
         languages=(LANG_CPP,),
         checks=[CheckOverallScore(0, 100), CheckTimeout()]),

    # Nonzero return status.

    Test('nonzero-return-stdio',
         task=batch_stdio, filenames=['nonzero-return-stdio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100), CheckNonzeroReturn()]),

    Test('nonzero-return-fileio',
         task=batch_fileio, filenames=['nonzero-return-fileio.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100), CheckNonzeroReturn()]),

    # Fork

    # We can't really check for a specific error, because forking
    # doesn't cause an exceptional stop: it just returns -1 to the
    # caller; we rely on the fact that the test program is designed to
    # produce output only inside the child process

    # TODO: since we allow many processes in the sandbox now by default,
    # these submission rightfully pass. We need to refactor TestRunner
    # to allow different contests for different tests to re-enable them.

    # Test('fork',
    #      task=batch_stdio, filenames=['fork.%l'],
    #      languages=(LANG_C, LANG_CPP),
    #      checks=[CheckOverallScore(0, 100)]),

    # OOM problems.

    Test('oom-static',
         task=batch_stdio, filenames=['oom-static.%l'],
         languages=NON_INTERPRETED_LANGUAGES,
         checks=[CheckOverallScore(0, 100)]),

    Test('oom-heap',
         task=batch_stdio, filenames=['oom-heap.%l'],
         languages=ALL_LANGUAGES,
         checks=[CheckOverallScore(0, 100)]),

    # Tasks with graders. PHP is not yet supported.

    Test('managed-correct',
         task=batch_fileio_managed, filenames=['managed-correct.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA,
                    LANG_C_SHARP),
         checks=[CheckOverallScore(100, 100)],
         user_tests=True, user_managers=['grader.%l'],
         user_checks=[CheckUserTestEvaluated()]),

    Test('managed-incorrect',
         task=batch_fileio_managed, filenames=['managed-incorrect.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA,
                    LANG_C_SHARP),
         checks=[CheckOverallScore(0, 100)]),

    # Communication tasks. PHP is not yet supported.

    Test('communication-fifoio-correct',
         task=communication_fifoio_stubbed,
         filenames=['communication-stubbed-correct.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(100, 100)]),

    Test('communication-fifoio-incorrect',
         task=communication_fifoio_stubbed,
         filenames=['communication-stubbed-incorrect.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(0, 100)]),

    Test('communication-stdio-correct',
         task=communication_stdio_stubbed,
         filenames=['communication-stubbed-correct.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(100, 100)]),

    Test('communication-stdio-incorrect',
         task=communication_stdio_stubbed,
         filenames=['communication-stubbed-incorrect.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(0, 100)]),

    Test('communication-stdio-unstubbed-correct',
         task=communication_stdio,
         filenames=['communication-stdio-correct.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(100, 100)]),

    Test('communication-stdio-unstubbed-incorrect',
         task=communication_stdio,
         filenames=['communication-stdio-incorrect.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(0, 100)]),

    # Communication tasks with two processes.

    Test('communication-many-fifoio-correct',
         task=communication_many_fifoio_stubbed,
         filenames=['communication-many-correct-user1.%l',
                    'communication-many-correct-user2.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(100, 100)]),

    Test('communication-many-fifoio-incorrect',
         task=communication_many_fifoio_stubbed,
         filenames=['communication-many-incorrect-user1.%l',
                    'communication-many-incorrect-user2.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(0, 100)]),

    Test('communication-many-stdio-correct',
         task=communication_many_stdio_stubbed,
         filenames=['communication-many-correct-user1.%l',
                    'communication-many-correct-user2.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(100, 100)]),

    Test('communication-many-stdio-incorrect',
         task=communication_many_stdio_stubbed,
         filenames=['communication-many-incorrect-user1.%l',
                    'communication-many-incorrect-user2.%l'],
         languages=(LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON3, LANG_JAVA),
         checks=[CheckOverallScore(0, 100)]),

    # TwoSteps

    Test('twosteps-correct',
         task=twosteps, filenames=["twosteps-correct-first.%l",
                                   "twosteps-correct-second.%l"],
         languages=(LANG_C, ),
         checks=[CheckOverallScore(100, 100)]),

    Test('twosteps-half-correct',
         task=twosteps, filenames=["twosteps-half-correct-first.%l",
                                   "twosteps-correct-second.%l"],
         languages=(LANG_C,),
         checks=[CheckOverallScore(50, 100)]),

    Test('twosteps-incorrect',
         task=twosteps, filenames=["twosteps-incorrect-first.%l",
                                   "twosteps-correct-second.%l"],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('twosteps-comparator-correct',
         task=twosteps_comparator, filenames=["twosteps-correct-first.%l",
                                              "twosteps-correct-second.%l"],
         languages=(LANG_C,),
         checks=[CheckOverallScore(100, 100)]),

    Test('twosteps-comparator-half-correct',
         task=twosteps_comparator, filenames=["twosteps-half-correct-first.%l",
                                              "twosteps-correct-second.%l"],
         languages=(LANG_C,),
         checks=[CheckOverallScore(50, 100)]),

    Test('twosteps-comparator-incorrect',
         task=twosteps_comparator, filenames=["twosteps-incorrect-first.%l",
                                              "twosteps-correct-second.%l"],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    # Writing to files not allowed.

    # Inability to write to a file does not throw a specific error,
    # just returns a NULL file handler to the caller. So we rely on
    # the test program to write the correct result only if the
    # returned handler is valid.

    Test('write-forbidden-fileio',
         task=batch_fileio, filenames=['write-forbidden-fileio.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('write-forbidden-stdio',
         task=batch_stdio, filenames=['write-forbidden-stdio.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('write-forbidden-managed',
         task=batch_fileio_managed, filenames=['write-forbidden-managed.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('write-forbidden-communication',
         task=communication_fifoio_stubbed,
         filenames=['write-forbidden-communication.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    # This tests complete successfully only if it is unable to execute
    # output.txt.

    Test('executing-output',
         task=batch_fileio, filenames=['executing-output.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(100, 100)]),

    # Rewrite input in the solution.

    Test('rewrite-input',
         task=batch_fileio_managed, filenames=['rewrite-input.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    Test('delete-write-input',
         task=batch_fileio_managed, filenames=['delete-write-input.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

    # Write a huge file

    Test('write-big-fileio',
         task=batch_fileio, filenames=['write-big-fileio.%l'],
         languages=(LANG_C,),
         checks=[CheckOverallScore(0, 100)]),

]
