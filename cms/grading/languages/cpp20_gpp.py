#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2024 Filippo Casarin <casarin.filippo17@gmail.com>
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

"""C++20 programming language definition."""

from cms.grading import CompiledLanguage


__all__ = ["Cpp20Gpp"]


class Cpp20Gpp(CompiledLanguage):
    """This defines the C++ programming language, compiled with g++ (the
    version available on the system) using the C++20 standard.

    """

    @property
    def name(self):
        """See Language.name."""
        return "C++20 / g++"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".cpp", ".cc", ".cxx", ".c++", ".C"]

    @property
    def header_extensions(self):
        """See Language.header_extensions."""
        return [".h"]

    @property
    def object_extensions(self):
        """See Language.object_extensions."""
        return [".o"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        command = ["/usr/bin/g++"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-std=gnu++20", "-O2", "-pipe", "-static",
                    "-s", "-o", executable_filename]
        command += source_filenames
        return [command]
