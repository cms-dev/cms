#!/usr/bin/env python2
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

"""This script creates a new user in the database.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import logging
import sys

from cms import utf8_decoder
from cms.db import SessionGen, User
from cmscommon.crypto import generate_random_password

from sqlalchemy.exc import IntegrityError


logger = logging.getLogger(__name__)


def add_user(first_name, last_name, username, password, email, timezone,
             preferred_languages):
    logger.info("Creating the user in the database.")
    if password is None:
        password = generate_random_password()
    if preferred_languages is None or preferred_languages == "":
        preferred_languages = "[]"
    else:
        preferred_languages = \
            "[" + ",".join("\"" + lang + "\""
                           for lang in preferred_languages.split(",")) + "]"
    user = User(first_name=first_name,
                last_name=last_name,
                username=username,
                password=password,
                email=email,
                timezone=timezone,
                preferred_languages=preferred_languages)
    try:
        with SessionGen() as session:
            session.add(user)
            session.commit()
    except IntegrityError:
        logger.error("A user with the given username already exists.")
        return False

    logger.info("User added. "
                "Use AddParticipation to add this user to a contest.")
    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add a user to CMS.")
    parser.add_argument("first_name", action="store", type=utf8_decoder,
                        help="given name of the user")
    parser.add_argument("last_name", action="store", type=utf8_decoder,
                        help="family name of the user")
    parser.add_argument("username", action="store", type=utf8_decoder,
                        help="username used to log in")
    parser.add_argument("-p", "--password", action="store", type=utf8_decoder,
                        help="password, leave empty to auto-generate")
    parser.add_argument("-e", "--email", action="store", type=utf8_decoder,
                        help="email of the user")
    parser.add_argument("-t", "--timezone", action="store", type=utf8_decoder,
                        help="timezone of the user, e.g. Europe/London")
    parser.add_argument("-l", "--languages", action="store", type=utf8_decoder,
                        help="comma-separated list of preferred languages")

    args = parser.parse_args()

    success = add_user(args.first_name, args.last_name,
                       args.username, args.password, args.email,
                       args.timezone, args.languages)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
