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

import io
import pathlib
import typing

if typing.TYPE_CHECKING:
    from tornado.httputil import HTTPFile

from cmscommon.archive import open_archive


# Represents a file received through HTTP from an HTML form.
# codename: the name of the form field (in our case it's the
#   filename-with-%l).
# filename: the name the file had on the user's system.
# content: the data of the file.
class ReceivedFile(typing.NamedTuple):
    codename: str | None
    filename: str | None
    content: bytes


class InvalidArchive(Exception):
    """Raised when the archive submitted by the user cannot be opened."""

    def __init__(self, too_big: bool = False, too_many_files: bool = False):
        """
        too_big: Whether the InvalidArchive was raised because the files in it
            exceeded the size limit after decompression.
        too_many_files: Whether the InvalidArchive was raised because the
            archive contained more than the maximum number of files.
        """
        self.too_big = too_big
        self.too_many_files = too_many_files
        super().__init__()


def extract_files_from_archive(
    data: bytes, max_size: int | None = None, max_files: int | None = None
) -> list[ReceivedFile]:
    """Return the files contained in the given archive.

    Given the binary data of an archive in a supported format, extract its
    contents and return them in our format. The directory structure of the
    archive is ignored; files will be returned with their basename.

    data: the raw contents of the archive.
    max_size: maximum decompressed size of the archive.
    max_files: maximum number of files to allow in the archive.

    return: the files contained in the archive, with
        their filename filled in but their codename set to None.

    raise (InvalidArchive): if the data doesn't seem to encode an
        archive, its contents are invalid, or other issues.

    """

    result: list[ReceivedFile] = []
    total_size = 0
    try:
        archive = open_archive(io.BytesIO(data))
        for (filepath, size, handle) in archive.iter_regular_files():
            total_size += size
            if max_size is not None and total_size > max_size:
                raise InvalidArchive(too_big=True)
            if max_files is not None and len(result) + 1 > max_files:
                raise InvalidArchive(too_many_files=True)
            filedata = archive.get_file_bytes(handle)
            # archive file paths are always /-separated, so we can use
            # PosixPath to extract the basename.
            filename = pathlib.PurePosixPath(filepath).name
            result.append(ReceivedFile(None, filename, filedata))
    except InvalidArchive:
        raise
    # the Archive class might raise all kinds of exceptions when fed invalid data. Catch them all here.
    except Exception:
        raise InvalidArchive()

    return result


def extract_files_from_tornado(
    tornado_files: dict[str, list["HTTPFile"]],
    max_size: int | None = None,
    max_files: int | None = None,
) -> list[ReceivedFile]:
    """Transform some files as received by Tornado into our format.

    Given the files as provided by Tornado on the HTTPServerRequest's
    files attribute, produce a result in our own format. Also, if the
    files look like they consist of just a compressed archive, extract
    it and return its contents instead.

    tornado_files: a bunch of files, in Tornado's format.
    max_size: limit on total size of decompressed files
        (protects against zip bombs).
    max_files: maximum number of files to allow in the archive

    return: the same bunch of files, in our format
        (except if it was an archive: then it's the archive's contents).

    raise (InvalidArchive): if there are issues extracting the archive.

    """
    if (
        len(tornado_files) == 1
        and "submission" in tornado_files
        and len(tornado_files["submission"]) == 1
    ):
        return extract_files_from_archive(
            tornado_files["submission"][0].body, max_size, max_files
        )

    result = list()
    for codename, files in tornado_files.items():
        for f in files:
            result.append(ReceivedFile(codename, f.filename, f.body))
    return result
