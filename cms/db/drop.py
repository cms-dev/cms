#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Drop all content and tables in the database.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

from psycopg2 import ProgrammingError
from sqlalchemy.engine.url import make_url

from cms import config

from . import custom_psycopg2_connection


logger = logging.getLogger(__name__)


def drop_db():
    """Drop everything in the database. In theory metadata.drop_all()
    should do the same; in practice, it isn't able to handle cases
    when the data present in the database doesn't fit the schema known
    by metadata.

    This method is psycopg2 and PostgreSQL-specific. Technically, what
    it does is to drop the schema "public", create it again and fix
    corresponding privileges. This doesn't work if for some reason the
    database was set up to use a different schema: this situation is
    strange enough for us to just ignore it.

    return (bool): True if successful.

    """
    connection = custom_psycopg2_connection()
    connection.autocommit = True
    cursor = connection.cursor()

    # See
    # http://stackoverflow.com/questions/3327312/drop-all-tables-in-postgresql
    try:
        cursor.execute("DROP SCHEMA public CASCADE")
    except ProgrammingError:
        logger.error("Couldn't drop schema \"public\", probably you don't "
                     "have the privileges. Please execute as database "
                     "superuser: \"ALTER SCHEMA public OWNER TO %s;\" and "
                     "run again", make_url(config.database).username)
        return False
    cursor.execute("CREATE SCHEMA public")

    # But we also have to drop the large objects
    try:
        cursor.execute("SELECT oid FROM pg_largeobject_metadata")
    except ProgrammingError:
        logger.error("Couldn't list large objects, probably you don't have "
                     "the privileges. Please execute as database superuser: "
                     "\"GRANT SELECT ON pg_largeobject TO %s;\" and run "
                     "again", make_url(config.database).username)
        return False
    rows = cursor.fetchall()
    for row in rows:
        cursor.execute("SELECT lo_unlink(%d)" % row[0])

    cursor.close()

    return True
