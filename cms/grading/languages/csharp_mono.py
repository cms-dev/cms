#!/usr/bin/env python3

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

"""C# programming language definition, using the mono compiler "mcs"
and runtime "mono" installed in the system.

"""

from cms.grading import Language


__all__ = ["CSharpMono"]


class CSharpMono(Language):
    """This defines the C# programming language, compiled with the mono
    compiler "mcs" and executed with the runtime "mono".

    """

    @property
    def name(self):
        """See Language.name."""
        return "C# / Mono"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".cs"]

    @property
    def executable_extension(self):
        """See Language.executable_extension."""
        return ".exe"

    @property
    def requires_multithreading(self):
        """See Language.requires_multithreading."""
        return True

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        compile_command = ["/usr/bin/mcs",
                           "-out:" + executable_filename,
                           "-optimize+"]
        compile_command += source_filenames
        return [compile_command]

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        return [["/usr/bin/mono", executable_filename]]
