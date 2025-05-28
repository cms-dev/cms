#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import ipaddress
from datetime import datetime, timedelta
import typing

from sqlalchemy.dialects.postgresql import ARRAY, CIDR, JSONB, OID
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.orm import \
    class_mapper, object_mapper, ColumnProperty, RelationshipProperty
from sqlalchemy.orm.exc import ObjectDeletedError
from sqlalchemy.orm.session import object_session
from sqlalchemy.types import \
    Boolean, Integer, Float, String, Unicode, Enum, DateTime, Interval, \
    BigInteger

from cms.db.session import Session

from . import engine, metadata, CastingArray, Codename, Filename, \
    FilenameSchema, FilenameSchemaArray, Digest


_TYPE_MAP = {
    Boolean: bool,
    Integer: int,
    BigInteger: int,
    OID: int,
    Float: float,
    Enum: str,
    Unicode: str,
    String: str,  # TODO Use bytes.
    Codename: str,
    Filename: str,
    FilenameSchema: str,
    Digest: str,
    DateTime: datetime,
    Interval: timedelta,
    ARRAY: list,
    CastingArray: list,
    FilenameSchemaArray: list,
    CIDR: (ipaddress.IPv4Network, ipaddress.IPv6Network),
    JSONB: object,
}


# this has an @as_declarative, but to ease type checking it's applied manually
# after the class definition, only when not type-checking (i.e. at runtime).
class Base:
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

        Split the properties into column and relationship properties.

        raise (RuntimeError): if something isn't correctly understood.

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

                # Ignore IDs and foreign keys
                if col.primary_key or col.foreign_keys:
                    continue

                # Check that we understand the type
                if not isinstance(col.type, tuple(_TYPE_MAP.keys())):
                    raise RuntimeError(
                        "Unknown SQLAlchemy column type for ColumnProperty "
                        "%s of %s: %s" % (prp.key, cls.__name__, col.type))

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

        # Check the number of positional arguments
        if len(args) > len(self._col_props):
            raise TypeError(
                "%s.__init__() takes at most %d positional arguments (%d "
                "given)" % (cls.__name__, len(self._col_props), len(args)))

        # Copy the positional arguments into the keyword ones
        for arg, prp in zip(args, self._col_props):
            if prp.key in kwargs:
                raise TypeError(
                    "%s.__init__() got multiple values for keyword "
                    "argument '%s'" % (cls.__name__, prp.key))
            kwargs[prp.key] = arg

        try:
            self.set_attrs(kwargs, fill_with_defaults=True)
        except TypeError as err:
            message, = err.args
            err.args = (message.replace("set_attrs()",
                                        "%s.__init__()" % cls.__name__),)
            raise

    @classmethod
    def get_from_id(cls, id_: tuple | int | str, session: Session) -> typing.Self | None:
        """Retrieve an object from the database by its ID.

        Use the given session to fetch the object of this class with
        the given ID, and return it. If it doesn't exist return None.

        cls: the class to which the method is attached.
        id_: the ID of the object we want; in
            general it will be a tuple (one int for each of the columns
            that make up the primary key) but if there's only one then
            a single int (even encoded as unicode or bytes) will work.
        session: the session to query.

        return: the desired object, or None if not found.

        """
        try:
            # The .get() method returns None if the object isn't in the
            # identity map of the session nor in the database, but
            # raises ObjectDeletedError in case it was in the identity
            # map, got marked as expired but couldn't be found in the
            # database again.
            return session.query(cls).get(id_)
        except ObjectDeletedError:
            return None

    def clone(self) -> typing.Self:
        """Copy all the column properties into a new object

        Create a new object of this same type and set the values of all
        its column properties to the ones of this "old" object. Leave
        the relationship properties unset.

        return: a clone of this object

        """
        cls = type(self)
        args = list(getattr(self, prp.key) for prp in self._col_props)
        return cls(*args)

    def get_attrs(self) -> dict[str, object]:
        """Return self.__dict__.

        Limited to SQLAlchemy column properties.

        return: the properties of this object.

        """
        attrs = dict()
        for prp in self._col_props:
            if hasattr(self, prp.key):
                attrs[prp.key] = getattr(self, prp.key)
        return attrs

    def set_attrs(self, attrs: dict[str, object], fill_with_defaults: bool = False):
        """Do self.__dict__.update(attrs) with validation.

        Limited to SQLAlchemy column and relationship properties.

        attrs: the new properties we want to set on
            this object.
        fill_with_defaults: whether to explicitly reset the
            attributes that were not provided in attrs to their default
            value.

        """
        # We want to pop items without altering the caller's object.
        attrs = attrs.copy()

        for prp in self._col_props:
            col = prp.columns[0]

            if prp.key not in attrs and fill_with_defaults:
                # We're assuming the default value, if specified, has
                # the correct type
                if col.default is None and not col.nullable:
                    raise TypeError(
                        "set_attrs() didn't get required keyword "
                        "argument '%s'" % prp.key)
                # We're setting the default ourselves, since we may
                # want to use the object before storing it in the DB.
                # FIXME This code doesn't work with callable defaults.
                # We can use the is_callable and is_scalar properties
                # (and maybe the is_sequence and is_clause_element ones
                # too) to detect the type. Note that callables require
                # an ExecutionContext argument (which we don't have).
                if col.default is not None:
                    setattr(self, prp.key, col.default.arg)
            elif prp.key in attrs:
                val = attrs.pop(prp.key)

                if val is None:
                    if not col.nullable:
                        raise TypeError(
                            "set_attrs() got None for keyword argument '%s',"
                            " which is not nullable" % prp.key)
                    setattr(self, prp.key, val)
                else:
                    # TODO col.type.python_type contains the type that
                    # SQLAlchemy thinks is more appropriate. We could
                    # use that and drop _TYPE_MAP...
                    py_type = _TYPE_MAP[type(col.type)]
                    if not isinstance(val, py_type):
                        raise TypeError(
                            "set_attrs() got a '%s' for keyword argument "
                            "'%s', which requires a '%s'" %
                            (type(val), prp.key, py_type))
                    if isinstance(col.type, ARRAY):
                        py_item_type = _TYPE_MAP[type(col.type.item_type)]
                        for item in val:
                            if not isinstance(item, py_item_type):
                                raise TypeError(
                                    "set_attrs() got a '%s' inside the list "
                                    "for keyword argument '%s', which requires "
                                    "a list of '%s'"
                                    % (type(item), prp.key, py_item_type))
                    setattr(self, prp.key, val)

        for prp in self._rel_props:
            if prp.key in attrs:
                val = attrs.pop(prp.key)

                # TODO Some type validation (take a look at prp.uselist)
                setattr(self, prp.key, val)

        # Check if there were unknown arguments
        if attrs:
            raise TypeError(
                "set_attrs() got an unexpected keyword argument '%s'" %
                attrs.popitem()[0])

# don't apply the decorator when type checking, as as_declarative doesn't have
# enough type hints for pyright to consider it valid. This means that pyright
# doesn't consider Base to be a valid base class, and thus all derived classes
# will be missing the methods from Base.
if not typing.TYPE_CHECKING:
    Base = as_declarative(bind=engine, metadata=metadata, constructor=None)(Base)
