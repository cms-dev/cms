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

import cms.util.Configuration as Configuration

db = create_engine(Configuration.sqlalchemy_database, echo=True)

Base = declarative_base(db)
metadata = Base.metadata

Session = sessionmaker(db)

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

class SessionGen:
    """This allows us to create handy local sessions simply with:

    with SessionGen as session:
        session.do_something()

    and at the end, commit & close are automatically called.

    """
    def __enter__(self):
        self.session = Session()
        return self.session
    def __exit__(self, a, b, c):
        self.session.commit()
        self.session.close()

def get_from_id(cls, id, session):
    try:
        return session.query(cls).filter(cls.id == id).one()
    except NoResultFound:
        return None
    except MultipleResultsFound:
        return None
Base.get_from_id = classmethod(get_from_id)
