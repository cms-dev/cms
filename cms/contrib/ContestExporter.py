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

class ContestExporter(Service):

    def __init__(self, shard, contest_id, export_dir):
        self.contest_id = contest_id
        self.export_dir = export_dir

        logger.initialize(ServiceCoord("ContestExporter", shard))
        logger.debug("ContestExporter.__init__")
        Service.__init__(self, shard)
        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        if not self.FS.connected:
            logger.error("Please run the FileStorage service.")
            self.exit()
        self.FC = FileCacher(self, self.FS)


    def do_export(self):
        logger.operation = "exporting contest %d" % (self.contest_id)
        logger.info("Starting export")

        logger.info("Creating dir structure")
        try:
            os.mkdir(self.export_dir)
        except OSError:
            logger.error("The specified directory already exists, I won't overwrite it")
            sys.exit(1)
        files_dir = os.path.join(self.export_dir, "files")
        os.mkdir(files_dir)

        with SessionGen() as session:

            c = Contest.get_from_id(self.contest_id, session)

            for task in c.tasks:
                logger.info("Exporting files for task %d" % task.id)

                # Export attachments
                for f in task.attachments.values():
                    self.safe_get_file(f.digest, os.path.join(files_dir, f.digest))

                # Export managers
                for f in task.managers.values():
                    self.safe_get_file(f.digest, os.path.join(files_dir, f.digest))

                # Export testcases
                for testcase in task.testcases:
                    self.safe_get_file(testcase.input, os.path.join(files_dir, testcase.input))
                    self.safe_get_file(testcase.output, os.path.join(files_dir, testcase.output))

            for submission in c.get_submissions(session):
                logger.info("Exporting files for submission %d" % submission.id)

                # Export files
                for f in submission.files.values():
                    self.safe_get_file(f.digest, os.path.join(files_dir, f.digest))

                # Export executables
                for f in submission.executables.values():
                    self.safe_get_file(f.digest, os.path.join(files_dir, f.digest))

            # Export the contest in JSON format
            logger.info("Exporting the contest in JSON format")
            with open(os.path.join(self.export_dir, "contest.json"), 'w') as fout:
                json.dump(c.export_to_dict(), fout, indent=4)

            # Warning: this part depends on the specific database used
            logger.info("Dumping SQL database")
            (engine, connection) = Config.database.split(':', 1)
            db_exportfile = os.path.join(self.export_dir, "database_dump.sql")

            # Export procedure for PostgreSQL
            if engine == 'postgresql':
                db_regex = re.compile('//(\w*):(\w*)@(\w*)/(\w*)')
                db_match = db_regex.match(connection)
                if db_match is not None:
                    username, password, host, database = db_match.groups()
                    os.environ['PGPASSWORD'] = password
                    export_res = os.system('pg_dump -h %s -U %s -w %s -x --inserts | grep "^INSERT" > %s' % (host, username, database, db_exportfile))
                    del os.environ['PGPASSWORD']
                    if export_res != 0:
                        logger.critical("Database export failed")
                        sys.exit(1)
                else:
                    logger.critical("Cannot obtain parameters for database connection")
                    sys.exit(1)

            # Export procedure for SQLite
            elif engine == 'sqlite':
                db_regex = re.compile('///(.*)')
                db_match = db_regex.match(connection)
                if db_match is not None:
                    dbfile, = db_match.groups()
                    export_res = os.system('sqlite3 %s .dump | grep "^INSERT" > %s' % (dbfile, db_exportfile))
                    if export_res != 0:
                        logger.critical("Database export failed")
                        sys.exit(1)
                else:
                    logger.critical("Cannot obtain parameters for database connection")
                    sys.exit(1)

            else:
                logger.critical("Database engine not supported :-(")
                sys.exit(1)

            logger.info("Export finished")
            logger.operation = ""

    def safe_get_file(self, digest, path):
        # First get the file
        try:
            self.FC.get_file_to_path(digest, path, sync=True)
        except SyncRPCError:
            logger.critical("File %s could not retrieved from file server, aborting..." % digest)
            sys.exit(1)

        # Then check the digest
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.critical("File %s has wrong hash %s, aborting..." % (digest, calc_digest))
            sys.exit(1)

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-c", "--contest", help="contest ID to export",
                      dest="contest_id", action="store", type="int", default=None)
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the directory where to export the contest")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")

    if options.contest_id is None:
        options.contest_id = ask_for_contest()

    contest_exporter = ContestExporter(shard=options.shard, contest_id=options.contest_id, export_dir=args[0])
    contest_exporter.do_export()

if __name__ == "__main__":
    main()
