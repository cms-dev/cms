#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014-2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Abstraction layer for reading from and writing to archives.

"""

from abc import ABCMeta, abstractmethod
from collections.abc import Generator, Iterable
import os
import shutil
import tarfile
import tempfile
import typing
import zipfile

import patoolib
from patoolib.util import PatoolError

from cms import config


class ArchiveException(Exception):
    """Exception for when the interaction with the Archive class is
    incorrect.

    """
    pass


class Archive:
    """Class to manage archives.

    This class has static methods to test, extract, and create
    archives. Moreover, an instance of this class can be create to
    manage an existing archive. At the moment, all operations depend
    on calling first the unpack method, that extract the archive in a
    temporary directory.

    """

    @staticmethod
    def is_supported(path: str) -> bool:
        """Return whether the file at path is supported by patoolib.

        path: the path to test.

        return: whether path is supported.

        """
        try:
            patoolib.test_archive(path, interactive=False)
            return True
        except PatoolError:
            return False

    @staticmethod
    def create_from_dir(from_dir: str, archive_path: str):
        """Create a new archive containing all files in from_dir.

        from_dir: directory with the files to archive.
        archive_path: the new archive's path.

        """
        files = tuple(os.listdir(from_dir))
        cwd = os.getcwd()
        os.chdir(from_dir)
        patoolib.create_archive(archive_path, files, interactive=False)
        os.chdir(cwd)

    @staticmethod
    def extract_to_dir(archive_path: str, to_dir: str):
        """Extract the content of an archive in to_dir.

        archive_path: path of the archive to extract.
        to_dir: destination directory.

        """
        patoolib.extract_archive(archive_path, outdir=to_dir, interactive=False)

    @staticmethod
    def from_raw_data(raw_data: bytes) -> "Archive | None":
        """Create an Archive object out of raw archive data.

        This method treats the given string as archive data: it dumps it
        into a temporary file, then creates an Archive object. Since the
        user did not provide a path, we assume that when cleanup() is
        called the temporary file should be deleted as well as unpacked
        data.

        raw_data: the actual bytes that form the archive.

        return: an object that represents the new
            archive or None, if raw_data doesn't represent an archive.

        """
        temp_file, temp_filename = tempfile.mkstemp(dir=config.global_.temp_dir)
        with open(temp_file, "wb") as temp_file:
            temp_file.write(raw_data)

        try:
            return Archive(temp_filename, delete_source=True)
        except ArchiveException:
            os.remove(temp_filename)
            return None

    def __init__(self, path: str, delete_source: bool = False):
        """Init.

        path: the path of the archive.
        delete_source: whether the source archive should be
            deleted at cleanup or not.

        """
        if not Archive.is_supported(path):
            raise ArchiveException("This type of archive is not supported.")
        self.delete_source = delete_source
        self.path = path
        self.temp_dir = None

    def unpack(self) -> str:
        """Extract archive's content to a temporary directory.

        return: the path of the temporary directory.

        """
        self.temp_dir = tempfile.mkdtemp(dir=config.global_.temp_dir)
        patoolib.extract_archive(self.path, outdir=self.temp_dir,
                                 interactive=False)
        return self.temp_dir

    def repack(self, target: str):
        """Repack to a new archive all the files which were unpacked in
        self.temp_dir.

        target: the new archive path.

        """
        if self.temp_dir is None:
            raise ArchiveException("The unpack() method must be called first.")
        Archive.create_from_dir(self.temp_dir, target)

    def cleanup(self):
        """Remove temporary directory, if needed.

        """
        if self.temp_dir is not None and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
        if self.delete_source:
            try:
                os.remove(self.path)
            except OSError:
                # Cannot delete source, it is not a big problem.
                pass

    def namelist(self) -> list[str]:
        """Returns all pathnames for this archive.

        return: list of files in the archive.

        raise (NotImplementedError): when the archive was unpacked
            first.

        """
        if self.temp_dir is None:
            # Unfortunately, this "prints" names to the screen, so it's
            # not very handy.
            # patoolib.list_archive(self.path)
            raise NotImplementedError("Cannot list before unpacking.")
        else:
            names = []
            for path, _, filenames in os.walk(self.temp_dir):
                for filename in filenames:
                    filepath = os.path.join(path, filename)
                    if os.path.islink(filepath) or not os.path.isfile(filepath):
                        continue
                    names.append(os.path.relpath(filepath, self.temp_dir))
            return names

    def read(self, file_path: str) -> typing.BinaryIO:
        """Read a single file and return its file object.

        file_path: path of the file in the archive.

        return: handler for the file.

        raise (NotImplementedError): when the archive was unpacked
            first.

        """
        if self.temp_dir is None:
            # Unfortunately, patoolib does not expose an API to do this.
            raise NotImplementedError("Cannot read before unpacking.")
        else:
            return open(os.path.join(self.temp_dir, file_path), "rb")

    def write(self, file_path: str, file_object):
        """Writes a file in the archive in place.

        file_path: new path in the archive.
        file_object: file-like object.

        raise (NotImplementedError): always; this method is not yet
            implemented.

        """
        if self.temp_dir is None:
            # Unfortunately, patoolib does not expose an API to do this.
            raise NotImplementedError("Cannot write before unpacking.")
        else:
            raise NotImplementedError(
                "You should write the file directly, in the "
                "folder returned by unpack(), and then "
                "call the repack() method.")

class ArchiveBase(metaclass=ABCMeta):
    """Base class for archive reader implementations."""

    @abstractmethod
    def iter_regular_files(self) -> Iterable[tuple[str, int, object]]:
        """Yields tuples of (filepath, decompressed size, handle),
        regular files only.

        filepath will always be /-separated.
        handle can be passed to open_file.
        """
        pass

    @abstractmethod
    def open_file(self, handle: object) -> typing.IO[bytes]:
        """Open a member of the archive for reading."""
        pass

    def get_file_bytes(self, handle: object) -> bytes:
        """Read an archive member into bytes."""
        with self.open_file(handle) as f:
            return f.read()


class ArchiveZipfile(ArchiveBase):
    """Archive reader using `zipfile`, see ArchiveBase for method descriptions."""

    def __init__(self, inner: zipfile.ZipFile):
        self.inner = inner

    def iter_regular_files(self) -> list[tuple[str, int, zipfile.ZipInfo]]:
        return [
            (x.filename, x.file_size, x)
            for x in self.inner.infolist()
            if not x.is_dir()
        ]

    def open_file(self, handle: object) -> typing.IO[bytes]:
        assert isinstance(handle, zipfile.ZipInfo)
        return self.inner.open(handle, "r")


class ArchiveTarfile(ArchiveBase):
    """Archive reader using `tarfile`, see ArchiveBase for method descriptions."""

    def __init__(self, inner: tarfile.TarFile):
        self.inner = inner

    def iter_regular_files(self) -> Generator[tuple[str, int, tarfile.TarInfo]]:
        while (member := self.inner.next()) is not None:
            if member.isfile():
                yield (member.path, member.size, member)

    def open_file(self, handle: object) -> typing.IO[bytes]:
        assert isinstance(handle, tarfile.TarInfo)
        fobj = self.inner.extractfile(handle)
        if fobj is None:
            raise ValueError("not a regular file")
        return fobj


def open_archive(input: typing.IO[bytes]) -> ArchiveBase:
    """Open an archive for reading.

    input: the archive, opened for reading in binary mode.
    """
    # Order is not entirely arbitrary here: is_zipfile is a very lenient check
    # that will also return True when the file is an uncompressed tar file that
    # happens to contain a zip file inside it. So check is_tarfile first (which
    # only reads the very start of the file).
    if tarfile.is_tarfile(input):
        return ArchiveTarfile(tarfile.open(fileobj=input))
    elif zipfile.is_zipfile(input):
        return ArchiveZipfile(zipfile.ZipFile(input))
    else:
        raise ValueError("not a known archive format")
