#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""C++ programming language definition."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cms.grading import CompiledLanguage


__all__ = ["Cpp14Gpp"]


class Cpp14Gpp(CompiledLanguage):
    """This defines the C++ programming language, compiled with g++ (the
    version available on the system) using the C++11 standard.

    """

    @property
    def name(self):
        """See Language.name."""
        return "C++14 / g++"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".cpp", ".cc", ".cxx", ".c++", ".C"]

    @property
    def header_extensions(self):
        """See Language.source_extensions."""
        return [".h"]

    @property
    def object_extensions(self):
        """See Language.source_extensions."""
        return [".o"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        command = ["/usr/bin/g++"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-std=gnu++14", "-O2", "-pipe", "-static",
                    "-s", "-o", executable_filename]
        command += source_filenames
        return [command]

    def get_compilation_no_link_command(self, source_filenames):
        """See Language.get_compilation_no_link_command."""
        command = ["/usr/bin/g++"]
        command += ["-std=gnu++14", "-O2", "-pipe", "-static",
                    "-s", "-c"]
        command += source_filenames
        return [command]
