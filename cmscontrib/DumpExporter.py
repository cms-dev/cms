#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
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

"""This service exports every data that CMS knows. The process of
exporting and importing again should be idempotent.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import json
import logging
import os
import sys
import tarfile
import tempfile
from datetime import date

from sqlalchemy.types import \
    Boolean, Integer, Float, String, Unicode, DateTime, Interval, Enum
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, JSONB

from cms import rmtree, utf8_decoder
from cms.db import version as model_version, Codename, Filename, \
    FilenameSchema, FilenameSchemaArray, Digest, SessionGen, Contest, User, \
    Task, Submission, UserTest, SubmissionResult, UserTestResult, PrintJob, \
    enumerate_files
from cms.db.filecacher import FileCacher
from cmscommon.datetime import make_timestamp
from cmscommon.digest import path_digest


logger = logging.getLogger(__name__)


def get_archive_info(file_name):
    """Return information about the archive name.

    file_name (string): the file name of the archive to analyze.

    return (dict): dictionary containing the following keys:
                   "basename", "extension", "write_mode"

    """

    # TODO - This method doesn't seem to be a masterpiece in terms of
    # cleanness...
    ret = {"basename": "",
           "extension": "",
           "write_mode": "",
           }
    if not (file_name.endswith(".tar.gz")
            or file_name.endswith(".tar.bz2")
            or file_name.endswith(".tar")
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


def encode_value(type_, value):
    """Encode a given value of a given type to a JSON-compatible form.

    type_ (sqlalchemy.types.TypeEngine): the SQLAlchemy type of the
        column that held the value.
    value (object): the value.

    return (object): the value, encoded as bool, int, float, string,
        list, dict or any other JSON-compatible format.

    """
    if value is None:
        return None
    elif isinstance(type_, (
            Boolean, Integer, Float, String, Unicode, Enum, JSONB, Codename,
            Filename, FilenameSchema, Digest)):
        return value
    elif isinstance(type_, DateTime):
        return make_timestamp(value)
    elif isinstance(type_, Interval):
        return value.total_seconds()
    elif isinstance(type_, (ARRAY, FilenameSchemaArray)):
        return list(encode_value(type_.item_type, item) for item in value)
    elif isinstance(type_, CIDR):
        return str(value)
    else:
        raise RuntimeError("Unknown SQLAlchemy column type: %s" % type_)


class DumpExporter:

    """This service exports every data that CMS knows. The process of
    exporting and importing again should be idempotent.

    """

    def __init__(self, contest_ids, export_target,
                 dump_files, dump_model, skip_generated,
                 skip_submissions, skip_user_tests, skip_print_jobs):
        if contest_ids is None:
            with SessionGen() as session:
                contests = session.query(Contest).all()
                self.contests_ids = [contest.id for contest in contests]
                users = session.query(User).all()
                self.users_ids = [user.id for user in users]
                tasks = session.query(Task)\
                    .filter(Task.contest_id.is_(None)).all()
                self.tasks_ids = [task.id for task in tasks]
        else:
            # FIXME: this is ATM broken, because if you export a contest, you
            # then export the users who participated in it and then all of the
            # contests those users participated in.
            self.contests_ids = contest_ids
            self.users_ids = []
            self.tasks_ids = []
        self.dump_files = dump_files
        self.dump_model = dump_model
        self.skip_generated = skip_generated
        self.skip_submissions = skip_submissions
        self.skip_user_tests = skip_user_tests
        self.skip_print_jobs = skip_print_jobs
        self.export_target = export_target

        # If target is not provided, we use the contest's name.
        if export_target == "":
            self.export_target = "dump_%s.tar.gz" % date.today().isoformat()
            logger.warning("export_target not given, using \"%s\"",
                           self.export_target)

        self.file_cacher = FileCacher()

    def do_export(self):
        """Run the actual export code."""
        logger.info("Starting export.")

        export_dir = self.export_target
        archive_info = get_archive_info(self.export_target)

        if archive_info["write_mode"] != "":
            # We are able to write to this archive.
            if os.path.exists(self.export_target):
                logger.critical("The specified file already exists, "
                                "I won't overwrite it.")
                return False
            export_dir = os.path.join(tempfile.mkdtemp(),
                                      archive_info["basename"])

        logger.info("Creating dir structure.")
        try:
            os.mkdir(export_dir)
        except OSError:
            logger.critical("The specified directory already exists, "
                            "I won't overwrite it.")
            return False

        files_dir = os.path.join(export_dir, "files")
        descr_dir = os.path.join(export_dir, "descriptions")
        os.mkdir(files_dir)
        os.mkdir(descr_dir)

        with SessionGen() as session:
            # Export files.
            logger.info("Exporting files.")
            if self.dump_files:
                for contest_id in self.contests_ids:
                    contest = Contest.get_from_id(contest_id, session)
                    files = enumerate_files(
                        session, contest,
                        skip_submissions=self.skip_submissions,
                        skip_user_tests=self.skip_user_tests,
                        skip_print_jobs=self.skip_print_jobs,
                        skip_generated=self.skip_generated)
                    for file_ in files:
                        if not self.safe_get_file(file_,
                                                  os.path.join(files_dir,
                                                               file_),
                                                  os.path.join(descr_dir,
                                                               file_)):
                            return False

            # Export data in JSON format.
            if self.dump_model:
                logger.info("Exporting data to a JSON file.")

                # We use strings because they'll be the keys of a JSON
                # object
                self.ids = {}
                self.queue = []

                data = dict()

                for cls, lst in [(Contest, self.contests_ids),
                                 (User, self.users_ids),
                                 (Task, self.tasks_ids)]:
                    for i in lst:
                        obj = cls.get_from_id(i, session)
                        self.get_id(obj)

                # Specify the "root" of the data graph
                data["_objects"] = list(self.ids.values())

                while self.queue:
                    obj = self.queue.pop(0)
                    data[self.ids[obj.sa_identity_key]] = \
                        self.export_object(obj)

                data["_version"] = model_version

                destination = os.path.join(export_dir, "contest.json")
                with open(destination, "wt", encoding="utf-8") as fout:
                    json.dump(data, fout, indent=4, sort_keys=True)

        # If the admin requested export to file, we do that.
        if archive_info["write_mode"] != "":
            with tarfile.open(self.export_target,
                              archive_info["write_mode"]) as archive:
                archive.add(export_dir, arcname=archive_info["basename"])
            rmtree(export_dir)

        logger.info("Export finished.")

        return True

    def get_id(self, obj):
        obj_key = obj.sa_identity_key
        if obj_key not in self.ids:
            # We use strings because they'll be the keys of a JSON object
            self.ids[obj_key] = "%d" % len(self.ids)
            self.queue.append(obj)

        return self.ids[obj_key]

    def export_object(self, obj):

        """Export the given object, returning a JSON-encodable dict.

        The returned dict will contain a "_class" item (the name of the
        class of the given object), an item for each column property
        (with a value properly translated to a JSON-compatible type)
        and an item for each relationship property (which will be an ID
        or a collection of IDs).

        The IDs used in the exported dict aren't related to the ones
        used in the DB: they are newly generated and their scope is
        limited to the exported file only. They are shared among all
        classes (that is, two objects can never share the same ID, even
        if they are of different classes).

        If, when exporting the relationship, we find an object without
        an ID we generate a new ID, assign it to the object and append
        the object to the queue of objects to export.

        The self.skip_submissions flag controls whether we export
        submissions (and all other objects that can be reached only by
        passing through a submission) or not.

        """

        cls = type(obj)

        data = {"_class": cls.__name__}

        for prp in cls._col_props:
            col, = prp.columns

            val = getattr(obj, prp.key)
            data[prp.key] = encode_value(col.type, val)

        for prp in cls._rel_props:
            other_cls = prp.mapper.class_

            # Skip submissions if requested
            if self.skip_submissions and other_cls is Submission:
                continue

            # Skip user_tests if requested
            if self.skip_user_tests and other_cls is UserTest:
                continue

            # Skip print jobs if requested
            if self.skip_print_jobs and other_cls is PrintJob:
                continue

            # Skip generated data if requested
            if self.skip_generated and other_cls in (SubmissionResult,
                                                     UserTestResult):
                continue

            val = getattr(obj, prp.key)
            if val is None:
                data[prp.key] = None
            elif isinstance(val, other_cls):
                data[prp.key] = self.get_id(val)
            elif isinstance(val, list):
                data[prp.key] = list(self.get_id(i) for i in val)
            elif isinstance(val, dict):
                data[prp.key] = \
                    dict((k, self.get_id(v)) for k, v in val.items())
            else:
                raise RuntimeError("Unknown SQLAlchemy relationship type: %s"
                                   % type(val))

        return data

    def safe_get_file(self, digest, path, descr_path=None):

        """Get file from FileCacher ensuring that the digest is
        correct.

        digest (string): the digest of the file to retrieve.
        path (string): the path where to save the file.
        descr_path (string): the path where to save the description.

        return (bool): True if all ok, False if something wrong.

        """

        # TODO - Probably this method could be merged in FileCacher

        # First get the file
        try:
            self.file_cacher.get_file_to_path(digest, path)
        except Exception:
            logger.error("File %s could not retrieved from file server.",
                         digest, exc_info=True)
            return False

        # Then check the digest
        calc_digest = path_digest(path)
        if digest != calc_digest:
            logger.critical("File %s has wrong hash %s.",
                            digest, calc_digest)
            return False

        # If applicable, retrieve also the description
        if descr_path is not None:
            with open(descr_path, 'wt', encoding='utf-8') as fout:
                fout.write(self.file_cacher.describe(digest))

        return True


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(description="Exporter of CMS data.")
    parser.add_argument("-c", "--contest-ids", nargs="+", type=int,
                        metavar="contest_id", help="id of contest to export")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-f", "--files", action="store_true",
                       help="only export files, ignore database structure")
    group.add_argument("-F", "--no-files", action="store_true",
                       help="only export database structure, ignore files")
    parser.add_argument("-G", "--no-generated", action="store_true",
                        help="don't export data and files that can be "
                             "automatically generated")
    parser.add_argument("-S", "--no-submissions", action="store_true",
                        help="don't export submissions")
    parser.add_argument("-U", "--no-user-tests", action="store_true",
                        help="don't export user tests")
    parser.add_argument("-P", "--no-print-jobs", action="store_true",
                        help="don't export print jobs")
    parser.add_argument("export_target", action="store",
                        type=utf8_decoder, nargs='?', default="",
                        help="target directory or archive for export")

    args = parser.parse_args()

    exporter = DumpExporter(contest_ids=args.contest_ids,
                            export_target=args.export_target,
                            dump_files=not args.no_files,
                            dump_model=not args.files,
                            skip_generated=args.no_generated,
                            skip_submissions=args.no_submissions,
                            skip_user_tests=args.no_user_tests,
                            skip_print_jobs=args.no_print_jobs)
    success = exporter.do_export()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
