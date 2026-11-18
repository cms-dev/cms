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

"""Browser tests for the registration form: both tabs, the validation
messages and the confirmation."""

import pytest
from playwright.sync_api import expect

from cmstestsuite.browser_tests import seed


def fill_new_user(page, username, password, confirm=None):
    page.locator("#first_name").fill("New")
    page.locator("#last_name").fill("Person")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#password-confirm").fill(
        password if confirm is None else confirm)


def test_tabs_switch_between_new_user_and_join(page, base_url):
    page.goto(base_url + "register")
    # The new user tab is shown first, with the whole form.
    expect(page.locator("#profile")).to_be_visible()
    expect(page.locator("#first_name")).to_be_visible()
    expect(page.locator("#password-confirm")).to_be_visible()

    # Joining with an existing user hides the profile and the password
    # confirmation.
    page.locator("#join-pill").get_by_role("link").click()
    expect(page.locator("#profile")).to_be_hidden()
    expect(page.locator("#first_name")).to_be_hidden()
    expect(page.locator("#password-confirm")).to_be_hidden()
    expect(page.locator("#username")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()

    page.locator("#register-pill").get_by_role("link").click()
    expect(page.locator("#profile")).to_be_visible()
    expect(page.locator("#first_name")).to_be_visible()
    expect(page.locator("#password-confirm")).to_be_visible()


def test_mismatching_passwords_show_an_error(page, base_url):
    page.goto(base_url + "register")
    fill_new_user(page, "mismatch-user", "a-long-password", "another-one-12")
    page.get_by_role("button", name="Register").click()
    expect(page.get_by_text("The passwords do not match!")).to_be_visible()
    expect(page.locator("#confirmed-mask")).to_be_hidden()


def test_register_a_new_user(page, base_url):
    page.goto(base_url + "register")
    fill_new_user(page, "fresh-user", "a-long-password")
    page.get_by_role("button", name="Register").click()
    expect(page.locator("#confirmed-mask")).to_be_visible()
    expect(page.locator("#show-username")).to_have_text("fresh-user")
    expect(page.locator("#signup-mask")).to_be_hidden()


# The next three tests make the server answer 409 or 404 on purpose, and
# Chromium logs failed requests as console errors.
@pytest.mark.allow_browser_errors
def test_taken_username_shows_an_error(page, base_url):
    page.goto(base_url + "register")
    fill_new_user(page, seed.READER, "a-long-password")
    page.get_by_role("button", name="Register").click()
    expect(page.get_by_text("This username is already taken")).to_be_visible()
    expect(page.locator("#confirmed-mask")).to_be_hidden()


@pytest.mark.allow_browser_errors
def test_joining_when_already_registered_shows_an_error(page, base_url):
    page.goto(base_url + "register")
    page.locator("#join-pill").get_by_role("link").click()
    page.locator("#username").fill(seed.READER)
    page.locator("#password").fill(seed.PASSWORDS[seed.READER])
    page.get_by_role("button", name="Register").click()
    expect(page.get_by_text("This user is already registered")).to_be_visible()


@pytest.mark.allow_browser_errors
def test_joining_with_an_unknown_user_shows_an_error(page, base_url):
    page.goto(base_url + "register")
    page.locator("#join-pill").get_by_role("link").click()
    page.locator("#username").fill("nobody-by-that-name")
    page.locator("#password").fill("whatever-password")
    page.get_by_role("button", name="Register").click()
    expect(page.get_by_text("No such user.")).to_be_visible()
