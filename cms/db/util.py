#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Utilities relying on the database.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import sys

from . import SessionGen, Contest


def get_contest_list(session=None):
    """Return all the contest objects available on the database.

    session (Session|None): if specified, use such session for
        connecting to the database; otherwise, create a temporary one
        and discard it after the operation (this means that no further
        expansion of lazy properties of the returned Contest objects
        will be possible).

    return ([Contest]): the list of contests in the DB.

    """
    if session is None:
        with SessionGen() as session:
            return get_contest_list(session)

    return session.query(Contest).all()


def is_contest_id(contest_id):
    """Return if there is a contest with the given id in the database.

    contest_id (int): the id to query.
    return (boolean): True if there is such a contest.

    """
    with SessionGen() as session:
        return Contest.get_from_id(contest_id, session) is not None


def ask_for_contest(skip=None):
    """Print a greeter that ask the user for a contest, if there is
    not an indication of which contest to use in the command line.

    skip (int|None): how many commandline arguments are already taken
        by other usages (None for no arguments already consumed).

    return (int): a contest_id.

    """
    if isinstance(skip, int) and len(sys.argv) > skip + 1:
        contest_id = int(sys.argv[skip + 1])

    else:

        with SessionGen() as session:
            contests = get_contest_list(session)
            # The ids of the contests are cached, so the session can
            # be closed as soon as possible
            matches = {}
            n_contests = len(contests)
            if n_contests == 0:
                print("No contests in the database.")
                print("You may want to use some of the facilities in "
                      "cmscontrib to import a contest.")
                sys.exit(0)
            print("Contests available:")
            for i, row in enumerate(contests):
                print("%3d  -  ID: %d  -  Name: %s  -  Description: %s" %
                      (i + 1, row.id, row.name, row.description), end='')
                matches[i + 1] = row.id
                if i == n_contests - 1:
                    print(" (default)")
                else:
                    print()

        contest_number = raw_input("Insert the row number next to the contest "
                                   "you want to load (not the id): ")
        if contest_number == "":
            contest_number = n_contests
        try:
            contest_id = matches[int(contest_number)]
        except (ValueError, KeyError):
            print("Insert a correct number.")
            sys.exit(1)

    return contest_id
