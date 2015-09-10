#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import patoolib

from patoolib.util import PatoolError

from cms import config


class ArchiveException(Exception):
    """Exception for when the interaction with the Archive class is
    incorrect.

    """
    pass


class Archive(object):
    """Class to manage archives.

    This class has static methods to test, extract, and create
    archives. Moreover, an instance of this class can be create to
    manage an existing archive. At the moment, all operations depend
    on calling first the unpack method, that extract the archive in a
    temporary directory.

    """

    @staticmethod
    def is_supported(path):
        """Return whether the file at path is supported by patoolib.

        path (string): the path to test.

        return (bool): whether path is supported.

        """
        try:
            patoolib.test_archive(path)
            return True
        except PatoolError:
            return False

    @staticmethod
    def create_from_dir(from_dir, archive_path):
        """Create a new archive containing all files in from_dir.

        from_dir (string): directory with the files to archive.
        archive_path (string): the new archive's path.

        """
        files = tuple(os.listdir(from_dir))
        cwd = os.getcwd()
        os.chdir(from_dir)
        patoolib.create_archive(archive_path, files)
        os.chdir(cwd)

    @staticmethod
    def extract_to_dir(archive_path, to_dir):
        """Extract the content of an archive in to_dir.

        archive_path (string): path of the archive to extract.
        to_dir (string): destination directory.

        """
        patoolib.extract_archive(archive_path, outdir=to_dir)

    @staticmethod
    def from_raw_data(raw_data):
        """Create an Archive object out of raw archive data.

        This method treats the given string as archive data: it dumps it
        into a temporary file, then creates an Archive object. Since the
        user did not provide a path, we assume that when cleanup() is
        called the temporary file should be deleted as well as unpacked
        data.

        raw_data (bytes): the actual bytes that form the archive.

        return (Archive|None): an object that represents the new
            archive or None, if raw_data doesn't represent an archive.

        """
        temp_file, temp_filename = tempfile.mkstemp(dir=config.temp_dir)
        with os.fdopen(temp_file, "w") as temp_file:
            temp_file.write(raw_data)

        try:
            return Archive(temp_filename, delete_source=True)
        except ArchiveException:
            os.remove(temp_filename)
            return None

    def __init__(self, path, delete_source=False):
        """Init.

        path (string): the path of the archive.
        delete_source (bool): whether the source archive should be
            deleted at cleanup or not.

        """
        if not Archive.is_supported(path):
            raise ArchiveException("This type of archive is not supported.")
        self.delete_source = delete_source
        self.path = path
        self.temp_dir = None

    def unpack(self):
        """Extract archive's content to a temporary directory.

        return (string): the path of the temporary directory.

        """
        self.temp_dir = tempfile.mkdtemp(dir=config.temp_dir)
        patoolib.extract_archive(self.path, outdir=self.temp_dir)
        return self.temp_dir

    def repack(self, target):
        """Repack to a new archive all the files which were unpacked in
        self.temp_dir.

        target (string): the new archive path.

        """
        if self.temp_dir is None:
            raise ArchiveException("The unpack() method must be called first.")
        Archive.create_from_dir(self.temp_dir, target)

    def cleanup(self):
        """Remove temporary directory, if needed.

        """
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        self.temp_dir = None
        if self.delete_source:
            try:
                os.remove(self.path)
            except OSError:
                # Cannot delete source, it is not a big problem.
                pass

    def namelist(self):
        """Returns all pathnames for this archive.

        return ([string]): list of files in the archive.

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
            cwd = os.getcwd()
            os.chdir(self.temp_dir)
            for level in os.walk("."):
                for filename in level[2]:
                    names.append(os.path.join(level[0], filename))
            os.chdir(cwd)
            return names

    def read(self, file_path):
        """Read a single file and return its file object.

        file_path (string): path of the file in the archive.

        return (file): handler for the file.

        raise (NotImplementedError): when the archive was unpacked
            first.

        """
        if self.temp_dir is None:
            # Unfortunately, patoolib does not expose an API to do this.
            raise NotImplementedError("Cannot read before unpacking.")
        else:
            return file(os.path.join(self.temp_dir, file_path), "r")

    def write(self, file_path, file_object):
        """Writes a file in the archive in place.

        file_path (string): new path in the archive.
        file_object (object): file-like object.

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
