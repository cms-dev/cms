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

"""Browser tests for the submissions page: listing, details dialog,
download, tokens and sending a new submission."""

from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


ROWS = ".submission_list tbody tr[data-submission]"


def open_submissions(page, base_url):
    page.goto("%stasks/%s/submissions" % (base_url, seed.TASK_NAME))


def test_submission_list_shows_seeded_results(page, base_url, login, seeded):
    login(seed.READER)
    open_submissions(page, base_url)
    rows = page.locator(ROWS)
    expect(rows).to_have_count(seeded.reader_submissions)
    expect(rows.first).to_contain_text("50 / 50")


def test_no_submissions_is_an_empty_list(page, base_url, login):
    login(seed.NOBODY)
    open_submissions(page, base_url)
    expect(page.locator(ROWS)).to_have_count(0)


def test_submission_details_open_in_a_dialog(page, base_url, login):
    login(seed.READER)
    open_submissions(page, base_url)
    dialog = page.locator("#submission_detail")
    expect(dialog).to_be_hidden()

    page.get_by_text("details", exact=True).first.click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("Output is correct")).to_be_visible()

    dialog.get_by_text("Close", exact=True).click()
    expect(dialog).to_be_hidden()


def test_submission_details_close_with_the_x(page, base_url, login):
    login(seed.READER)
    open_submissions(page, base_url)
    page.get_by_text("details", exact=True).first.click()
    dialog = page.locator("#submission_detail")
    expect(dialog).to_be_visible()
    # The footer's "Close" may be a link or a button; the x comes first.
    dialog.get_by_role("button", name="Close").first.click()
    expect(dialog).to_be_hidden()


def test_download_submitted_file(page, base_url, login):
    login(seed.READER)
    open_submissions(page, base_url)
    with page.expect_download() as info:
        page.get_by_role("link", name="Download").first.click()
    assert info.value.suggested_filename == "sum.py"


def test_play_a_token(page, base_url, login):
    login(seed.TOKEN_USER)
    open_submissions(page, base_url)
    play = page.get_by_role("button", name="Play!")
    before = play.count()
    assert before >= 1
    play.first.click()
    page.wait_for_load_state("networkidle")
    open_submissions(page, base_url)
    expect(page.get_by_text("Played", exact=True)).to_have_count(1)
    expect(page.get_by_role("button", name="Play!")).to_have_count(before - 1)


def test_submit_a_solution(page, base_url, login, tmp_path):
    login(seed.SUBMITTER)
    open_submissions(page, base_url)
    expect(page.locator(ROWS)).to_have_count(0)

    source = tmp_path / "sum.py"
    source.write_text("print(sum(map(int, input().split())))\n")
    page.set_input_files("input[type=file][name='sum.%l']", str(source))
    page.locator("select[name=language]").select_option(
        label="Python 3 / CPython")
    page.get_by_role("button", name="Submit").first.click()

    # The submission is listed; it stays unevaluated since no evaluation
    # service runs in the browser tests.
    expect(page.locator(ROWS)).to_have_count(1)


def test_submit_nothing_creates_no_submission(page, base_url, login):
    login(seed.ASKER)
    open_submissions(page, base_url)
    page.get_by_role("button", name="Submit").first.click()
    open_submissions(page, base_url)
    expect(page.locator(ROWS)).to_have_count(0)
