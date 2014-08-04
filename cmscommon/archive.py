#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import patoolib


class Archive(object):
    """This service is an abstraction layer for transparently reading
    from and writing to archives.
    """

    @staticmethod
    def is_supported(path):
        try:
            patoolib.test_archive(path)
            return True
        except:
            return False

    @staticmethod
    def create_from_dir(from_dir, archive_path):
        """Create a new archive containing all files in from_dir.
        """
        files = tuple(os.listdir(from_dir))
        cwd = os.getcwd()
        os.chdir(from_dir)
        patoolib.create_archive(archive_path, files)
        os.chdir(cwd)

    @staticmethod
    def extract_to_dir(archive_path, to_dir):
        """Extract the content of an archive in to_dir.
        """
        patoolib.extract_archive(archive_path, outdir=to_dir)

    def __init__(self, path):
        if not Archive.is_supported(path):
            raise Exception("This type of archive is not supported.")
        self.path = path
        self.temp_dir = None

    def unpack(self):
        """Extract archive's content to a temporary directory.
        """
        self.temp_dir = tempfile.mkdtemp()
        patoolib.extract_archive(self.path, outdir=self.temp_dir)
        return self.temp_dir

    def repack(self, target):
        """Repack to a new archive all the files which were unpacked in
        self.temp_dir.
        """
        if self.temp_dir is None:
            raise Exception("The unpack() method must be called first.")
        Archive.create_from_dir(self.temp_dir, target)

    def cleanup(self):
        """Remove temporary directory, if needed.
        """
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        self.temp_dir = None

    def namelist(self):
        """Returns all pathnames for this archive.
        """
        if self.temp_dir is None:
            # Unfortunately, this "prints" names to the screen, so it's
            # not very handy.
            # patoolib.list_archive(self.path)
            raise Exception("Not implemented yet: you must first call "
                            "the unpack() method.")
        else:
            for name in os.walk(self.temp_dir):
                yield name

    def read(self, file_path):
        """Read a single file and return its file object.
        """
        if self.temp_dir is None:
            # Unfortunately, patoolib does not expose an API to do this.
            raise Exception("Not implemented yet: you must first call "
                            "the unpack() method.")
        else:
            return file(os.path.join(self.temp_dir, file_path), "r")

    def write(self, file_path, file_object):
        """Writes a file in the archive in place.
        """
        if self.temp_dir is None:
            # Unfortunately, patoolib does not expose an API to do this.
            raise Exception("Not implemented yet.")
        else:
            raise Exception("You should write the file directly, in the"
                            " folder returned by unpack(), and then "
                            "call the repack() method.")
