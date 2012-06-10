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

"""SQLAlchemy interfaces to store files in the database. Not to be
used directly (import from SQLAlchemyAll).

"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm.exc import NoResultFound

from psycopg2 import OperationalError
from psycopg2.extensions import lobject

from cms.db.SQLAlchemyUtils import Base

from contextlib import contextmanager


class FSObject(Base):
    """Class to describe a file stored in the database.

    """

    __tablename__ = 'fsobjects'

    # Here we use the digest (SHA1 sum) of the file as primary key;
    # ideally al the columns that refer digests could be declared as
    # foreign keys against this column, but we intentiolally avoid
    # doing this to keep uncoupled the database and the file storage
    digest = Column(String, primary_key=True)

    # OID of the large object in the database
    loid = Column(Integer, nullable=False)

    # Human-readable description, primarily meant for debugging (i.e,
    # should have no semantic value from the viewpoint of CMS)
    description = Column(String, nullable=True)

    def __init__(self, digest=None, loid=0, description=None):
        self.digest = digest
        self.loid = loid
        self.description = description

    @contextmanager
    def get_lobject(self, session=None, mode=None):
        """Return an open file bounded to the represented large
        object. This is a context manager, so it should be used with
        the `with' clause this way:

          with fsobject.get_lobject() as lo:

        session (session object): the session to use, or None to use
                                  the one associated with the FSObject.
        mode (string): how to open the file (r -> read, w -> write,
                       b -> binary). If None, use `rb'.

        """
        if mode is None:
            mode = 'rb'
        if session is None:
            session = self.get_session()

        # Here we relay on the fact that we're using psycopg2 as
        # PostgreSQL backend
        lo = lobject(session.connection().connection.connection, self.loid)

        if self.loid == 0:
            self.loid = lo.oid

        try:
            yield lo
        finally:
            lo.close()

    def check_lobject(self):
        """Check that the referenced large object is actually
        available in the database.

        """
        try:
            lo = lobject(self.get_session().connection().connection.connection,
                         self.loid)
            lo.close()
            return True
        except OperationalError:
            return False

    def delete(self):
        """Delete this file.

        """
        with self.get_lobject() as lo:
            lo.unlink()
        self.get_session().delete(self)

    @classmethod
    def get_from_digest(cls, digest, session):
        """Return the FSObject with the specified digest, using the
        specified session.

        """
        try:
            return session.query(cls).filter(cls.digest == digest).one()
        except NoResultFound:
            return None

    @classmethod
    def get_all(cls, session):
        """Iterate over all the FSObjects available in the database.

        """
        if cls.__table__.exists():
            return session.query(cls)
        else:
            return []

    @classmethod
    def delete_all(cls, session):
        """Delete all files stored in the database. This cannot be
        undone. Large objects not linked by some FSObject cannot be
        detected at the moment, so they don't get deleted.

        """
        for fso in cls.get_all(session):
            fso.delete()

    def export_to_dict(self):
        """FSObjects cannot be exported to a dictionary.

        """
        return {}
