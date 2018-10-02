#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Luca Versari <veluca93@gmail.com>
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""This script scans the whole database for file objects references
and removes unreferenced file objects from the file store. If required,
it also replaces all the executable digests in the database with a
tombstone digest, to make executables removable in the clean pass.

"""

import argparse
import logging
import sys

from cms.db import SessionGen, Digest, Executable, enumerate_files
from cms.db.filecacher import FileCacher


logger = logging.getLogger()


def make_tombstone(session):
    count = 0
    for exe in session.query(Executable).all():
        if exe.digest != Digest.TOMBSTONE:
            count += 1
        exe.digest = Digest.TOMBSTONE
    logger.info("Replaced %d executables with the tombstone.", count)


def clean_files(session, dry_run):
    filecacher = FileCacher()
    files = set(file[0] for file in filecacher.list())
    logger.info("A total number of %d files are present in the file store",
                len(files))
    found_digests = enumerate_files(session)
    logger.info("Found %d digests while scanning", len(found_digests))
    files -= found_digests
    logger.info("%d digests are orphan.", len(files))
    total_size = 0
    for orphan in files:
        total_size += filecacher.get_size(orphan)
    logger.info("Orphan files take %s bytes of disk space",
                "{:,}".format(total_size))
    if not dry_run:
        for count, orphan in enumerate(files):
            filecacher.delete(orphan)
            if count % 100 == 0:
                logger.info("%d files deleted from the file store", count)
        logger.info("All orphan files have been deleted")


def main():
    parser = argparse.ArgumentParser(
        description="Remove unused file objects from the database. "
        "If -t is specified, also replace all executables with the tombstone")
    parser.add_argument("-t", "--tombstone", action="store_true")
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()
    with SessionGen() as session:
        if args.tombstone:
            make_tombstone(session)
        clean_files(session, args.dry_run)
        if not args.dry_run:
            session.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
