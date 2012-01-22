#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""Utilities functions that interacts with the database.

"""

import sys

from cms.db.SQLAlchemyAll import metadata, Contest, SessionGen


def analyze_table(tablename, session=None):
    """Analyze the specified table (issuing the corresponding ANALYZE
    command to the SQL backend).

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation.

    """
    if session is None:
        with SessionGen(commit=True) as session:
            return analyze_table(tablename, session)

    session.execute("ANALYZE %s;" % (tablename))


def analyze_all_tables(session=None):
    """Analyze all tables tracked by SQLAlchemy.

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation.

    """
    if session is None:
        with SessionGen(commit=False) as session:
            return analyze_all_tables(session)

    for table in metadata.sorted_tables:
        analyze_table(table.name, session)


def get_contest_list(session=None):
    """Return all the contest objects available on the database.

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation (this means that no
                              further expansion of lazy properties of
                              the returned Contest objects will be
                              possible).

    """
    if session is None:
        with SessionGen(commit=True) as session:
            return get_contest_list(session)

    return session.query(Contest).all()


def ask_for_contest(skip=None):
    """Print a greeter that ask the user for a contest, if there is
    not an indication of which contest to use in the command line.

    skip (int/None): how many commandline arguments are already taken
                     by other usages.

    return (int): a contest_id.

    """
    # It seems nice to create the tables first if they do not exists.
    metadata.create_all()

    if isinstance(skip, int) and len(sys.argv) > skip + 1:
        contest_id = int(sys.argv[skip + 1])

    else:

        with SessionGen(commit=False) as session:
            contests = get_contest_list(session)
            # The ids of the contests are cached, so the session can
            # be closed as soon as possible
            matches = {}
            n_contests = len(contests)
            if n_contests == 0:
                print "No contests in the database."
                print "You may want to use some of the facilities in " \
                      "cmscontrib to import a contest."
                sys.exit(0)
            print "Contests available:"
            for i, row in enumerate(contests):
                print "%3d  -  ID: %d  -  Name: %s  -  Description: %s" % \
                      (i + 1, row.id, row.name, row.description),
                matches[i + 1] = row.id
                if i == n_contests - 1:
                    print " (default)"
                else:
                    print

        contest_number = raw_input("Insert the number next to the contest "
                                   "you want to load: ")
        if contest_number == "":
            contest_number = n_contests - 1
        try:
            contest_id = matches[int(contest_number)]
        except (ValueError, KeyError):
            print "Insert a correct number."
            sys.exit(1)

    return contest_id


def default_argument_parser(description, cls, ask_contest=False):
    """Default argument parser for services - in two versions: needing
    a contest_id, or not.

    description (string): description of the service.
    cls (class): service's class.
    ask_contest (bool): True if the service needs a contest_id.

    return (object): an instance of a service.

    """
    from argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("shard", type=int)

    # We need to allow using the switch "-c" also for services that do
    # not need the contest_id because RS needs to be able to restart
    # everything without knowing which is which.
    contest_id_help = "id of the contest to automatically load"
    if not ask_contest:
        contest_id_help += " (ignored)"
    parser.add_argument("-c", "--contest-id", help=contest_id_help,
                        nargs="?", type=int)
    args = parser.parse_args()
    if ask_contest:
        if args.contest_id is not None:
            return cls(args.shard, args.contest_id)
        else:
            return cls(args.shard, ask_for_contest())
    else:
        return cls(args.shard)
