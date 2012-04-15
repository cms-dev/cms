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

"""This service imports a contest from a directory that has been the
target of a ContestExport. The process of exporting and importing
again should be idempotent.

"""

import os
import argparse
import shutil
import simplejson as json
import tempfile

import sqlalchemy.exc
import tarfile
import zipfile

from cms import logger
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import SessionGen, Contest, metadata

from cmscontrib import sha1sum


def find_root_of_archive(file_names):
    """Given a list of file names (the content of an archive) find the
    name of the root directory, i.e., the only file that would be
    created in a directory if we extract there the archive.

    file_names (list of strings): the list of file names in the
                                  archive

    return (string): the root directory, or None if unable to find.

    """
    current_root = None
    for file_name in file_names:
        if '/' not in file_name:
            if current_root is None:
                current_root = file_name
            else:
                return None
    return current_root


class ContestImporter:
    """This service imports a contest from a directory that has been
    the target of a ContestExport. The process of exporting and
    importing again should be idempotent.

    """
    def __init__(self, drop, import_source, only_files, no_files):
        self.drop = drop
        self.only_files = only_files
        self.no_files = no_files
        self.import_source = import_source
        self.import_dir = import_source

        self.file_cacher = FileCacher()

    def run(self):
        """Interface to make the class do its job."""
        return self.do_import()

    def do_import(self):
        """Run the actual import code.

        """
        logger.operation = "importing contest from %s" % self.import_source
        logger.info("Starting import.")

        if not os.path.isdir(self.import_source):
            if self.import_source.endswith(".zip"):
                archive = zipfile.ZipFile(self.import_source, "r")
                file_names = archive.infolist()

                self.import_dir = tempfile.mkdtemp()
                archive.extractall(self.import_dir)
            elif self.import_source.endswith(".tar.gz") \
                     or self.import_source.endswith(".tgz") \
                     or self.import_source.endswith(".tar.bz2") \
                     or self.import_source.endswith(".tbz2") \
                     or self.import_source.endswith(".tar"):
                archive = tarfile.open(name=self.import_source)
                file_names = archive.getnames()
            else:
                logger.critical("Unable to import from %s." %
                                self.import_source)
                return False

            root = find_root_of_archive(file_names)
            if root is None:
                logger.critical("Cannot find a root directory in %s." %
                                self.import_source)
                return False

            self.import_dir = tempfile.mkdtemp()
            archive.extractall(self.import_dir)
            self.import_dir = os.path.join(self.import_dir, root)

        if self.drop:
            logger.info("Dropping and recreating the database.")
            try:
                metadata.drop_all()
            except sqlalchemy.exc.OperationalError as error:
                logger.critical("Unable to access DB.\n%r" % error)
                return False
        try:
            metadata.create_all()
        except sqlalchemy.exc.OperationalError as error:
            logger.critical("Unable to access DB.\n%r" % error)
            return False

        if not self.no_files:
            logger.info("Importing files.")
            files_dir = os.path.join(self.import_dir, "files")
            descr_dir = os.path.join(self.import_dir, "descriptions")
            files = set(os.listdir(files_dir))
            for _file in files:
                if not self.safe_put_file(os.path.join(files_dir, _file),
                                          os.path.join(descr_dir, _file)):
                    return False

        if not self.only_files:
            with SessionGen(commit=False) as session:

                # Import the contest in JSON format.
                logger.info("Importing the contest from JSON file.")
                with open(os.path.join(self.import_dir,
                                       "contest.json")) as fin:
                    contest = Contest.import_from_dict(json.load(fin))
                    session.add(contest)

                # Check that no files were missing (only if files were
                # imported).
                if not self.no_files:
                    contest_files = contest.enumerate_files()
                    missing_files = contest_files.difference(files)
                    if len(missing_files) > 0:
                        logger.warning("Some files needed to the contest "
                                       "are missing in the import directory.")

                session.flush()
                contest_id = contest.id
                session.commit()

        logger.info("Import finished (contest id: %s)." % contest_id)
        logger.operation = ""

        # If we extracted an archive, we remove it.
        if self.import_dir != self.import_source:
            shutil.rmtree(self.import_dir)

        return True

    def safe_put_file(self, path, descr_path):
        """Put a file to FileCacher signaling every error (including
        digest mismatch).

        path (string): the path from which to load the file.
        descr_path (string): same for description.

        return (bool): True if all ok, False if something wrong.

        """
        # First read the description.
        try:
            with open(descr_path) as fin:
                description = fin.read()
        except IOError:
            description = ''

        # Put the file.
        try:
            digest = self.file_cacher.put_file(path=path,
                                               description=description)
        except Exception as error:
            logger.error("File %s could not be put to file server (%r), "
                         "aborting." % (path, error))
            return False

        # Then check the digest.
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.error("File %s has hash %s, but the server returned %s, "
                         "aborting." % (path, calc_digest, digest))
            return False

        return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Importer of CMS contests")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-f", "--only-files", action="store_true",
                       help="only import files, ignore database structure")
    group.add_argument("-F", "--no-files", action="store_true",
                       help="only import database structure, ignore files")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop everything from the database "
                        "before importing")
    parser.add_argument("import_source",
                        help="source directory or compressed file")

    args = parser.parse_args()

    ContestImporter(drop=args.drop,
                    import_source=args.import_source,
                    only_files=args.only_files,
                    no_files=args.no_files).run()


if __name__ == "__main__":
    main()
