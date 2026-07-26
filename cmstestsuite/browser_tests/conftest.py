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

import logging
import os
import sys
import pytest

logger = logging.getLogger(__name__)


def pytest_configure(config):
    """Initialize CONFIG dictionary before tests run."""
    from cmstestsuite import CONFIG

    CONFIG["CONFIG_PATH"] = os.path.join(sys.prefix, "etc/cms.toml")

    # Allow override via CMS_CONFIG env
    if "CMS_CONFIG" in os.environ:
        CONFIG["CONFIG_PATH"] = os.environ["CMS_CONFIG"]


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for tests.

    Runs headless by default (for CI), but can be overridden
    with pytest --headed flag for local debugging.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }
