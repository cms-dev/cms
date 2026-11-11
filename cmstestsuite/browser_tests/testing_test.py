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

"""Browser tests for the testing page, which has one tab per task, a
details dialog and download menus."""

import pytest
from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


@pytest.fixture
def testing(page, base_url, login):
    login(seed.READER)
    page.goto(base_url + "testing")
    return page


def test_tabs_switch_between_tasks(testing):
    sum_pane = testing.locator("#test_%s" % seed.TASK_NAME)
    pair_pane = testing.locator("#test_%s" % seed.PAIR_TASK_NAME)
    expect(sum_pane).to_be_visible()
    expect(pair_pane).to_be_hidden()

    testing.get_by_role("link", name=seed.PAIR_TASK_NAME, exact=True).click()
    expect(pair_pane).to_be_visible()
    expect(sum_pane).to_be_hidden()

    testing.get_by_role("link", name=seed.TASK_NAME, exact=True).click()
    expect(sum_pane).to_be_visible()
    expect(pair_pane).to_be_hidden()


def test_previous_tests_are_listed(testing):
    rows = testing.locator("#test_%s tr[data-user-test]" % seed.TASK_NAME)
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Executed")


def test_test_details_open_in_a_dialog(testing):
    dialog = testing.locator("#user_test_detail")
    expect(dialog).to_be_hidden()

    testing.get_by_text("details", exact=True).first.click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("Execution completed successfully")) \
        .to_be_visible()

    dialog.get_by_text("Close", exact=True).click()
    expect(dialog).to_be_hidden()


def test_test_details_close_with_the_x(testing):
    testing.get_by_text("details", exact=True).first.click()
    dialog = testing.locator("#user_test_detail")
    expect(dialog).to_be_visible()
    # The footer's "Close" may be a link or a button; the x comes first.
    dialog.get_by_role("button", name="Close").first.click()
    expect(dialog).to_be_hidden()


def test_multi_file_test_has_a_download_menu(testing):
    testing.get_by_role("link", name=seed.PAIR_TASK_NAME, exact=True).click()
    pane = testing.locator("#test_%s" % seed.PAIR_TASK_NAME)
    first, second = seed.PAIR_FILES
    item = pane.get_by_role("link", name=first)
    expect(item).to_be_hidden()

    pane.locator("tr[data-user-test] td.files") \
        .get_by_text("Download", exact=True).click()
    expect(item).to_be_visible()
    expect(pane.get_by_role("link", name=second)).to_be_visible()

    with testing.expect_download() as info:
        item.click()
    assert info.value.suggested_filename == first


def test_single_file_test_has_a_direct_download_link(testing):
    pane = testing.locator("#test_%s" % seed.TASK_NAME)
    link = pane.locator("tr[data-user-test] td.files") \
        .get_by_role("link", name="Download")
    with testing.expect_download() as info:
        link.click()
    assert info.value.suggested_filename == "sum.py"


def test_submit_test_form_has_file_inputs_and_language(testing):
    pane = testing.locator("#test_%s" % seed.TASK_NAME)
    expect(pane.get_by_role("heading", name="Submit a test")).to_be_visible()
    expect(pane.locator("input[type=file][name='sum.%l']")).to_be_visible()
    expect(pane.locator("input[type=file][name=input]")).to_be_visible()
    expect(pane.locator("select[name=language]")).to_be_visible()
