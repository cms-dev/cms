#!/usr/bin/env python
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

"""Java programming language definition, compiled."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import os

from cms.grading import CompiledLanguage


__all__ = ["Java14Gcj"]


class Java14Gcj(CompiledLanguage):
    """This defines the Java programming language, compiled with gcj (the
    current version available on the system) using the most recent
    version supported (1.4 with some features of 1.5).

    """

    @property
    def name(self):
        """See Language.name."""
        return "Java 1.4 / gcj"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".java"]

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        class_name = os.path.splitext(source_filenames[0])[0]
        command = [
            "/usr/bin/gcj", "--main=%s" % class_name, "-O3",
            "-o", executable_filename
        ]
        command += source_filenames
        return [command]
