#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

from sqlalchemy import create_engine, __version__ as sqlalchemy_version
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import ObjectDeletedError
from sqlalchemy.orm.session import object_session
from sqlalchemy.orm import class_mapper, object_mapper, \
                           ColumnProperty, RelationshipProperty
from sqlalchemy.types import Boolean, Integer, Float, String, DateTime, Interval

from datetime import datetime, timedelta

from cms import config

import six

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


_type_map = {
    Boolean: bool,
    Integer: six.integer_types,
    Float: float,
    String: six.string_types, # XXX unicode, bytes or both?
    DateTime: datetime,
    Interval: timedelta,
    }


class Base(object):
    """Base class for all classes managed by SQLAlchemy. Extending the
    base class given by SQLAlchemy.

    """
    @property
    def sa_mapper(self):
        return object_mapper(self)

    @property
    def sa_session(self):
        return object_session(self)

    @property
    def sa_primary_key(self):
        return self.sa_mapper.primary_key_from_instance(self)

    @property
    def sa_identity_key(self):
        return self.sa_mapper.identity_key_from_instance(self)

    # This method gets called after the mapper has been initialized
    # (i.e. all properties, both columns and relationships) are ready to use
    @classmethod
    def __declare_last__(cls):
        """Analyze and extract properties of mapper and save them in cls

        Split the properties into column and relationship properties and
        raise RuntimeError if something isn't correctly understood.

        """
        # Divide all properties into column and relationship ones.
        cls._col_props = list()
        cls._rel_props = list()

        for prp in class_mapper(cls).iterate_properties:
            if isinstance(prp, ColumnProperty):
                if len(prp.columns) != 1:
                    raise RuntimeError(
                        "Unexpected number of columns for ColumnProperty %s of"
                        " %s: %d" % (prp.key, cls.__name__, len(prp.columns)))
                col = prp.columns[0]
                col_type = type(col.type)

                # Ignore IDs and foreign keys
                if col.primary_key or col.foreign_keys:
                    continue

                # Check that we understand the type
                if col_type not in _type_map:
                    raise RuntimeError(
                        "Unknown SQLAlchemy column type for ColumnProperty "
                        "%s of %s: %s" % (prp.key, cls.__name__, col_type))

                cls._col_props.append(prp)
            elif isinstance(prp, RelationshipProperty):
                cls._rel_props.append(prp)
            else:
                raise RuntimeError(
                    "Unknown SQLAlchemy property type for %s of %s: %s" %
                    (prp.key, cls.__name__, type(prp)))

    def __init__(self, *args, **kwargs):
        """Initialize a new object with the given properties

        The properties we're referring to are the SQLAlchemy ones,
        specified as class-level attributes during class definition.
        They can be of two types: column or relationship properties
        (note that a relationship can also be created by a backref
        of another relationship property). For the purpose of this
        method the column properties that are part of a primary key
        or of a foreign key constraint are ignored.

        This constructor behaves like the following one (which uses
        Python 3 syntax, see [1][2][3] for additional information):

            obj = cls(<col props>, *, <rel props>)

        This means that the column properties can be specified both
        as positional and as keyword arguments while the relationship
        properties have to be given as keyword arguments. The order
        in which column properties appear as positional arguments is
        the order they were defined as class-attributes.

        All relationship properties are optional. Column properties
        are optional only if they're nullable or if they have a not
        null default value. The default value is the one specified
        in the Column() call used to define the property (None by
        default). This could cause us to violate a restriction that
        the Python syntax (see [2]) imposes on other functions: an
        argument without a default value may come after one with it.

        Additionally, this function also does some type-checking for
        column properties: a TypeError is raised if a given argument
        has a type that doesn't match the one of the corresponding
        property. Relationship properties aren't checked (for now).

        [1] http://www.python.org/dev/peps/pep-3102/
        [2] http://docs.python.org/3/reference/compound_stmts.html#function
        [3] http://docs.python.org/3/reference/expressions.html#calls

        """
        cls = type(self)

        # Check the number of positional argument
        if len(args) > len(cls._col_props):
            raise TypeError(
                "%s.__init__() takes at most %d positional arguments (%d "
                "given)" % (cls.__name__, len(cls._col_props), len(args)))

        # Copy the positional arguments into the keyword ones
        for arg, prp in zip(args, cls._col_props):
            if prp.key in kwargs:
                raise TypeError(
                    "%s.__init__() got multiple values for keyword "
                    "argument '%s'" % (cls.__name__, prp.key))
            kwargs[prp.key] = arg

        for prp in cls._col_props:
            col = prp.columns[0]
            col_type = type(col.type)

            if prp.key not in kwargs:
                # We're assuming the default value, if specified, has
                # the correct type
                if col.default is None and not col.nullable:
                    raise TypeError(
                        "%s.__init__() didn't get required keyword "
                        "argument '%s'" % (cls.__name__, prp.key))
                # We're setting the default ourselves, since we may
                # want to use the object before storing it in the DB.
                # FIXME This code doesn't work with callable defaults.
                # We can use the is_callable and is_scalar properties
                # (and maybe the is_sequence and is_clause_element ones
                # too) to detect the type. Note that callables require a
                # ExecutionContext argument (which we don't have).
                if col.default is not None:
                    setattr(self, prp.key, col.default.arg)
            else:
                val = kwargs.pop(prp.key)

                if val is None:
                    if not col.nullable:
                        raise TypeError(
                            "%s.__init__() got None for keyword argument '%s',"
                            " which is not nullable" % (cls.__name__, prp.key))
                else:
                    # TODO col_type.python_type contains the type that
                    # SQLAlchemy thinks is more appropriate. We could
                    # use that and drop _type_map...
                    if not isinstance(val, _type_map[col_type]):
                        raise TypeError(
                            "%s.__init__() got a '%s' for keyword argument "
                            "'%s', which requires a '%s'" % (cls.__name__,
                            type(val), prp.key, _type_map[col_type]))
                    setattr(self, prp.key, val)

        for prp in cls._rel_props:
            if prp.key not in kwargs:
                # If the property isn't given we leave the default
                # value instead of explictly setting it ourself.
                pass
            else:
                val = kwargs.pop(prp.key)

                # TODO Some type validation (take a look at prp.uselist)
                setattr(self, prp.key, val)

        # Check if there were unknown arguments
        if kwargs:
            raise TypeError(
                "%s.__init__() got an unexpected keyword argument '%s'\n%s" %
                (cls.__name__, kwargs, kwargs.popitem()[0]))

    @classmethod
    def get_from_id(cls, id_, session):
        """Given a session and an id, this class method returns the object
        corresponding to the class and id, if existing.

        cls (class): the class to which the method is attached
        id_ (string): the id of the object we want
        session (SQLAlchemy session): the session to query

        return (object): the wanted object, or None

        """
        try:
            # This method returns None if the object isn't in the
            # identity map of the session nor in the database, but
            # raises ObjectDeletedError in case it was in the identity
            # map, got marked as expired but couldn't be found in the
            # database again.
            return session.query(cls).get(id_)
        except ObjectDeletedError:
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


Base = declarative_base(db, cls=Base, constructor=None)


metadata = Base.metadata
