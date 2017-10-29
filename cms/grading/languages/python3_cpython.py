#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os

from cms.grading import CompiledLanguage


__all__ = ["Python3CPython"]


class Python3CPython(CompiledLanguage):
    """This defines the Python programming language, version 3 (more
    precisely, the subversion of Python 3 available on the system)
    using the default interpeter in the system.

    """

    @property
    def name(self):
        """See Language.name."""
        return "Python 3 / CPython"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".py"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        basename = os.path.splitext(os.path.basename(source_filenames[0]))[0]
        compilation_program = ";".join([
            "import py_compile as m",
            "m.compile(%s, %s, doraise=True)" % (
                repr(basename + ".py"), repr(basename))])
        py_command = ["/usr/bin/python3", "-c", compilation_program]
        return [py_command]

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        args = args if args is not None else []
        return [["/usr/bin/python3", executable_filename] + args]
