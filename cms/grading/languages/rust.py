#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Dario Ostuni <dario.ostuni@gmail.com>
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

"""Rust programming language definition."""

from cms.grading import CompiledLanguage


__all__ = ["Rust"]


class Rust(CompiledLanguage):
    """This defines the Rust programming language, compiled with the
    standard Rust compiler available in the system.

    """

    @property
    def name(self):
        """See Language.name."""
        return "Rust"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".rs"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        # In Rust only the source file containing the main function has
        # to be passed to the compiler
        return [["/usr/bin/rustc", "-O", "-o",
                 executable_filename, source_filenames[0]]]
