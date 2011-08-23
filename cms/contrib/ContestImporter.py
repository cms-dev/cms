#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import sys
import os
import codecs
import optparse
import re
import json

from cms.async.AsyncLibrary import Service, logger, SyncRPCError
from cms.async import ServiceCoord
from cms.service.FileStorage import FileCacher

from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.db.Utils import ask_for_contest
from cms.util.Utils import sha1sum
from cms import Config

class ContestImporter(Service):

    def __init__(self, shard, import_dir):
        self.import_dir = import_dir

        logger.initialize(ServiceCoord("ContestImporter", shard))
        logger.debug("ContestImporter.__init__")
        Service.__init__(self, shard)
        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        if not self.FS.connected:
            logger.error("Please run the FileStorage service.")
            self.exit()
        self.FC = FileCacher(self, self.FS)


    def do_import(self):
        logger.operation = "importing contest from %s" % (self.import_dir)
        logger.info("Starting import")

        logger.info("Importing files")
        files_dir = os.path.join(self.import_dir, "files")
        files = os.listdir(files_dir)
        for file in files:
            self.safe_put_file(os.path.join(files_dir, file))

        with SessionGen() as session:

            # Import the contest in JSON format
            logger.info("Importing the contest from JSON file")
            with open(os.path.join(self.import_dir, "contest.json")) as fin:
                c = Contest.import_from_dict(json.load(fin))
                session.add(c)

        logger.info("Import finished")
        logger.operation = ""

    def safe_put_file(self, path):
        # First put the file
        try:
            digest = self.FC.put_file_from_path(path, sync=True)
        except SyncRPCError:
            logger.error("File %s could not be put to file server, aborting..." % path)
            sys.exit(1)

        # Then check the digest
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.error("File %s has hash %s, but the server returned %d, aborting..." % (path, calc_digest, digest))
            sys.exit(1)

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the directory from where to import the contest")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")

    contest_importer = ContestImporter(shard=options.shard,
                                       import_dir=args[0])
    contest_importer.do_import()

if __name__ == "__main__":
    main()
