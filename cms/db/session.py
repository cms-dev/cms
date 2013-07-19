#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
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

from __future__ import absolute_import

import psycopg2

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import make_url

from cms import config

from . import engine


Session = sessionmaker(engine, twophase=config.twophase_commit)
ScopedSession = scoped_session(Session)

# For two-phases transactions:
#Session = sessionmaker(db, twophase=True)


# TODO: decide which one of the following is better.

# from contextlib import contextmanager

# @contextmanager
# def SessionGen():
#     """This allows us to create handy local sessions simply with:

#     with SessionGen as session:
#         session.do_something()

#     and at the end, commit & close are automatically called.

#     """
#     session = Session()
#     try:
#         yield session
#     finally:
#         session.commit()
#         session.close()

# FIXME How does one rollback a session created with SessionGen?
class SessionGen:
    """This allows us to create handy local sessions simply with:

    with SessionGen() as session:
        session.do_something()

    and at the end the session is automatically closed.

    commit (bool): whether to commit or to rollback the session by
                   default, when no other instruction has been
                   specified. To do the commit or the rollback
                   idependently of this setting, just call the
                   relevant function from the session.  ATTENTION: by
                   default, the session is not committed.

    """
    def __init__(self, commit=False):
        self.commit = commit
        self.session = None

    def __enter__(self):
        self.session = Session()
        return self.session

    def __exit__(self, unused1, unused2, unused3):
        if self.commit:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()


def get_psycopg2_connection(session):
    """Return the psycopg2 connection object associated to the given
    SQLAlchemy Session. This, of course, means that the Session must
    be using psycopg2 as backend.

    Since the connection will be returned to the SQLAlchemy pool after
    use its "behavior" cannot be changed (e.g. by setting autocommit).
    Please use custom_psycopg2_connection in those cases.

    Moreover, all psycopg2-specific code in CMS is supposed to invoke
    this method or custom_psycopg2_connection.

    session (Session): a SQLAlchemy Session.

    return (connection): the associated psycopg2 connection object.

    """
    sa_conn = session.connection()
    assert sa_conn.dialect.driver == "psycopg2"

    return sa_conn.connection


def custom_psycopg2_connection(**kwargs):
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
