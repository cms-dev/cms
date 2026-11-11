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

"""Browser tests for the pages reachable from the navigation menu."""

import re

import pytest
from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


@pytest.fixture
def reader(page, login):
    login(seed.READER)
    return page


def test_overview(reader):
    expect(reader.get_by_role("heading", name="Overview", exact=True)).to_be_visible()
    expect(reader.get_by_text("The contest is currently running.")) \
        .to_be_visible()
    expect(reader.get_by_text("Server time:")).to_be_visible()


def test_navigation_menu_lists_task_and_pages(reader):
    for name in ("Overview", "Communication", "Statement", "Submissions",
                 "Documentation"):
        expect(reader.get_by_role("link", name=name).first).to_be_visible()


def test_server_clock_ticks(reader):
    clock = reader.locator("#server_time")
    first = clock.inner_text()
    expect(clock).not_to_have_text(first, timeout=5000)


def test_task_statement(reader):
    reader.get_by_role("link", name="Statement").first.click()
    expect(reader).to_have_url(
        re.compile(r"/tasks/%s/description$" % seed.TASK_NAME))
    expect(reader.get_by_text(seed.TASK_TITLE).first).to_be_visible()
    expect(reader.locator("a[href*='/statements/']").first).to_be_visible()


def test_documentation(reader):
    reader.get_by_role("link", name="Documentation").click()
    expect(reader).to_have_url(re.compile(r"/documentation$"))
    expect(reader.get_by_role("heading").first).to_be_visible()


def test_language_selector_switches_language(reader):
    selector = reader.locator("#lang")
    if selector.count() == 0:
        pytest.skip("only one translation is installed")
    codes = [o.get_attribute("value")
             for o in selector.locator("option").all()]
    target = next(c for c in codes if c and not c.startswith("en"))
    with reader.expect_navigation():
        selector.select_option(target)
    expect(reader.locator("#lang")).to_have_value(target)
    # Put the automatic language back, so later tests see English.
    with reader.expect_navigation():
        reader.locator("#lang").select_option("")


@pytest.mark.allow_browser_errors
def test_unknown_task_shows_error_page(reader, base_url):
    response = reader.goto(base_url + "tasks/does-not-exist/description")
    assert response.status == 404
    expect(reader.get_by_text("404").first).to_be_visible()
