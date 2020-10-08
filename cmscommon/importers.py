#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

import logging
import zipfile

from cms.db import Testcase


logger = logging.getLogger(__name__)


def import_testcases_from_zipfile(
        session, file_cacher, dataset,
        archive, input_re, output_re, overwrite, public):
    """Import testcases from a zipped archive

    session (Session): session to use to add the testcases.
    file_cacher (FileCacher): interface to access the files in the DB.
    dataset (Dataset): dataset where to add the testcases.
    archive (File): file-like object representing a zip file.
    input_re (_sre.SRE_Pattern): regular expression matching the input
        filenames (e.g., re.compile(r"input_(.*).txt)).
    output_re (_sre.SRE_Pattern): regular expression matching the output
        filenames (e.g., re.compile(r"output_(.*).txt)).
    overwrite (bool): whether to overwrite existing testcases.
    public (bool): whether to mark the new testcases as public.

    return ((unicode, unicode)): subject and text of a message describing
        the outcome of the operation.

    """
    task_name = dataset.task.name
    try:
        with zipfile.ZipFile(archive, "r") as archive_zfp:
            tests = dict()
            # Match input/output file names to testcases' codenames.
            for filename in archive_zfp.namelist():
                match = input_re.match(filename)
                if match:
                    codename = match.group(1)
                    if codename not in tests:
                        tests[codename] = [None, None]
                    tests[codename][0] = filename
                else:
                    match = output_re.match(filename)
                    if match:
                        codename = match.group(1)
                        if codename not in tests:
                            tests[codename] = [None, None]
                        tests[codename][1] = filename

            skipped_tc = []
            overwritten_tc = []
            added_tc = []
            for codename, testdata in tests.items():
                # If input or output file isn't found, skip it.
                if not testdata[0] or not testdata[1]:
                    continue

                # Check, whether current testcase already exists.
                if codename in dataset.testcases:
                    # If we are allowed, remove existing testcase.
                    # If not - skip this testcase.
                    if overwrite:
                        testcase = dataset.testcases[codename]
                        session.delete(testcase)
                        try:
                            session.commit()
                        except Exception:
                            skipped_tc.append(codename)
                            continue
                        overwritten_tc.append(codename)
                    else:
                        skipped_tc.append(codename)
                        continue

                # Add current testcase.
                try:
                    input_ = archive_zfp.read(testdata[0])
                    output = archive_zfp.read(testdata[1])
                except Exception:
                    raise Exception("Reading testcase %s failed" % codename)
                try:
                    input_digest = file_cacher.put_file_content(
                        input_, "Testcase input for task %s" % task_name)
                    output_digest = file_cacher.put_file_content(
                        output, "Testcase output for task %s" % task_name)
                except Exception:
                    raise Exception("Testcase storage failed")

                testcase = Testcase(codename, public, input_digest,
                                    output_digest, dataset=dataset)
                session.add(testcase)
                try:
                    session.commit()
                except Exception:
                    raise Exception("Couldn't add test %s" % codename)
                if codename not in overwritten_tc:
                    added_tc.append(codename)
    except zipfile.BadZipfile:
        raise Exception(
            "The selected file is not a zip file. "
            "Please select a valid zip file.")

    return (
        "Successfully added %d and overwritten %d testcase(s)" %
        (len(added_tc), len(overwritten_tc)),
        "Added: %s; overwritten: %s; skipped: %s" %
        (", ".join(added_tc) if added_tc else "none",
         ", ".join(overwritten_tc) if overwritten_tc else "none",
         ", ".join(skipped_tc) if skipped_tc else "none"))
