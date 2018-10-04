#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Functions to collect and put files in the format needed for matching.

Provide functions that allow to fetch files from various sources, taking
care of the processing necessary to transform them into CWS's own
format.

"""

import os.path
from collections import namedtuple

from patoolib.util import PatoolError

from cmscommon.archive import Archive


# Represents a file received through HTTP from an HTML form.
# codename (str|None): the name of the form field (in our case it's the
#   filename-with-%l).
# filename (str|None): the name the file had on the user's system.
# content (bytes): the data of the file.
ReceivedFile = namedtuple("ReceivedFile", ["codename", "filename", "content"])


class InvalidArchive(Exception):
    """Raised when the archive submitted by the user cannot be opened."""

    pass


def extract_files_from_archive(data):
    """Return the files contained in the given archive.

    Given the binary data of an archive in any of the formats supported
    by patool, extract its contents and return them in our format. The
    archive's contents must be a valid directory structure (i.e., its
    contents cannot have conflicting/duplicated paths) but the structure
    will be ignored and the files will be returned with their basename.

    data (bytes): the raw contents of the archive.

    return ([ReceivedFile]): the files contained in the archive, with
        their filename filled in but their codename set to None.

    raise (InvalidArchive): if the data doesn't seem to encode an
        archive, its contents are invalid, or other issues.

    """
    archive = Archive.from_raw_data(data)

    if archive is None:
        raise InvalidArchive()

    result = list()

    try:
        archive.unpack()
        for name in archive.namelist():
            with archive.read(name) as f:
                result.append(
                    ReceivedFile(None, os.path.basename(name), f.read()))

    except (PatoolError, OSError):
        raise InvalidArchive()

    finally:
        archive.cleanup()

    return result


def extract_files_from_tornado(tornado_files):
    """Transform some files as received by Tornado into our format.

    Given the files as provided by Tornado on the HTTPServerRequest's
    files attribute, produce a result in our own format. Also, if the
    files look like they consist of just a compressed archive, extract
    it and return its contents instead.

    tornado_files ({str: [tornado.httputil.HTTPFile]}): a bunch of
        files, in Tornado's format.

    return ([ReceivedFile]): the same bunch of files, in our format
        (except if it was an archive: then it's the archive's contents).

    raise (InvalidArchive): if there are issues extracting the archive.

    """
    if len(tornado_files) == 1 and "submission" in tornado_files \
            and len(tornado_files["submission"]) == 1:
        return extract_files_from_archive(tornado_files["submission"][0].body)

    result = list()
    for codename, files in tornado_files.items():
        for f in files:
            result.append(ReceivedFile(codename, f.filename, f.body))
    return result
