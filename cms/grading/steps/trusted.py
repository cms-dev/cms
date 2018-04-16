#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""High level functions to perform standardized trusted executions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import io
import logging

from .evaluation import EVALUATION_MESSAGES


logger = logging.getLogger(__name__)


def _filter_ansi_escape(string):
    """Filter out ANSI commands from the given string.

    string (str): string to process.

    return (str): string with ANSI commands stripped.

    """
    ansi_mode = False
    res = ''
    for char in string:
        if char == u'\033':
            ansi_mode = True
        if not ansi_mode:
            res += char
        if char == u'm':
            ansi_mode = False
    return res


def extract_outcome_and_text(sandbox):
    """Extract the outcome and the text from the two outputs of a trusted
    manager (stdout contains the outcome, and stderr the text).

    stdout (Sandbox): the sandbox whose last execution was a comparator.

    return (float, [str]): outcome and text.

    raise (ValueError): if cannot decode the data.

    """
    stdout = sandbox.relative_path(sandbox.stdout_file)
    stderr = sandbox.relative_path(sandbox.stderr_file)
    with io.open(stdout, "r", encoding="utf-8") as stdout_file:
        with io.open(stderr, "r", encoding="utf-8") as stderr_file:
            try:
                outcome = stdout_file.readline().strip()
            except UnicodeDecodeError as error:
                logger.error("Unable to interpret manager stdout "
                             "(outcome) as unicode. %r", error)
                raise ValueError("Cannot decode the outcome.")
            try:
                text = _filter_ansi_escape(stderr_file.readline())
            except UnicodeDecodeError as error:
                logger.error("Unable to interpret manager stderr "
                             "(text) as unicode. %r", error)
                raise ValueError("Cannot decode the text.")

    try:
        outcome = float(outcome)
    except ValueError:
        logger.error("Wrong outcome `%s' from manager.", outcome)
        raise ValueError("Outcome is not a float.")

    # If the text starts with translate, the manager is asking us to
    # use a stock message, that can be translated.
    if text.startswith("translate:"):
        remaining = text[len("translate:"):].strip()
        if remaining in ["success", "partial", "wrong"]:
            text = EVALUATION_MESSAGES.get(remaining).message
        else:
            remaining = remaining[:15]  # to avoid logging lots of text
            logger.warning("Manager asked to translate text, but string "
                           "'%s' is not recognized." % remaining)

    return outcome, [text]
