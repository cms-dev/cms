#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import atexit
import tempfile
import subprocess
import shutil
import os
from argparse import ArgumentParser

from cms import utf8_decoder
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
    sh(["git", "clone", CONFIG["GIT_ORIGIN"], CONFIG["TEST_DIR"]])
    os.chdir("%(TEST_DIR)s" % CONFIG)
    sh(["git", "checkout", CONFIG["GIT_REVISION"]])

    info("Configuring CMS.")
    configure_cms(
        {"database": '"postgresql+psycopg2://'
         '%(DB_USER)s:%(DB_PASSWORD)s@'
         '%(DB_HOST)s/%(DB_NAME)s"' % CONFIG,
         "keep_sandbox": "false",
         "contest_listen_address": '["127.0.0.1"]',
         "admin_listen_address": '"127.0.0.1"',
         "min_submission_interval": '0',
         })

    info("Setting environment.")
    os.environ["PYTHONPATH"] = "%(TEST_DIR)s" % CONFIG

    info("Building cms.")
    sh("./setup.py build")
    # Add permission bits to isolate.
    sh("sudo chown root:root isolate/isolate")
    sh("sudo chmod 4755 isolate/isolate")

    # Ensure our logs get preserved. Point them into the checkout instead of
    # the tempdir that we blow away.
    sh(["mkdir", "-p", "%(GIT_ORIGIN)s/log" % CONFIG])
    sh(["ln", "-s", "%(GIT_ORIGIN)s/log" % CONFIG, "log"])

    info("Creating tables.")
    sh("python scripts/cmsInitDB")


if __name__ == "__main__":
    parser = ArgumentParser(
        description="This utility tests a clean checkout of CMS.")
    parser.add_argument(
        "-r", "--revision", action="store", type=utf8_decoder,
        help="Test a specific git revision.")
    parser.add_argument(
        "-k", "--keep-working", action="store_true", default=False,
        help="Do not delete the working directory.")
    parser.add_argument(
        "arguments", action="store", type=utf8_decoder, nargs="*",
        help="All remaining arguments are passed to the test script.")
    args = parser.parse_args()

    CONFIG["TEST_DIR"] = tempfile.mkdtemp()
    CONFIG["CONFIG_PATH"] = "%s/examples/cms.conf" % CONFIG["TEST_DIR"]
    CONFIG["GIT_ORIGIN"] = subprocess.check_output(
        "git rev-parse --show-toplevel", shell=True).strip()
    if args.revision is None:
        CONFIG["GIT_REVISION"] = \
            subprocess.check_output("git rev-parse HEAD", shell=True).strip()
    else:
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
        os.chdir("%(TEST_DIR)s" % CONFIG)
        os.environ["PYTHONPATH"] = "%(TEST_DIR)s" % CONFIG
        read_cms_config()

    # Now run the tests from the checkout.
    sh(["./cmstestsuite/RunTests.py"] + args.arguments)

    # We export the contest, import it again and re-run the tests on the
    # existing contest. Hard-coded contest indicies should be correct, as we
    # own the database.
    sh(["./cmscontrib/ContestExporter.py", "-c", "1"])
    sh(["./cmscontrib/ContestImporter.py", "dump_testcontest1.tar.gz"])
    sh(["./cmstestsuite/RunTests.py", "-c", "2"] + args.arguments)

    # Export coverage results.
    sh("python -m coverage xml --include 'cms*'")
    shutil.copyfile("coverage.xml", "%(GIT_ORIGIN)s/coverage.xml" % CONFIG)
