#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Admin-related database interfaces for SQLAlchemy.

"""

from sqlalchemy.schema import Column
from sqlalchemy.types import Boolean, Integer, Unicode

from . import Codename, Base


class Admin(Base):
    """Class to store information for a person able to access AWS.

    An enabled account always has read access to all of AWS. For
    changing data and perform actions, additional permission bits
    need to be set.

    """

    __tablename__ = 'admins'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Real name (human readable) of the user.
    name = Column(
        Unicode,
        nullable=False)

    # Username used to log in in AWS.
    username = Column(
        Codename,
        nullable=False,
        unique=True)

    # String used to authenticate the user, in the format
    # <authentication type>:<authentication_string>
    authentication = Column(
        Unicode,
        nullable=False)

    # Whether the account is enabled. Disabled accounts have their
    # info kept in the database, but for all other purposes it is like
    # they did not exist.
    enabled = Column(
        Boolean,
        nullable=False,
        default=True)

    # All-access bit. If this is set, the admin can do any operation
    # in AWS, regardless of the value of the other access bits.
    permission_all = Column(
        Boolean,
        nullable=False,
        default=False)

    # Messaging-access bit. If this is set, the admin can communicate
    # with the contestants via announcement, private messages and
    # questions.
    permission_messaging = Column(
        Boolean,
        nullable=False,
        default=False)
