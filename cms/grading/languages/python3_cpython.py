#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Python programming language, version 3, definition."""

import os

from cms.grading import CompiledLanguage


__all__ = ["Python3CPython"]


class Python3CPython(CompiledLanguage):
    """This defines the Python programming language, version 3 (more
    precisely, the subversion of Python 3 available on the system)
    using the default interpeter in the system.

    """

    MAIN_FILENAME = "__main__.pyc"

    @property
    def name(self):
        """See Language.name."""
        return "Python 3 / CPython"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".py"]

    @property
    def executable_extension(self):
        """See Language.executable.extension."""
        # Defined in PEP 441 (https://www.python.org/dev/peps/pep-0441/).
        return ".pyz"

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""

        commands = []
        files_to_package = []
        commands.append(["/usr/bin/python3", "-m", "compileall", "-b", "."])
        for idx, source_filename in enumerate(source_filenames):
            basename = os.path.splitext(os.path.basename(source_filename))[0]
            pyc_filename = "%s.pyc" % basename
            # The file with the entry point must be in first position.
            if idx == 0:
                commands.append(["/bin/mv", pyc_filename, self.MAIN_FILENAME])
                files_to_package.append(self.MAIN_FILENAME)
            else:
                files_to_package.append(pyc_filename)

        commands.append(["/usr/bin/zip", executable_filename]
                        + files_to_package)

        return commands

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        args = args if args is not None else []
        return [["/usr/bin/python3", executable_filename] + args]
