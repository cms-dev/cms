#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Luca Versari <veluca93@gmail.com>
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

"""This script removes all the unused file objects from the file store,
marking all the executables in the database as bogus if required."""

import argparse
import logging

from cms.db import (Attachment, Executable, File, Manager, PrintJob,
                    SessionGen, Statement, Testcase, UserTest,
                    UserTestExecutable, UserTestFile, UserTestManager,
                    UserTestResult)
from cms.db.filecacher import FileCacher
from cms.server.util import format_size

logger = logging.getLogger()


def make_bogus(session):
    count = 0
    for exe in session.query(Executable).all():
        if exe.digest != FileCacher.bogus_digest():
            count += 1
        exe.digest = FileCacher.bogus_digest()
    logger.info("Made %d executables bogus.", count)


def clean_files(session, dry_run):
    filecacher = FileCacher()
    files = set(file[0] for file in filecacher.list())
    logger.info("A total number of %d files are present", len(files))
    for cls in [Attachment, Executable, File, Manager, PrintJob,
                Statement, Testcase, UserTest, UserTestExecutable,
                UserTestFile, UserTestManager, UserTestResult]:
        for col in ["input", "output", "digest"]:
            if hasattr(cls, col):
                found_digests = set()
                digests = session.query(cls).all()
                digests = [getattr(obj, col) for obj in digests]
                found_digests |= set(digests)
                found_digests.discard(FileCacher.bogus_digest())
                logger.info("Found %d digests while scanning %s.%s",
                            len(found_digests), cls.__name__, col)
                files -= found_digests
    logger.info("%d digests are orphan.", len(files))
    total_size = 0
    for orphan in files:
        total_size += filecacher.get_size(orphan)
    logger.info("Orphan files take %s disk space", format_size(total_size))
    if dry_run:
        return
    for count, orphan in enumerate(files):
        filecacher.delete(orphan)
        if count % 100 == 0:
            logger.info("%d files deleted", count)
    logger.info("All orphan files have been deleted")


def main():
    parser = argparse.ArgumentParser(description="Remove unused file objects "
                                     "from the database. If -b is specified, "
                                     "also mark all executables as bogus")
    parser.add_argument("-b", "--bogus", action="store_true")
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()
    with SessionGen() as session:
        if args.bogus:
            make_bogus(session)
        clean_files(session, args.dry_run)
        if not args.dry_run:
            session.commit()
