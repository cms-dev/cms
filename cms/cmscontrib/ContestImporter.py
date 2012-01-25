#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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
import optparse
import json

from cms.async import ServiceCoord
from cms.async.AsyncLibrary import Service
from cms.db.SQLAlchemyAll import SessionGen, Contest, metadata
from cms.service.FileStorage import FileCacher
from cms.service.LogService import logger
from cms.util.Utils import sha1sum


class ContestImporter(Service):

    def __init__(self, shard, drop, import_dir, only_files, no_files):
        self.import_dir = import_dir
        self.drop = drop
        self.only_files = only_files
        self.no_files = no_files

        logger.initialize(ServiceCoord("ContestImporter", shard))
        Service.__init__(self, shard, custom_logger=logger)
        self.FC = FileCacher(self)
        self.add_timeout(self.do_import, None, 10, immediately=True)

    def do_import(self):
        logger.operation = "importing contest from %s" % (self.import_dir)
        logger.info("Starting import")

        if self.drop:
            logger.info("Dropping and recreating the database")
            metadata.drop_all()
        metadata.create_all()

        if not self.no_files:
            logger.info("Importing files")
            files_dir = os.path.join(self.import_dir, "files")
            descr_dir = os.path.join(self.import_dir, "descriptions")
            files = set(os.listdir(files_dir))
            for file in files:
                self.safe_put_file(os.path.join(files_dir, file),
                                   os.path.join(descr_dir, file))

        if not self.only_files:
            with SessionGen(commit=False) as session:

                # Import the contest in JSON format
                logger.info("Importing the contest from JSON file")
                with open(os.path.join(self.import_dir,
                                       "contest.json")) as fin:
                    c = Contest.import_from_dict(json.load(fin))
                    session.add(c)

                # Check that no files were missing (only if files were
                # imported)
                if not self.no_files:
                    contest_files = c.enumerate_files()
                    missing_files = contest_files.difference(files)
                    if len(missing_files) > 0:
                        logger.warning("Some files needed to the contest "
                                       "are missing in the import directory")

                session.flush()
                contest_id = c.id
                session.commit()

        logger.info("Import finished (contest id: %d)" % (contest_id))
        logger.operation = ""
        self.exit()
        return False

    def safe_put_file(self, path, descr_path):
        # First read the description
        try:
            with open(descr_path) as fin:
                description = fin.read()
        except IOError:
            description = ''

        # Put the file
        try:
            digest = self.FC.put_file(path=path, description=description)
        except Exception as error:
            logger.error("File %s could not be put to file server (%r), "
                         "aborting..." % (path, error))
            sys.exit(1)

        # Then check the digest
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.error("File %s has hash %s, but the server returned %d, "
                         "aborting..." % (path, calc_digest, digest))
            sys.exit(1)


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    parser.add_option("-d", "--drop", dest="drop",
                      help="drop everything from the database "
                      "before importing",
                      default=False, action="store_true")
    parser.add_option("-f", "--only-files", dest="only_files",
                      help="only import files, ignore database structure",
                      default=False, action="store_true")
    parser.add_option("-F", "--no-files", dest="no_files",
                      help="only import database structure, ignore files",
                      default=False, action="store_true")
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the directory "
                     "from where to import the contest")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")
    if options.only_files and options.no_files:
        parser.error("Only one of `-f' and `-F' can be specified")

    ContestImporter(shard=options.shard,
                    drop=options.drop,
                    import_dir=args[0],
                    only_files=options.only_files,
                    no_files=options.no_files).run()


if __name__ == "__main__":
    main()
