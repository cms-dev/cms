#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/.
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

"""This is an example of a FileLengther, that is a file-like object
that receives a file (via write) and uses tell() to give the 'size' of
the file as an input file. In this example, we return the first
integer in the file as the measure for the complexity of the input.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


class FileLengther(object):
    """A simple file-like object to extract the first number of the
    file.

    """
    def __init__(self):
        """Initialize the file object."""
        self.string = ""
        self.state = 0

    def open(self, unused_name, unused_mode):
        """Initialize the file object."""
        self.string = ""
        self.state = 0

    def write(self, string):
        """Add string to the content of the file."""
        if self.state == 0:
            self.string += string
            if " " in self.string or "\n" in self.string:
                self.state = 1

    def tell(self):
        """Return the current position in the file."""
        return int(self.string.split()[0])

    def close(self):
        """Close the file object."""
        self.string = ""
        self.state = 0
