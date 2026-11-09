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

"""Browser tests for the communication page."""

from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


def test_shows_announcements_messages_and_answers(page, base_url, login):
    login(seed.READER)
    page.get_by_role("link", name="Communication").click()
    expect(page.get_by_text(seed.ANNOUNCEMENT_SUBJECT)).to_be_visible()
    expect(page.get_by_text(seed.MESSAGE_SUBJECT)).to_be_visible()
    expect(page.get_by_text(seed.ANSWERED_QUESTION_SUBJECT).first) \
        .to_be_visible()
    expect(page.get_by_text(seed.ANSWER_TEXT)).to_be_visible()


def test_ask_a_question(page, base_url, login):
    login(seed.ASKER)
    page.get_by_role("link", name="Communication").click()
    page.locator("#input_subject").fill("Where is the toilet?")
    page.locator("#input_text").fill("Asking for a friend.")
    page.get_by_role("button", name="Ask question").click()

    page.get_by_role("link", name="Communication").click()
    expect(page.get_by_text("Where is the toilet?").first).to_be_visible()


def test_reset_clears_the_question_form(page, base_url, login):
    login(seed.ASKER)
    page.get_by_role("link", name="Communication").click()
    page.locator("#input_subject").fill("draft")
    page.get_by_role("button", name="Reset").click()
    expect(page.locator("#input_subject")).to_have_value("")
