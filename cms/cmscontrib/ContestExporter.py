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

from cms.async.AsyncLibrary import Service, logger
from cms.async import ServiceCoord
from cms.service.FileStorage import FileCacher

from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.db.Utils import ask_for_contest
from cms.util.Utils import sha1sum
from cms import Config

class ContestExporter(Service):

    def __init__(self, shard, contest_id, dump,
                 export_dir, skip_submissions):
        self.contest_id = contest_id
        self.export_dir = export_dir
        self.dump = dump
        self.skip_submissions = skip_submissions

        logger.initialize(ServiceCoord("ContestExporter", shard))
        logger.debug("ContestExporter.__init__")
        Service.__init__(self, shard)
        self.FC = FileCacher(self)
        self.add_timeout(self.do_export, None, 10, immediately=True)

    def do_export(self):
        logger.operation = "exporting contest %d" % self.contest_id
        logger.info("Starting export")

        logger.info("Creating dir structure")
        try:
            os.mkdir(self.export_dir)
        except OSError:
            logger.error("The specified directory already exists, "
                         "I won't overwrite it")
            sys.exit(1)
        files_dir = os.path.join(self.export_dir, "files")
        descr_dir = os.path.join(self.export_dir, "descriptions")
        os.mkdir(files_dir)
        os.mkdir(descr_dir)

        with SessionGen(commit=False) as session:

            c = Contest.get_from_id(self.contest_id, session)

            # Export files
            logger.info("Exporting files")
            files = c.enumerate_files(self.skip_submissions)
            for f in files:
                self.safe_get_file(f, os.path.join(files_dir, f),
                                   os.path.join(descr_dir, f))

            # Export the contest in JSON format
            logger.info("Exporting the contest in JSON format")
            with open(os.path.join(self.export_dir,
                                   "contest.json"), 'w') as fout:
                json.dump(c.export_to_dict(self.skip_submissions), fout, indent=4)

        # The database dump is never used; however, this part is
        # retained for historical reasons
        if self.dump:

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
                    export_res = os.system('pg_dump -h %s -U %s -w %s -x " \
                        "--attribute-inserts > %s' % (host, username, database,
                                                      db_exportfile))
                    del os.environ['PGPASSWORD']
                    if export_res != 0:
                        logger.critical("Database export failed")
                        sys.exit(1)
                else:
                    logger.critical("Cannot obtain parameters for "
                                    "database connection")
                    sys.exit(1)

            # Export procedure for SQLite
            elif engine == 'sqlite':
                db_regex = re.compile('///(.*)')
                db_match = db_regex.match(connection)
                if db_match is not None:
                    dbfile, = db_match.groups()
                    export_res = os.system('sqlite3 %s .dump > %s' % (dbfile, db_exportfile))
                    if export_res != 0:
                        logger.critical("Database export failed")
                        sys.exit(1)
                else:
                    logger.critical("Cannot obtain parameters for "
                                    "database connection")
                    sys.exit(1)

            else:
                logger.critical("Database engine not supported :-(")
                sys.exit(1)

        logger.info("Export finished")
        logger.operation = ""
        self.exit()
        return False

    def safe_get_file(self, digest, path, descr_path=None):
        # First get the file
        try:
            self.FC.get_file(digest, path=path)
        except Exception as e:
            logger.error("File %s could not retrieved from file server "
                         "(%r), aborting..." % (digest, e))
            sys.exit(1)

        # Then check the digest
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.error("File %s has wrong hash %s, aborting..." %
                         (digest, calc_digest))
            sys.exit(1)

        # If applicable, retrieve also the description
        if descr_path is not None:
            with open(descr_path, 'w') as fout:
                fout.write(self.FC.describe(digest))

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-c", "--contest", help="contest ID to export",
                      dest="contest_id", action="store", type="int",
                      default=None)
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int",
                      default=None)
    parser.add_option("-d", "--dump-database",
                      help="include a SQL dump of the database (this will "
                      "disclose data about other contests stored in the same "
                      "database)",
                      dest="dump", action="store_true", default=False)
    parser.add_option("-S", "--skip-submissions",
                      help="don't export submissions, only contest data",
                      dest="skip_submissions", action="store_true", default=False)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, "
                     "the directory where to export the contest")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")

    if options.contest_id is None:
        options.contest_id = ask_for_contest()

    contest_exporter = ContestExporter(shard=options.shard,
                                       contest_id=options.contest_id,
                                       dump=options.dump,
                                       export_dir=args[0],
                                       skip_submissions=options.skip_submissions).run()

if __name__ == "__main__":
    main()
