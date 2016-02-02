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

"""Interfaces for supported programming languages."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os


logger = logging.getLogger(__name__)


class Language(object):
    """A supported programming language"""

    @property
    def name(self):
        """Returns the name of the language.

        Should be uniquely describing the language and the
        version/compiler used, for example "C++11 / g++" better than "C++",
        or "Java 1.5 / JDK", "Java 1.4 / gcj" better than "Java".

        return (str): the name

        """
        raise NotImplementedError("Please subclass this class.")

    @property
    def source_extensions(self):
        """Extensions used for sources for this language (including the dot).

        The first one is the canonical one, used by CMS. Any of these
        can be used by contestants.

        """
        return []

    @property
    def source_extension(self):
        """Default source extension for the language."""
        return self.source_extensions[0] \
            if len(self.source_extensions) > 0 else None

    @property
    def header_extensions(self):
        """Extensions used for headers for this language (including the dot).

        """
        return []

    @property
    def header_extension(self):
        """Default header extension for the language."""
        return self.header_extensions[0] \
            if len(self.header_extensions) > 0 else None

    @property
    def object_extensions(self):
        """Extensions used for object files for this language (including the
        dot).

        """
        return []

    @property
    def object_extension(self):
        """Default object extension for the language."""
        return self.object_extensions[0] \
            if len(self.object_extensions) > 0 else None

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """Return the compilation commands.

        The compilation commands are for the specified language,
        source filenames and executable filename. Each command is a
        list of strings, suitable to be passed to the methods in
        subprocess package.

        source_filenames ([string]): a list of the string that are the
            filenames of the source files to compile; the order is
            relevant: the first file must be the one that contains the
            program entry point (with some langages, e.g. Pascal, only
            the main file must be passed to the compiler).
        executable_filename (string): the output file.
        for_evaluation (bool): if True, define EVAL during the
            compilation; defaults to True.

        return ([[string]]): a list of commands, each a list of
            strings to be passed to subprocess.

        """
        raise NotImplementedError("Please subclass this class.")

    def get_evaluation_commands(self, executable_filename):
        """Return the evaluation commands.

        executable_filename: the name of the "executable" (does not
            need to be executable per se).
        return ([[string]]): a list of commands, each a list of
            strings to be passed to subprocess.

        """
        raise NotImplementedError("Please subclass this class.")


class CompiledLanguage(Language):
    """A language where the compilation step produces an executable."""

    def get_evaluation_commands(self, executable_filename):
        """See Language.get_evaluation_commands."""
        return [[os.path.join(".", executable_filename)]]
