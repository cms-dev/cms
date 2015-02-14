#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import io
import json
import logging
import os
from datetime import timedelta

from sqlalchemy.types import \
    Boolean, Integer, Float, String, Unicode, DateTime, Interval, Enum

import cms.db as class_hook

from cms import utf8_decoder
from cms.db import version as model_version
from cms.db import SessionGen, init_db, drop_db, Submission, UserTest, \
    SubmissionResult, UserTestResult, RepeatedUnicode
from cms.db.filecacher import FileCacher

from cmscontrib import sha1sum
from cmscommon.datetime import make_datetime
from cmscommon.archive import Archive


logger = logging.getLogger(__name__)


def find_root_of_archive(file_names):

    """Given a list of file names (the content of an archive) find the
    name of the root directory, i.e., the only file that would be
    created in a directory if we extract there the archive.

    file_names (list of strings): the list of file names in the
                                  archive

    return (string): the root directory, or None if unable to find
                     (for example if there is more than one).

    """

    current_root = None
    for file_name in file_names:
        if '/' not in file_name or '/' not in file_name[0:-1]:
            if current_root is None:
                current_root = file_name
            else:
                return None
    return current_root


class ContestImporter(object):

    """This service imports a contest from a directory that has been
    the target of a ContestExport. The process of exporting and
    importing again should be idempotent.

    """

    def __init__(self, drop, import_source,
                 load_files, load_model, skip_generated,
                 skip_submissions, skip_user_tests):
        self.drop = drop
        self.load_files = load_files
        self.load_model = load_model
        self.skip_generated = skip_generated
        self.skip_submissions = skip_submissions
        self.skip_user_tests = skip_user_tests

        self.import_source = import_source
        self.import_dir = import_source

        self.file_cacher = FileCacher()

    def do_import(self):
        """Run the actual import code."""
        logger.info("Starting import.")

        archive = None
        if Archive.is_supported(self.import_source):
            archive = Archive(self.import_source)
            self.import_dir = archive.unpack()

            file_names = os.listdir(self.import_dir)
            if len(file_names) != 1:
                logger.critical("Cannot find a root directory in %s.",
                                self.import_source)
                archive.cleanup()
                return False

            self.import_dir = os.path.join(self.import_dir, file_names[0])

        if self.drop:
            logger.info("Dropping and recreating the database.")
            try:
                if not (drop_db() and init_db()):
                    logger.critical("Unexpected error while dropping "
                                    "and recreating the database.",
                                    exc_info=True)
                    return False
            except Exception:
                logger.critical("Unable to access DB.", exc_info=True)
                return False

        with SessionGen() as session:

            # Import the contest in JSON format.
            if self.load_model:
                logger.info("Importing the contest from a JSON file.")

                with io.open(os.path.join(self.import_dir,
                                          "contest.json"), "rb") as fin:
                    # TODO - Throughout all the code we'll assume the
                    # input is correct without actually doing any
                    # validations.  Thus, for example, we're not
                    # checking that the decoded object is a dict...
                    self.datas = json.load(fin, encoding="utf-8")

                # If the dump has been exported using a data model
                # different than the current one (that is, a previous
                # one) we try to update it.
                # If no "_version" field is found we assume it's a v1.0
                # export (before the new dump format was introduced).
                dump_version = self.datas.get("_version", 0)

                if dump_version < model_version:
                    logger.warning(
                        "The dump you're trying to import has been created "
                        "by an old version of CMS (it declares data model "
                        "version %d). It may take a while to adapt it to "
                        "the current data model (which is version %d). You "
                        "can use cmsDumpUpdater to update the on-disk dump "
                        "and speed up future imports.",
                        dump_version, model_version)

                if dump_version > model_version:
                    logger.critical(
                        "The dump you're trying to import has been created "
                        "by a version of CMS newer than this one (it "
                        "declares data model version %d) and there is no "
                        "way to adapt it to the current data model (which "
                        "is version %d). You probably need to update CMS to "
                        "handle it. It is impossible to proceed with the "
                        "importation.", dump_version, model_version)
                    return False

                for version in range(dump_version, model_version):
                    # Update from version to version+1
                    updater = __import__(
                        "cmscontrib.updaters.update_%d" % (version + 1),
                        globals(), locals(), ["Updater"]).Updater(self.datas)
                    self.datas = updater.run()
                    self.datas["_version"] = version + 1

                assert self.datas["_version"] == model_version

                self.objs = dict()
                for id_, data in self.datas.iteritems():
                    if not id_.startswith("_"):
                        self.objs[id_] = self.import_object(data)
                for id_, data in self.datas.iteritems():
                    if not id_.startswith("_"):
                        self.add_relationships(data, self.objs[id_])

                for k, v in list(self.objs.iteritems()):

                    # Skip submissions if requested
                    if self.skip_submissions and isinstance(v, Submission):
                        del self.objs[k]

                    # Skip user_tests if requested
                    if self.skip_user_tests and isinstance(v, UserTest):
                        del self.objs[k]

                    # Skip generated data if requested
                    if self.skip_generated and \
                            isinstance(v, (SubmissionResult, UserTestResult)):
                        del self.objs[k]

                contest_id = list()
                contest_files = set()

                # Add each base object and all its dependencies
                for id_ in self.datas["_objects"]:
                    contest = self.objs[id_]

                    # We explictly add only the contest since all child
                    # objects will be automatically added by cascade.
                    # Adding each object individually would also add
                    # orphaned objects like the ones that depended on
                    # submissions or user_tests that we (possibly)
                    # removed above.
                    session.add(contest)
                    session.flush()

                    contest_id += [contest.id]
                    contest_files |= contest.enumerate_files(
                        self.skip_submissions, self.skip_user_tests,
                        self.skip_generated)

                session.commit()
            else:
                contest_id = None
                contest_files = None

            # Import files.
            if self.load_files:
                logger.info("Importing files.")

                files_dir = os.path.join(self.import_dir, "files")
                descr_dir = os.path.join(self.import_dir, "descriptions")

                files = set(os.listdir(files_dir))
                descr = set(os.listdir(descr_dir))

                if not descr <= files:
                    logger.warning("Some files do not have an associated "
                                   "description.")
                if not files <= descr:
                    logger.warning("Some descriptions do not have an "
                                   "associated file.")

                if not (contest_files is None or files <= contest_files):
                    # FIXME Check if it's because this is a light import
                    # or because we're skipping submissions or user_tests
                    logger.warning("The dump contains some files that are "
                                   "not needed by the contest.")
                if not (contest_files is None or contest_files <= files):
                    # The reason for this could be that it was a light
                    # export that's not being reimported as such.
                    logger.warning("The contest needs some files that are "
                                   "not contained in the dump.")

                # Limit import to files we actually need.
                if contest_files is not None:
                    files &= contest_files

                for digest in files:
                    file_ = os.path.join(files_dir, digest)
                    desc = os.path.join(descr_dir, digest)
                    if not self.safe_put_file(file_, desc):
                        logger.critical("Unable to put file `%s' in the DB. "
                                        "Aborting. Please remove the contest "
                                        "from the database.", file_)
                        # TODO: remove contest from the database.
                        return False

        # Clean up, if an archive was used
        if archive is not None:
            archive.cleanup()

        if contest_id is not None:
            logger.info("Import finished (contest id: %s).",
                        ", ".join("%d" % id_ for id_ in contest_id))
        else:
            logger.info("Import finished.")

        return True

    def import_object(self, data):

        """Import objects from the given data (without relationships).

        The given data is assumed to be a dict in the format produced by
        ContestExporter. This method reads the "_class" item and tries
        to find the corresponding class. Then it loads all column
        properties of that class (those that are present in the data)
        and uses them as keyword arguments in a call to the class
        constructor (if a required property is missing this call will
        raise an error).

        Relationships are not handled by this method, since we may not
        have all referenced objects available yet. Thus we prefer to add
        relationships in a later moment, using the add_relationships
        method.

        Note that both this method and add_relationships don't check if
        the given data has more items than the ones we understand and
        use.

        """

        cls = getattr(class_hook, data["_class"])

        args = dict()

        for prp in cls._col_props:
            if prp.key not in data:
                # We will let the __init__ of the class check if any
                # argument is missing, so it's safe to just skip here.
                continue

            col = prp.columns[0]
            col_type = type(col.type)

            val = data[prp.key]
            if col_type in \
                    [Boolean, Integer, Float, Unicode, RepeatedUnicode, Enum]:
                args[prp.key] = val
            elif col_type is String:
                args[prp.key] = \
                    val.encode('latin1') if val is not None else None
            elif col_type is DateTime:
                args[prp.key] = \
                    make_datetime(val) if val is not None else None
            elif col_type is Interval:
                args[prp.key] = \
                    timedelta(seconds=val) if val is not None else None
            else:
                raise RuntimeError(
                    "Unknown SQLAlchemy column type: %s" % col_type)

        return cls(**args)

    def add_relationships(self, data, obj):

        """Add the relationships to the given object, using the given data.

        Do what we didn't in import_objects: importing relationships.
        We already now the class of the object so we simply iterate over
        its relationship properties trying to load them from the data (if
        present), checking wheter they are IDs or collection of IDs,
        dereferencing them (i.e. getting the corresponding object) and
        reflecting all on the given object.

        Note that both this method and import_object don't check if the
        given data has more items than the ones we understand and use.

        """

        cls = type(obj)

        for prp in cls._rel_props:
            if prp.key not in data:
                # Relationships are always optional
                continue

            val = data[prp.key]
            if val is None:
                setattr(obj, prp.key, None)
            elif type(val) == unicode:
                setattr(obj, prp.key, self.objs[val])
            elif type(val) == list:
                setattr(obj, prp.key, list(self.objs[i] for i in val))
            elif type(val) == dict:
                setattr(obj, prp.key,
                        dict((k, self.objs[v]) for k, v in val.iteritems()))
            else:
                raise RuntimeError(
                    "Unknown RelationshipProperty value: %s" % type(val))

    def safe_put_file(self, path, descr_path):

        """Put a file to FileCacher signaling every error (including
        digest mismatch).

        path (string): the path from which to load the file.
        descr_path (string): same for description.

        return (bool): True if all ok, False if something wrong.

        """

        # TODO - Probably this method could be merged in FileCacher

        # First read the description.
        try:
            with io.open(descr_path, 'rt', encoding='utf-8') as fin:
                description = fin.read()
        except IOError:
            description = ''

        # Put the file.
        try:
            digest = self.file_cacher.put_file_from_path(path, description)
        except Exception as error:
            logger.critical("File %s could not be put to file server (%r), "
                            "aborting.", path, error)
            return False

        # Then check the digest.
        calc_digest = sha1sum(path)
        if digest != calc_digest:
            logger.critical("File %s has hash %s, but the server returned %s, "
                            "aborting.", path, calc_digest, digest)
            return False

        return True


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(description="Importer of CMS contests.")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop everything from the database "
                        "before importing")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-f", "--files", action="store_true",
                       help="only import files, ignore database structure")
    group.add_argument("-F", "--no-files", action="store_true",
                       help="only import database structure, ignore files")
    parser.add_argument("-G", "--no-generated", action="store_true",
                        help="don't import data and files that can be "
                             "automatically generated")
    parser.add_argument("-S", "--no-submissions", action="store_true",
                        help="don't import submissions")
    parser.add_argument("-U", "--no-user-tests", action="store_true",
                        help="don't import user tests")
    parser.add_argument("import_source", action="store", type=utf8_decoder,
                        help="source directory or compressed file")

    args = parser.parse_args()

    ContestImporter(drop=args.drop,
                    import_source=args.import_source,
                    load_files=not args.no_files,
                    load_model=not args.files,
                    skip_generated=args.no_generated,
                    skip_submissions=args.no_submissions,
                    skip_user_tests=args.no_user_tests).do_import()


if __name__ == "__main__":
    main()
