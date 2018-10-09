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

"""Utilities to handle messages for contestants about execution outcomes."""

import logging


logger = logging.getLogger(__name__)


class HumanMessage:
    """Represent a possible outcome message for a grading, to be presented
    to the contestants.

    """

    def __init__(self, shorthand, message, help_text):
        """Initialization.

        shorthand (str): what to call this message in the code.
        message (str): the message itself.
        help_text (str): a longer explanation for the help page.

        """
        self.shorthand = shorthand
        self.message = message
        self.help_text = help_text


class MessageCollection:
    """Represent a collection of messages, with error checking."""

    def __init__(self, messages=None):
        self._messages = {}
        self._ordering = []
        if messages is not None:
            for message in messages:
                self.add(message)

    def add(self, message):
        if message.shorthand in self._messages:
            logger.error("Trying to registering duplicate message `%s'.",
                         message.shorthand)
            return
        self._messages[message.shorthand] = message
        self._ordering.append(message.shorthand)

    def get(self, shorthand):
        if shorthand not in self._messages:
            error = "Trying to get a non-existing message `%s'." % \
                shorthand
            logger.error(error)
            raise KeyError(error)
        return self._messages[shorthand]

    def all(self):
        ret = []
        for shorthand in self._ordering:
            ret.append(self._messages[shorthand])
        return ret
