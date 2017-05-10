#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Luca Versari <veluca93@gmail.com>
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

"""Shell programming language definition."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cms.grading import Language


__all__ = ["SH"]


class SH(Language):
    """This defines the SH programming language, interpreted with the
    standard /bin/sh interpreter available in the system.

    """

    @property
    def name(self):
        """See Language.name."""
        return "SH"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".sh"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        return [["/bin/cp", source_filenames[0], executable_filename]]

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        args = args if args is not None else []
        return [["/bin/sh", executable_filename] + args]
