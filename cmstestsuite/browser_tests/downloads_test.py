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

"""Browser tests for the dropdown menu to download a submission made of
several files, and for the table in the details dialog."""

from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


def open_pair_submissions(page, base_url):
    page.goto("%stasks/%s/submissions" % (base_url, seed.PAIR_TASK_NAME))


def test_multi_file_download_menu_opens_and_closes(page, base_url, login):
    login(seed.READER)
    open_pair_submissions(page, base_url)
    first, second = seed.PAIR_FILES
    item = page.get_by_role("link", name=first)
    expect(item).to_be_hidden()

    page.get_by_text("Download", exact=True).first.click()
    expect(item).to_be_visible()
    expect(page.get_by_role("link", name=second)).to_be_visible()

    # Clicking elsewhere closes the menu.
    page.get_by_role("heading").first.click()
    expect(item).to_be_hidden()


def test_multi_file_download_menu_downloads_a_file(page, base_url, login):
    login(seed.READER)
    open_pair_submissions(page, base_url)
    page.get_by_text("Download", exact=True).first.click()
    with page.expect_download() as info:
        page.get_by_role("link", name=seed.PAIR_FILES[1]).click()
    assert info.value.suggested_filename == seed.PAIR_FILES[1]


def test_details_dialog_lists_testcases_in_a_table(page, base_url, login):
    login(seed.READER)
    page.goto("%stasks/%s/submissions" % (base_url, seed.TASK_NAME))  # noqa: UP031
    page.get_by_text("details", exact=True).first.click()
    dialog = page.locator("#submission_detail")
    table = dialog.get_by_role("table").filter(has_text="Correct")
    expect(table).to_be_visible()
    expect(dialog.get_by_role("columnheader", name="Outcome")).to_be_visible()
    expect(dialog.get_by_role("cell", name="Correct", exact=True)) \
        .to_be_visible()
