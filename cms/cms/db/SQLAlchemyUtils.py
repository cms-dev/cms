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

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from cms import Config

db = create_engine(Config.database, echo=Config.database_debug)

Base = declarative_base(db)
metadata = Base.metadata

Session = sessionmaker(db)

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

    commit (bool): whether to commit or to rollback the session
                   by default, when no other instruction has
                   been specified. To do the commit or the rollback
                   idependently of this setting, just call the
                   relevant function from the session.
                   ATTENTION: by default, the session is
                   committed, but this behaviour may change
                   in the future.

    """
    def __init__(self, commit=True):
        self.commit = commit

    def __enter__(self):
        self.session = Session()
        return self.session

    def __exit__(self, a, b, c):
        if self.commit:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()


def get_from_id(cls, id, session):
    """Given a session and an id, this class method returns the object
    corresponding to the class and id, if existing.

    cls (class): the class to which the method is attached
    id (string): the id of the object we want
    session (SQLAlchemy session): the session to query
    returns (object): the wanted object, or None

    """
    try:
        return session.query(cls).filter(cls.id == id).one()
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return None
Base.get_from_id = classmethod(get_from_id)
