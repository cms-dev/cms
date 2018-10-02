#!/usr/bin/env python3

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

"""Haskell programming language definition."""

import os

from cms.grading import CompiledLanguage


__all__ = ["HaskellGhc"]


class HaskellGhc(CompiledLanguage):
    """This defines the Haskell programming language, compiled with ghc
    (the version available on the system).

    """

    @property
    def name(self):
        """See Language.name."""
        return "Haskell / ghc"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".hs"]

    @property
    def object_extensions(self):
        """See Language.source_extensions."""
        return [".o"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        commands = []
        # Haskell module names are capitalized, so we change the source file
        # names (except for the first one) to match the module's name.
        # The first source file is, instead, the grader or the standalone
        # source file; it won't be imported in any other source file, so
        # there is no need to capitalize it.
        for source in source_filenames[1:]:
            commands.append(["/bin/ln", "-s", os.path.basename(source),
                             HaskellGhc._capitalize(source)])
        commands.append(["/usr/bin/ghc", "-static", "-O2", "-Wall", "-o",
                         executable_filename, source_filenames[0]])
        return commands

    @staticmethod
    def _capitalize(string):
        dirname, basename = os.path.split(string)
        return os.path.join(dirname, basename[0].upper() + basename[1:])
