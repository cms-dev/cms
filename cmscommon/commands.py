#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from shlex import quote


__all__ = [
    "pretty_print_cmdline",
]


def pretty_print_cmdline(cmdline):
    """Pretty print a command line.

    Take a command line suitable to be passed to a Popen-like call and
    returns a string that represents it in a way that preserves the
    structure of arguments and can be passed to bash as is.

    More precisely, delimitate every item of the command line with
    single apstrophes and join all the arguments separating them with
    spaces.

    """
    return " ".join(quote(x) for x in cmdline)
