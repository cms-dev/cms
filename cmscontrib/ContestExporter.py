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

"""This service exports every data about the contest that CMS
knows. The process of exporting and importing again should be
idempotent.

"""

import argparse
import os
import re
import shutil
import simplejson as json
import tempfile

import tarfile

from cms import config, logger
from cms.db import ask_for_contest
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import SessionGen, Contest

from cmscontrib import sha1sum


def get_archive_info(file_name):
    """Return information about the archive name.

    file_name (string): the file name of the archive to analyze.

    return (dict): dictionary containing the following keys:
                   "basename", "extension", "write_mode"

    """
    ret = {"basename": "",
           "extension": "",
           "write_mode": "",
           }
    if not (file_name.endswith(".tar.gz") \
           or file_name.endswith(".tar.bz2") \
           or file_name.endswith(".tar") \
           or file_name.endswith(".zip")):
        return ret

    if file_name.endswith(".tar"):
        ret["basename"] = os.path.basename(file_name[:-4])
        ret["extension"] = "tar"
        ret["write_mode"] = "w:"
    elif file_name.endswith(".tar.gz"):
        ret["basename"] = os.path.basename(file_name[:-7])
        ret["extension"] = "tar.gz"
        ret["write_mode"] = "w:gz"
    elif file_name.endswith(".tar.bz2"):
        ret["basename"] = os.path.basename(file_name[:-8])
        ret["extension"] = "tar.bz2"
        ret["write_mode"] = "w:bz2"
    elif file_name.endswith(".zip"):
        ret["basename"] = os.path.basename(file_name[:-4])
        ret["extension"] = "zip"
        ret["write_mode"] = ""

    return ret


class ContestExporter:
    """This service exports every data about the contest that CMS
    knows. The process of exporting and importing again should be
    idempotent.

    """
    def __init__(self, contest_id, dump, export_target, skip_submissions,
                 light):
        self.contest_id = contest_id
        self.dump = dump
        self.skip_submissions = skip_submissions
        self.light = light

        # If target is not provided, we use the contest's name.
        if export_target == "":
            with SessionGen(commit=False) as session:
                contest = Contest.get_from_id(self.contest_id, session)
                self.export_target = "dump_%s.tar.gz" % contest.name
        else:
            self.export_target = export_target

        self.file_cacher = FileCacher()

    def run(self):
        """Interface to make the class do its job."""
        return self.do_export()

    def do_export(self):
        """Run the actual export code.

        """
        logger.operation = "exporting contest %d" % self.contest_id
        logger.info("Starting export.")

        export_dir = self.export_target
        archive_info = get_archive_info(self.export_target)

        if archive_info["write_mode"] != "":
            # We are able to write to this archive.
            if os.path.exists(self.export_target):
                logger.error("The specified file already exists, "
                             "I won't overwrite it.")
                return False
            export_dir = os.path.join(tempfile.mkdtemp(),
                                      archive_info["basename"])

        logger.info("Creating dir structure.")
        try:
            os.mkdir(export_dir)
        except OSError:
            logger.error("The specified directory already exists, "
                         "I won't overwrite it.")
            return False

        files_dir = os.path.join(export_dir, "files")
        descr_dir = os.path.join(export_dir, "descriptions")
        os.mkdir(files_dir)
        os.mkdir(descr_dir)

        with SessionGen(commit=False) as session:

            contest = Contest.get_from_id(self.contest_id, session)

            # Export files.
            logger.info("Exporting files.")
            files = contest.enumerate_files(self.skip_submissions,
                                            light=self.light)
            for _file in files:
                if not self.safe_get_file(_file,
                                          os.path.join(files_dir, _file),
                                          os.path.join(descr_dir, _file)):
                    return False

            # Export the contest in JSON format.
            logger.info("Exporting the contest in JSON format.")
            with open(os.path.join(export_dir, "contest.json"), 'w') as fout:
                json.dump(contest.export_to_dict(self.skip_submissions),
                          fout, indent=4)

        if self.dump:
            if not self.dump_database(export_dir):
                return False

        # If the admin requested export to file, we do that.
        if archive_info["write_mode"] != "":
            archive = tarfile.open(self.export_target,
                                   archive_info["write_mode"])
            archive.add(export_dir, arcname=archive_info["basename"])
            archive.close()
            shutil.rmtree(export_dir)

        logger.info("Export finished.")
        logger.operation = ""

        return True

    def dump_database(self, export_dir):
        """Dump the whole database. This is never used; however, this
        part is retained for historical reasons.

        """
        # Warning: this part depends on the specific database used.
        logger.info("Dumping SQL database.")
        (engine, connection) = config.database.split(':', 1)
        db_exportfile = os.path.join(export_dir, "database_dump.sql")

        # Export procedure for PostgreSQL.
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
                    logger.critical("Database export failed.")
                    return False
            else:
                logger.critical("Cannot obtain parameters for "
                                "database connection.")
                return False

        # Export procedure for SQLite.
        elif engine == 'sqlite':
            db_regex = re.compile('///(.*)')
            db_match = db_regex.match(connection)
            if db_match is not None:
                dbfile, = db_match.groups()
                export_res = os.system('sqlite3 %s .dump > %s' %
                                       (dbfile, db_exportfile))
                if export_res != 0:
                    logger.critical("Database export failed.")
                    return False
            else:
                logger.critical("Cannot obtain parameters for "
                                "database connection.")
                return False

        else:
            logger.critical("Database engine not supported. :-(")
            return False

        return True

    def safe_get_file(self, digest, path, descr_path=None):
        """Get file from FileCacher ensuring that the digest is
        correct.

        digest (string): the digest of the file to retrieve.
        path (string): the path where to save the file.
        descr_path (string): the path where to save the description.

        return (bool): True if all ok, False if something wrong.

        """
        # First get the file
        try:
            self.file_cacher.get_file(digest, path=path)
        except Exception as error:
            logger.error("File %s could not retrieved from file server (%r)." %
                         (digest, error))
            return False

        # Then check the digest
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.error("File %s has wrong hash %s." % (digest, calc_digest))
            return False

        # If applicable, retrieve also the description
        if descr_path is not None:
            with open(descr_path, 'wb') as fout:
                try:
                    fout.write(self.file_cacher.describe(digest))
                except UnicodeEncodeError:
                    logger.warning("Caught a UnicodeDecodeError when writing "
                                   "the description for file %s" % (digest))

        return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Exporter of CMS contests.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest to export")
    parser.add_argument("-d", "--dump-database", action="store_true",
                        help="include a SQL dump of the database (this will "
                        "disclose data about other contests stored in the "
                        "same database) - deprecated")
    parser.add_argument("-s", "--skip-submissions", action="store_true",
                        help="don't export submissions, only contest data")
    parser.add_argument("-l", "--light", action="store_true",
                        help="light export (without executables and "
                        "testcases)")
    parser.add_argument("export_target", nargs='?', default="",
                        help="target directory or archive for export")

    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    ContestExporter(contest_id=args.contest_id,
                    dump=args.dump_database,
                    export_target=args.export_target,
                    skip_submissions=args.skip_submissions,
                    light=args.light).run()


if __name__ == "__main__":
    main()
