#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

import atexit
import tempfile
import subprocess
import shutil
import os
from argparse import ArgumentParser

from cmstestsuite import info, sh, configure_cms, read_cms_config, CONFIG

# These settings are only used within this file.
CONFIG.update({
    "DB_HOST": "localhost",
    "DB_USER": "cmsuser",
    "DB_PASSWORD": "cmsuser",
    "DB_NAME": "cmstestdb",
    "GIT_ORIGIN": None,
    "GIT_REVISION": None,
})


def drop_old_data():
    info("Dropping any old databases called %(DB_NAME)s." % CONFIG)
    sh("sudo -u postgres dropdb %(DB_NAME)s" % CONFIG, ignore_failure=True)

    info("Purging old checkout from %(TEST_DIR)s." % CONFIG)
    shutil.rmtree("%(TEST_DIR)s" % CONFIG)


def setup_cms():
    info("Creating database called %(DB_NAME)s accessible by %(DB_USER)s." %
         CONFIG)
    sh("sudo -u postgres createdb %(DB_NAME)s -O %(DB_USER)s" % CONFIG)

    info("Checking out code.")
    sh("git clone %(GIT_ORIGIN)s %(TEST_DIR)s" % CONFIG)
    os.chdir("%(TEST_DIR)s/cms" % CONFIG)
    sh("git checkout %(GIT_REVISION)s" % CONFIG)

    info("Configuring CMS.")
    configure_cms(
        {
            "database": '"postgresql+psycopg2://' \
                '%(DB_USER)s:%(DB_PASSWORD)s@' \
                '%(DB_HOST)s/%(DB_NAME)s"' % CONFIG,
            "keep_sandbox": "false",
            "contest_listen_address": '["127.0.0.1"]',
            "admin_listen_address": '"127.0.0.1"',
            "min_submission_interval": '0',
        })

    info("Setting environment.")
    os.environ["PYTHONPATH"] = "%(TEST_DIR)s/cms" % CONFIG

    info("Creating tables.")
    sh("python db/SQLAlchemyAll.py")


if __name__ == "__main__":
    parser = ArgumentParser(
        description="This utility tests a clean checkout of CMS.")
    parser.add_argument("-r", "--revision",
        type=str, default="master", action="store",
        help="Which git revision to test")
    parser.add_argument("-k", "--keep-working",
        default=False, action="store_true",
        help="Do not delete the working directory")
    parser.add_argument("arguments", nargs="*",
        help="All remaining arguments are passed to the test script.")
    args = parser.parse_args()

    CONFIG["TEST_DIR"] = tempfile.mkdtemp()
    CONFIG["CONFIG_PATH"] = "%s/examples/cms.conf" % CONFIG["TEST_DIR"]
    CONFIG["GIT_ORIGIN"] = subprocess.check_output(
        "git rev-parse --show-toplevel", shell=True).strip()
    CONFIG["GIT_REVISION"] = args.revision

    if not args.keep_working:
        def _cleanup():
            try:
                # Clean up tree.
                info("Cleaning up test directory %(TEST_DIR)s" % CONFIG)
                shutil.rmtree("%(TEST_DIR)s" % CONFIG)
            except:
                pass
        atexit.register(_cleanup)

    info("Testing `%(GIT_REVISION)s' in %(TEST_DIR)s" % CONFIG)

    reinitialize_everything = True

    if reinitialize_everything:
        drop_old_data()
        setup_cms()
    else:
        os.chdir("%(TEST_DIR)s/cms" % CONFIG)
        os.environ["PYTHONPATH"] = "%(TEST_DIR)s/cms" % CONFIG
        read_cms_config()

    # Now run the tests from the checkout.
    exec_cmd = " ".join(["./cmstestsuite/RunTests.py"] + args.arguments)
    sh(exec_cmd)
