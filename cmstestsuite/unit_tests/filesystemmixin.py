#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""A unittest.TestCase mixin for tests interacting with the filesystem.

"""

import os
import shutil
import tempfile


class FileSystemMixin:
    """Mixin for tests with filesystem access."""

    def setUp(self):
        super().setUp()
        self.base_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base_dir)
        super().tearDown()

    def get_path(self, inner_path):
        "Return the full path for a given inner path within the temp dir."
        return os.path.join(self.base_dir, inner_path)

    def makedirs(self, inner_path):
        """Create (possibly many) directories up to inner_path.

        inner_path (str): path to create.

        return (str): full path of the possibly new directory.

        """
        path = self.get_path(inner_path)
        try:
            os.makedirs(path)
        except FileExistsError:
            pass
        return path

    def write_file(self, inner_path, content):
        """Write content and return the full path.

        inner_path (str): path inside the temp dir to write to.
        content (bytes): content to write.

        return (str): full path of the file written.

        """
        path = self.get_path(inner_path)
        with open(path, "wb") as f:
            f.write(content)
        return path
