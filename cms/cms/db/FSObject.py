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

"""SQLAlchemy interfaces to store files in the database. Not to be
used directly (import from SQLAlchemyAll).

"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm.exc import NoResultFound

from psycopg2.extensions import lobject

from cms.db.SQLAlchemyUtils import Base

from contextlib import contextmanager

class FSObject(Base):

    __tablename__ = 'fsobjects'

    digest = Column(String, primary_key=True)
    loid = Column(Integer, nullable=False)
    description = Column(String, nullable=True)

    def __init__(self, digest=None, loid=0, description=None):
        self.digest = digest
        self.loid = loid
        self.description = description

    @contextmanager
    def get_lobject(self, session=None, mode=None):
        if mode is None:
            mode = 'rb'
        if session is None:
            session = self.get_session()
        lo = lobject(session.connection().connection.connection, self.loid)
        if self.loid == 0:
            self.loid = lo.oid
        try:
            yield lo
        finally:
            lo.close()

    @classmethod
    def get_from_digest(cls, digest, session):
        try:
            return session.query(cls).filter(cls.digest == digest).one()
        except NoResultFound:
            return None
