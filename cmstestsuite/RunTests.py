#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import os
import sys

from cmstestsuite import TestException, sh


UNITTESTS = "unittests"
FUNCTIONALTESTS = "functionaltests"
TESTS = set([UNITTESTS, FUNCTIONALTESTS])


def get_test_suite():
    """Return the test suite to run based on the env variable

    return (string): either "functionaltests" or "unittests" or an
        empty string to mean "run both".

    """
    test_suite = ""
    if "TEST_SUITE" in os.environ:
        test_suite = os.environ["TEST_SUITE"]
    if test_suite in TESTS:
        return test_suite
    else:
        return ""


def main():
    test_suite = get_test_suite()
    try:
        if test_suite == UNITTESTS or len(test_suite) == 0:
            sh(["./cmstestsuite/RunUnitTests.py"] + sys.argv[1:])
        if test_suite == FUNCTIONALTESTS or len(test_suite) == 0:
            sh(["./cmstestsuite/RunFunctionalTests.py"] + sys.argv[1:])
    except TestException:
        if os.path.exists("./log/cms/last.log"):
            print("\n\n===== START OF LOG DUMP =====\n\n")
            with open("./log/cms/last.log", "rt", encoding="utf-8") as f:
                print(f.read())
            print("\n\n===== END OF LOG DUMP =====\n\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
