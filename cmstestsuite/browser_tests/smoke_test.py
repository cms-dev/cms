#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Pasit Sangprachathanarak <ouipingpasit@gmail.com>
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

"""Smoke tests: every page loads for a logged-in user. Console errors and
missing static files are reported by the autouse fixture in conftest.py."""

import pytest

from cmstestsuite.browser_tests import seed


@pytest.mark.parametrize("path", [
    "",
    "communication",
    "documentation",
    "tasks/%s/description" % seed.TASK_NAME,
    "tasks/%s/submissions" % seed.TASK_NAME,
    "tasks/%s/description" % seed.PAIR_TASK_NAME,
    "tasks/%s/submissions" % seed.PAIR_TASK_NAME,
    "testing",
])
def test_page_loads(page, base_url, login, path):
    login(seed.READER)
    response = page.goto(base_url + path)
    assert response.status == 200
    page.wait_for_load_state("networkidle")


def test_registration_page_loads(page, base_url):
    response = page.goto(base_url + "register")
    assert response.status == 200
    page.wait_for_load_state("networkidle")
