#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Ron Ryvchin <ryvchin@gmail.com>
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

"""High level functions to perform standardized real-number comparison.

Policy:
- Tokenization: only fixed-format decimals (no exponent, no inf/nan).
  Accepted examples: "12", "12.", "12.34", ".5", "-0.0", "+3.000"
  Rejected examples: "1e-3", "nan", "inf", "0x1.8p3"
- Tolerance: 1e-6 absolute OR 1e-6 * max(1, |a|, |b|) relative.
- Pairwise comparison in order in case the number of fixed-format decimals
  is the same, otherwise the files are considered different.
"""

import logging
import re
import typing

from cms.grading.Sandbox import Sandbox

from .evaluation import EVALUATION_MESSAGES


logger = logging.getLogger(__name__)


# Fixed-format decimals only (bytes regex).
_FIXED_DEC_RE = re.compile(rb'[+-]?(?:\d+(?:\.\d*)?|\.\d+)')
_EPS = 1e-6


def _compare_real_pair(a: float, b: float) -> bool:
    """Return True if a and b match within absolute/relative tolerance."""
    diff = abs(a - b)
    tol = _EPS * max(1.0, abs(a), abs(b))
    return diff <= tol


def _parse_fixed(token: bytes) -> float | None:
    """Parse a fixed-format decimal token into float; return None on failure."""
    # The regex already excludes exponents/inf/nan; this is defensive.
    try:
        # Decode strictly ASCII; reject weird Unicode digits.
        s = token.decode("ascii", errors="strict")
        # float() accepts exponent, but regex guarantees none are present.
        return float(s)
    except Exception:
        return None


def _extract_fixed_decimals(stream: typing.BinaryIO) -> list[float]:
    """Extract and parse all fixed-format decimal tokens from a binary stream."""
    data = stream.read()
    nums: list[float] = []
    for m in _FIXED_DEC_RE.findall(data):
        v = _parse_fixed(m)
        if v is not None:
            nums.append(v)
    return nums


def _real_numbers_compare(
    output: typing.BinaryIO, correct: typing.BinaryIO
) -> bool:
    """Compare the two output files. Two files are equal if they have the
    same number of real numbers, and all for every integer i, the absolute
    or relative difference of real number i of first file and real number i 
    of second file is smaller or equal to 10^-6.

    output: the first file to compare.
    res: the second file to compare.
    return: True if the two file are (up to the 10^-6 accuracy) as explained above.

    """
    exp_nums = _extract_fixed_decimals(correct)
    act_nums = _extract_fixed_decimals(output)

    if len(exp_nums) != len(act_nums):
        return False
    
    n = len(exp_nums)

    # Pairwise comparisons
    for i in range(n):
        a, b = exp_nums[i], act_nums[i]
        if not _compare_real_pair(a, b):
            return False
    
    return True


def realprecision_diff_fobj_step(
    output_fobj: typing.BinaryIO, correct_output_fobj: typing.BinaryIO
) -> tuple[float, list[str]]:
    """Compare user output and correct output by extracting the fixed
    floating point format number, and comparing their values.

    It gives an outcome 1.0 if the output and the reference output have
    an absoulte or a relative smaller or equal to 10^-6 and 0.0 if they don't.
    Calling this function means that the output file exists.

    output_fobj: file for the user output, opened in binary mode.
    correct_output_fobj: file for the correct output, opened in
        binary mode.

    return: the outcome as above and a description text.

    """
    if _real_numbers_compare(output_fobj, correct_output_fobj):
        return 1.0, [EVALUATION_MESSAGES.get("success").message]
    else:
        return 0.0, [EVALUATION_MESSAGES.get("wrong").message]


def realprecision_diff_step(
    sandbox: Sandbox, output_filename: str, correct_output_filename: str
) -> tuple[float, list[str]]:
    """Compare user output and correct output by extracting the fixed
    floating point format number, and comparing their values.

    It gives an outcome 1.0 if the output and the reference output have
    an absoulte or a relative smaller or equal to 10^-6 and 0.0 if they don't 
    (or if the output doesn't exist).

    sandbox: the sandbox we consider.
    output_filename: the filename of user's output in the sandbox.
    correct_output_filename: the same with reference output.

    return: the outcome as above and a description text.

    """
    if sandbox.file_exists(output_filename):
        with sandbox.get_file(output_filename) as out_file, \
             sandbox.get_file(correct_output_filename) as res_file:
            return real_precision_fobj_step(out_file, res_file)
    else:
        return 0.0, [
            EVALUATION_MESSAGES.get("nooutput").message, output_filename]
