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

    def __init__(self, shorthand: str, message: str, help_text: str, inline_help: bool = False):
        """Initialization.

        shorthand: what to call this message in the code.
        message: the message itself.
        help_text: a longer explanation for the help page.
        inline_help: Whether to show a help tooltip for this message whenever it is shown.

        """
        self.shorthand = shorthand
        self.message = message
        self.help_text = help_text
        self.inline_help = inline_help


class MessageCollection:
    """Represent a collection of messages, with error checking."""

    def __init__(self, namespace: str, messages: list[HumanMessage] | None = None):
        self._messages: dict[str, HumanMessage] = {}
        self._ordering: list[str] = []
        if messages is not None:
            for message in messages:
                self.add(message)
        MESSAGE_REGISTRY.add(namespace, self)

    def add(self, message: HumanMessage):
        if message.shorthand in self._messages:
            logger.error("Trying to registering duplicate message `%s'.",
                         message.shorthand)
            return
        self._messages[message.shorthand] = message
        self._ordering.append(message.shorthand)

    def get(self, shorthand: str) -> HumanMessage:
        if shorthand not in self._messages:
            error = "Trying to get a non-existing message `%s'." % \
                shorthand
            logger.error(error)
            raise KeyError(error)
        return self._messages[shorthand]

    def all(self) -> list[HumanMessage]:
        ret = []
        for shorthand in self._ordering:
            ret.append(self._messages[shorthand])
        return ret

class MessageRegistry:
    """Represents a collection of message collections, organized by a namespace
    prefix. This is a singleton that is automatically populated by
    MessageCollection."""

    def __init__(self):
        self._namespaces: dict[str, MessageCollection] = {}

    def add(self, namespace: str, collection: MessageCollection):
        if namespace in self._namespaces:
            logger.error(f"Trying to register duplicate namespace {namespace}")
            return
        self._namespaces[namespace] = collection

    def get(self, message_id: str) -> HumanMessage:
        if ':' not in message_id:
            raise KeyError(f"Invalid message ID {message_id}")
        namespace, message = message_id.split(':', 1)
        if namespace not in self._namespaces:
            raise KeyError(f"Message namespace {namespace} not found")
        collection = self._namespaces[namespace]
        return collection.get(message)

MESSAGE_REGISTRY = MessageRegistry()
