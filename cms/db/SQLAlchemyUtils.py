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

from sqlalchemy import create_engine, __version__ as sqlalchemy_version
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.orm import session as sessionlib

from cms import config

# We need version 0.7.3 because of the __abstract__ keyword.
sqlalchemy_version = tuple(int(x) for x in sqlalchemy_version.split("."))
assert sqlalchemy_version >= (0, 7, 3), \
       "Please install SQLAlchemy >= 0.7.3."

db_string = config.database.replace("%s", config.data_dir)
db = create_engine(db_string, echo=config.database_debug,
                   pool_size=20, pool_recycle=120)

Session = sessionmaker(db, twophase=config.twophase_commit)
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


class Base(object):
    """Base class for all classes managed by SQLAlchemy. Extending the
    base class given by SQLAlchemy.

    """
    # Needed so that SQLAlchemy does not think that this corresponds
    # to a table.
    __abstract__ = True

    @classmethod
    def get_from_id(cls, _id, session):
        """Given a session and an id, this class method returns the object
        corresponding to the class and id, if existing.

        cls (class): the class to which the method is attached
        _id (string): the id of the object we want
        session (SQLAlchemy session): the session to query

        return (object): the wanted object, or None

        """
        try:
            return session.query(cls).filter(cls.id == _id).one()
        except NoResultFound:
            return None
        except MultipleResultsFound:
            return None

    def get_session(self):
        """Get the session to which this object is bound, possibly None.

        """
        try:
            return sessionlib.object_session(self)
        except:
            return None

    def export_to_dict(self):
        """Placeholder for exporting method.

        """
        raise NotImplementedError("Please subclass me.")

    @classmethod
    def import_from_dict(cls, data):
        """Placeholder for importing method. These cannot be defined
        neither here nor at the time of the definition of the subclass
        (because they usually depends on a lot of other db-related
        classes). So we define them in ImportFromDict. To avoid
        unnecessary warnings, we don't throw a NotImplementedError
        here.

        """
        return cls(**data)


Base = declarative_base(db, cls=Base)


metadata = Base.metadata
