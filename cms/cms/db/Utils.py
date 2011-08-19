#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import sys

from cms.db.SQLAlchemyAll import Session, metadata, Contest, SessionGen

def analyze_table(tablename, session=None):
    """Analyze the specified table (issuing the corresponding ANALYZE
    command to the SQL backend).

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation.

    """
    if session == None:
        with SessionGen() as session:
            return analyze_table(tablename, session)

    session.execute("ANALYZE %s;" % (tablename))

def analyze_all_tables(session=None):
    """Analyze all tables tracked by SQLAlchemy.

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation.

    """
    if session == None:
        with SessionGen() as session:
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
    if session == None:
        with SessionGen() as session:
            return get_contest_list(session)

    return session.query(Contest).all()

def ask_for_contest(skip=0):
    if isinstance(skip, int) and len(sys.argv) > skip + 1:
        contest_id = sys.argv[skip + 1]

    elif isinstance(skip, str):
        contest_id = skip

    else:

        with SessionGen() as session:
            contests = get_contest_list(session)
            # The ids of the contests are cached, so the session can
            # be closed as soon as possible
            matches = {}
            print "Contests available:"
            for i, row in enumerate(contests):
                print "%3d  -  ID: %s  -  Name: %s  -  Description: %s" % (i + 1, row.id, row.name, row.description),
                matches[i+1] = row.id
                if i == 0:
                    print " (default)"
                else:
                    print

        contest_number = raw_input("Insert the number next to the contest you want to load: ")
        if contest_number == "":
            contest_number = 1
        try:
            contest_id = matches[int(contest_number)]
        except (ValueError, KeyError):
            print "Insert a correct number."
            sys.exit(1)

    return contest_id
