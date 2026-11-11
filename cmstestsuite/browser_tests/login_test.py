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

"""Browser tests for logging in and out of CWS."""

import re

from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


def test_login_page_shows_form(page, base_url):
    page.goto(base_url)
    expect(page.get_by_label("Username")).to_be_visible()
    expect(page.get_by_label("Password")).to_be_visible()
    expect(page.get_by_role("button", name="Login")).to_be_visible()
    expect(page.get_by_text("Failed to log in.")).to_have_count(0)


def test_login_and_logout(page, base_url, login):
    login(seed.READER)
    expect(page.get_by_text("Logged in as")).to_contain_text("Alice Tester")
    expect(page.get_by_role("heading", name="Overview", exact=True)).to_be_visible()

    page.get_by_role("button", name="Logout").click()
    expect(page.get_by_role("button", name="Login")).to_be_visible()
    expect(page.get_by_role("button", name="Logout")).to_have_count(0)


def test_failed_login_alert_can_be_dismissed(page, base_url):
    page.goto(base_url)
    page.get_by_label("Username").fill(seed.READER)
    page.get_by_label("Password").fill("not-the-password")
    page.get_by_role("button", name="Login").click()

    alert = page.get_by_text("Failed to log in.")
    expect(alert).to_be_visible()
    expect(page.get_by_role("button", name="Logout")).to_have_count(0)

    # The alert has a close control; using it must remove the alert.
    page.get_by_role("button", name="Close").click()
    expect(alert).to_be_hidden()


def test_reset_button_clears_the_login_form(page, base_url):
    page.goto(base_url)
    page.get_by_label("Username").fill("something")
    page.get_by_role("button", name="Reset").click()
    expect(page.get_by_label("Username")).to_have_value("")


def test_registration_link_opens_registration_page(page, base_url):
    page.goto(base_url)
    page.get_by_role("link", name="Register").click()
    expect(page).to_have_url(re.compile(r"/register$"))
