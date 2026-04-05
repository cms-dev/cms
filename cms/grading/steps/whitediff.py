#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""High level functions to perform standardized white-diff comparison."""

import logging
import typing

from cms.grading.Sandbox import Sandbox

from .evaluation import EVALUATION_MESSAGES


logger = logging.getLogger(__name__)


# We take as definition of whitespaces the list of Unicode White_Space
# characters (see http://www.unicode.org/Public/6.3.0/ucd/PropList.txt) that
# are in the ASCII range.
_WHITES = [b' ', b'\t', b'\n', b'\x0b', b'\x0c', b'\r']


def _white_diff_canonicalize(string: bytes) -> bytes:
    """Convert the input string to a canonical form for the white diff
    algorithm; that is, the strings a and b are mapped to the same
    string by _white_diff_canonicalize() if and only if they have to be
    considered equivalent for the purposes of the white-diff
    algorithm.

    More specifically, this function strips all the leading and
    trailing whitespaces from s and collapse all the runs of
    consecutive whitespaces into just one copy of one specific
    whitespace.

    string: the string to canonicalize.
    return: the canonicalized string.

    """
    # Replace all the whitespaces with copies of " ", making the rest
    # of the algorithm simpler
    for char in _WHITES[1:]:
        string = string.replace(char, _WHITES[0])

    # Split the string according to " ", filter out empty tokens and
    # join again the string using just one copy of the first
    # whitespace; this way, runs of more than one whitespaces are
    # collapsed into just one copy.
    string = _WHITES[0].join([x for x in string.split(_WHITES[0])
                              if len(x) > 0])
    return string


def _white_diff(output: typing.BinaryIO, res: typing.BinaryIO) -> tuple[bool, str | None]:
    """Compare the two output files. Two files are equal if for every
    integer i, line i of first file is equal to line i of second
    file. Two lines are equal if they differ only by number or type of
    whitespaces.

    Note that trailing lines composed only of whitespaces don't change
    the 'equality' of the two files. Note also that by line we mean
    'sequence of characters ending with \n or EOF and beginning right
    after BOF or \n'. In particular, every line has *at most* one \n.

    output: the first file to compare.
    res: the second file to compare.
    return: True if the two file are equal as explained above.

    """

    line = 0

    while True:
        lout = output.readline()
        lres = res.readline()
        line += 1

        # Both files finished: comparison succeded
        if len(lres) == 0 and len(lout) == 0:
            return True, None

        # Only one file finished: ok if the other contains only blanks
        elif len(lres) == 0 or len(lout) == 0:
            lout = lout.strip(b''.join(_WHITES))
            lres = lres.strip(b''.join(_WHITES))
            if len(lout) > 0:
                return False, "Contestant output too long"
            if len(lres) > 0:
                return False, "Contestant output too short"

        # Both file still have lines to go: ok if they agree except
        # for the number of whitespaces
        else:
            lout = _white_diff_canonicalize(lout)
            lres = _white_diff_canonicalize(lres)
            if lout != lres:
                LENGTH_LIMIT = 100
                if len(lout) > LENGTH_LIMIT:
                    lout = lout[:LENGTH_LIMIT] + b"..."
                if len(lres) > LENGTH_LIMIT:
                    lres = lres[:LENGTH_LIMIT] + b"..."
                lout = lout.decode("utf-8", errors='backslashreplace')
                lres = lres.decode("utf-8", errors='backslashreplace')
                return False, f"Expected `{lres}`, found `{lout}` on line {line}"


def white_diff_fobj_step(
    output_fobj: typing.BinaryIO, correct_output_fobj: typing.BinaryIO
) -> tuple[float, list[str], str | None]:
    """Compare user output and correct output with a simple diff.

    It gives an outcome 1.0 if the output and the reference output are
    identical (or differ just by white spaces) and 0.0 if they don't. Calling
    this function means that the output file exists.

    output_fobj: file for the user output, opened in binary mode.
    correct_output_fobj: file for the correct output, opened in
        binary mode.

    return: the outcome as above and a description text.

    """
    correct, admin_text = _white_diff(output_fobj, correct_output_fobj)
    if correct:
        return 1.0, [EVALUATION_MESSAGES.get("success").message], admin_text
    else:
        return 0.0, [EVALUATION_MESSAGES.get("wrong").message], admin_text


def white_diff_step(
    sandbox: Sandbox, output_filename: str, correct_output_filename: str
) -> tuple[float, list[str], str | None]:
    """Compare user output and correct output with a simple diff.

    It gives an outcome 1.0 if the output and the reference output are
    identical (or differ just by white spaces) and 0.0 if they don't (or if
    the output doesn't exist).

    sandbox: the sandbox we consider.
    output_filename: the filename of user's output in the sandbox.
    correct_output_filename: the same with reference output.

    return: the outcome as above and a description text.

    """
    if sandbox.file_exists(output_filename):
        with sandbox.get_file(output_filename) as out_file, \
                sandbox.get_file(correct_output_filename) as res_file:
            return white_diff_fobj_step(out_file, res_file)
    else:
        return 0.0, [
            EVALUATION_MESSAGES.get("nooutput").message, output_filename], None
