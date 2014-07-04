#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""Utilities related to SQLAlchemy sessions.

Contains context managers and custom methods to create sessions to
interact with SQLAlchemy objects.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import psycopg2

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import make_url

from cms import config

from . import engine


Session = sessionmaker(engine, twophase=config.twophase_commit)
ScopedSession = scoped_session(Session)

# For two-phases transactions:
# Session = sessionmaker(db, twophase=True)


class SessionGen(object):
    """This allows us to create handy local sessions simply with:

    with SessionGen() as session:
        session.do_something()

    and at the end the session is automatically rolled back and
    closed. If one wants to commit the session, they have to call
    commit() explicitly.

    """
    def __init__(self):
        self.session = None

    def __enter__(self):
        self.session = Session()
        return self.session

    def __exit__(self, unused1, unused2, unused3):
        self.session.rollback()
        self.session.close()


def custom_psycopg2_connection(**kwargs):
    """Establish a new psycopg2.connection to the database.

    The returned connection won't be in the SQLAlchemy pool and has to
    be closed manually by the caller when it's done with it.

    All psycopg2-specific code in CMS is supposed to obtain a function
    this way.

    kwargs (dict): additional values to use as query parameters in the
        connection URL.

    return (connection): a new, shiny connection object.

    raise (AssertionError): if CMS (actually SQLAlchemy) isn't
        configured to use psycopg2 as the DB-API driver.

    """
    database_url = make_url(config.database)
    assert database_url.get_dialect().driver == "psycopg2"
    database_url.query.update(kwargs)

    return psycopg2.connect(
        host=database_url.host,
        port=database_url.port,
        user=database_url.username,
        password=database_url.password,
        database=database_url.database,
        **database_url.query)
