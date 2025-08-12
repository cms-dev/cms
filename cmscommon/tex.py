#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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


REPLACEMENTS = {"&": r"\&{}",
                "%": r"\%{}",
                "$": r"\${}",
                "#": r"\#{}",
                "_": r"\_{}",
                "{": r"\{{}",
                "}": r"\}{}",
                "~": r"\textasciitilde{}",
                "^": r"\textasciicircum{}",
                "\\": r"\textbackslash{}"}


def escape_tex_normal(string: str) -> str:
    """Escape a string for use inside latex.

    string: string to escape
    return: escaped string

    """
    def repc(c):
        if c in REPLACEMENTS:
            return REPLACEMENTS[c]
        else:
            return c
    return "".join(repc(c) for c in string)


def escape_tex_tt(string: str) -> str:
    """Escape a string for use inside latex with \texttt.

    string: string to escape
    return: escaped string

    """
    def repc(c):
        if c in REPLACEMENTS:
            return "\\char\"%02X{}" % ord(c)
        else:
            return c
    return "".join(repc(c) for c in string)
