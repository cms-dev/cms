#!/usr/bin/env python3

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

"""SQLAlchemy interfaces to store files in the database.

"""

from collections.abc import Iterable
import io
from typing import Self
import typing

import psycopg2
import psycopg2.extensions
from sqlalchemy.dialects.postgresql import OID
from sqlalchemy.schema import Column
from sqlalchemy.types import String, Unicode

from . import Base, custom_psycopg2_connection, Session


class LargeObject(io.RawIOBase, typing.BinaryIO):

    """Present a PostgreSQL large object as a Python file-object.

    A LargeObject creates and maintains (i.e. closes when done) its
    own connection to the database. This approach is preferred over
    using one of the connections pooled by SQLAlchemy (for example by
    "borrowing" the one of the Session of the FSObject that created the
    LO instance, if any!) to make these objects independent from the
    Session (in particular, to allow them to live longer) and to avoid
    polluting the connections in the SQLAlchemy pool (because executing
    queries on the underlying DB API driver connection means kind of
    "abusing" the SQLAlchemy API, and also because we don't want to
    interfere with the life-cycle of these connections).

    We cannot use the lobject interface provided by psycopg2 because
    it's incompatible with asynchronous connections and thus coroutine
    libraries (like gevent). Hence, we use functions called via SQL
    queries to manipulate large objects on the server.

    This class extends RawIOBase and is therefore a fully-compliant
    file-like object. As for I/O, it just needs to provide the
    `readinto' and `write' methods, as all others (`read', `readall',
    `readline', `readlines', `writelines') are implemented in terms of
    these two by the parent class. See the official documentation for
    IOBase and RawIOBase to know the interface this class provides:
    http://docs.python.org/2.7/library/io.html

    """

    # Some constants from libpq, that are not published by psycopg2.
    INV_READ = 0x40000
    INV_WRITE = 0x20000

    def __init__(self, loid: int, mode: str = 'rb'):
        """Open a large object, creating it if required.

        loid: the large object ID.
        mode: how to open the file (`r' -> read, `w' -> write,
            `b' -> binary, which must be always specified). If not
            given, `rb' is used.

        """
        io.RawIOBase.__init__(self)

        self.loid = loid

        # Check mode value.
        modeset = set(mode)
        if not modeset.issubset('rwb'):
            raise ValueError("Only valid characters in mode are r, w and b.")
        if modeset.isdisjoint('rw'):
            raise ValueError("Character r or b must be specified in mode.")
        if 'b' not in modeset:
            raise ValueError("Character b must be specified in mode.")

        self._readable = 'r' in modeset
        self._writable = 'w' in modeset

        self._conn = custom_psycopg2_connection()
        cursor = self._conn.cursor()

        # If the loid is 0, create the large object.
        if self.loid == 0:
            creat_mode = LargeObject.INV_READ | LargeObject.INV_WRITE
            self.loid = self._execute("SELECT lo_creat(%(mode)s);",
                                      {'mode': creat_mode},
                                      "Couldn't create large object.", cursor)
            if self.loid == 0:
                raise OSError("Couldn't create large object.")

        # Open the large object.
        open_mode = (LargeObject.INV_READ if self._readable else 0) | \
                    (LargeObject.INV_WRITE if self._writable else 0)
        self._fd = self._execute("SELECT lo_open(%(loid)s, %(mode)s);",
                                 {'loid': self.loid, 'mode': open_mode},
                                 "Couldn't open large object with LOID "
                                 "%s." % self.loid, cursor)

        cursor.close()

    # cursor is typed as typing.Any because psycopg2 doesn't have good type hints.
    def _execute(
        self,
        operation: str,
        parameters: dict[str, typing.Any],
        message: str,
        cursor: typing.Any | None = None
    ) -> typing.Any:
        """Run the given query making many success checks.

        Execute the given SQL statement, instantiated with the given
        parameters, on the given cursor, making sure the connection is
        in an usable condition and is left such! Also check that there
        is a single return value and, if it's a status code, that it's
        not negative.

        operation: the SQL query to perform, with named
            string  placeholders (i.e. "%(name)s").
        parameters: the parameters to fill in the operation.
        message: a description to tell humans what we were
            doing in case something went wrong.
        cursor: the cursor to use to execute the
            statement (create and use a temporary one if not given).

        """
        if cursor is None:
            cursor = self._conn.cursor()
            res = self._execute(operation, parameters, message, cursor)
            cursor.close()
            return res

        try:
            assert self._conn.status in (
                psycopg2.extensions.STATUS_READY,
                psycopg2.extensions.STATUS_BEGIN)
            assert self._conn.get_transaction_status() in (
                psycopg2.extensions.TRANSACTION_STATUS_IDLE,
                psycopg2.extensions.TRANSACTION_STATUS_INTRANS)

            cursor.execute(operation, parameters)

            assert self._conn.status == \
                psycopg2.extensions.STATUS_BEGIN
            assert self._conn.get_transaction_status() == \
                psycopg2.extensions.TRANSACTION_STATUS_INTRANS

            res, = cursor.fetchone()

            assert len(cursor.fetchall()) == 0
            if isinstance(res, int):
                assert res >= 0
        except (AssertionError, ValueError, psycopg2.DatabaseError):
            raise OSError(message)
        else:
            return res

    def readable(self):
        """See IOBase.readable().

        """
        return self._readable

    def writable(self):
        """See IOBase.writable().

        """
        return self._writable

    def seekable(self):
        """See IOBase.seekable().

        """
        return True

    @property
    def closed(self):
        """See IOBase.closed().

        """
        return self._fd is None

    def readinto(self, buf) -> int:
        """Read from the large object, and write to the given buffer.

        Try to read as much data as we can fit into buf. If less is
        obtained, stop and don't do further SQL calls. The number of
        retrieved bytes is returned.

        buf: buffer into which to write data (e.g. bytearray).

        return: the number of bytes read.

        raise (io.UnsupportedOperation): when the file is closed or
            not open for reads.

        """
        if self._fd is None:
            raise io.UnsupportedOperation("Large object is closed.")

        if not self._readable:
            raise io.UnsupportedOperation("Large object hasn't been "
                                          "opened in 'read' mode.")

        data = self._execute("SELECT loread(%(fd)s, %(len)s);",
                             {'fd': self._fd, 'len': len(buf)},
                             "Couldn't write to large object.")
        buf[:len(data)] = data
        return len(data)

    def write(self, buf) -> int:
        """Write to the large object, reading from the given buffer.

        Try to write as much data as we have available. If less is
        stored, stop and don't do further SQL calls. The number of sent
        bytes is returned.

        buf: buffer from which to read data (e.g. bytes or bytearray).

        return: the number of bytes written.

        raise (io.UnsupportedOperation): when the file is closed or
            not open for writes.

        """
        if self._fd is None:
            raise io.UnsupportedOperation("Large object is closed.")

        if not self._writable:
            raise io.UnsupportedOperation("Large object hasn't been "
                                          "opened in 'write' mode.")

        len_ = self._execute("SELECT lowrite(%(fd)s, %(buf)s);",
                             {'fd': self._fd, 'buf': psycopg2.Binary(buf)},
                             "Couldn't write to large object.")
        return len_

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Move the stream position in large object.

        offset: offset from the reference point.
        whence: reference point, expressed like in os.seek().

        return: the new absolute position.

        raise (io.UnsupportedOperation): when the file is closed.

        """
        if self._fd is None:
            raise io.UnsupportedOperation("Large object is closed.")

        pos = self._execute("SELECT lo_lseek(%(fd)s, %(offset)s, %(whence)s);",
                            {'fd': self._fd,
                             'offset': offset,
                             'whence': whence},
                            "Couldn't seek large object.")
        return pos

    def tell(self) -> int:
        """Tell the stream position in a large object.

        return: the absolute position.

        """
        if self._fd is None:
            raise io.UnsupportedOperation("Large object is closed.")

        pos = self._execute("SELECT lo_tell(%(fd)s);",
                            {'fd': self._fd},
                            "Couldn't tell large object.")
        return pos

    def truncate(self, size: int | None = None) -> int:
        """Trucate a large object.

        size: the desired new size. If None, defaults to
            current position.

        return: the new actual size.

        """
        if self._fd is None:
            raise io.UnsupportedOperation("Large object is closed.")

        if not self._writable:
            raise io.UnsupportedOperation("Large object hasn't been "
                                          "opened in 'write' mode.")

        if size is None:
            size = self.tell()

        self._execute("SELECT lo_truncate(%(fd)s, %(size)s);",
                      {'fd': self._fd, 'size': size},
                      "Couldn't truncate large object.")
        return size

    def close(self):
        """Close the large object.

        After this call the object is not usable anymore. It is
        allowed to close an object more than once, with the calls
        after the first doing nothing.

        """
        # If the large object has already been closed, don't close it
        # again.
        if self._fd is None:
            return

        self._execute("SELECT lo_close(%(fd)s);",
                      {'fd': self._fd},
                      "Couldn't close large object.")

        self._conn.commit()

        # We delete the fd number to avoid writing on another file by
        # mistake
        self._fd = None

    @staticmethod
    def unlink(loid: int, conn=None):
        """Delete the large object, removing its content.

        After an unlink, the content can't be restored anymore, so use
        with caution!

        """
        if conn is None:
            conn = custom_psycopg2_connection()
            conn.autocommit = True

        with conn.cursor() as cursor:
            cursor.execute("SELECT lo_unlink(%(loid)s);", {'loid': loid})


class FSObject(Base):
    """Class to describe a file stored in the database.

    """

    __tablename__ = 'fsobjects'

    # Here we use the digest (SHA1 sum) of the file as primary key;
    # ideally all the columns that refer to digests could be declared
    # as foreign keys against this column, but we intentionally avoid
    # doing this to keep the database uncoupled from the file storage.
    digest: str = Column(
        String,
        primary_key=True,
        nullable=False)

    # OID of the large object in the database
    loid: int = Column(
        OID,
        nullable=False,
        default=0)

    # Human-readable description, primarily meant for debugging (i.e,
    # should have no semantic value from the viewpoint of CMS)
    description: str | None = Column(
        Unicode,
        nullable=True)

    def get_lobject(self, mode: str = 'rb') -> LargeObject:
        """Return an open file bound to the represented large object.

        The returned value acts as a context manager, so it can be used
        inside a `with' clause, this way:

            with fsobject.get_lobject() as lobj:

        mode: how to open the file (`r' -> read, `w' -> write,
             `b' -> binary, which must be always specified). If not
             given, `rb' is used.

        """
        assert self.loid != 0, "Expected LO to have already been created!"
        # Here we rely on the fact that we're using psycopg2 as
        # PostgreSQL backend.
        lobj = LargeObject(self.loid, mode)

        # FIXME Wrap with a io.BufferedReader/Writer/Random?
        return lobj

    def delete(self):
        """Delete this file.

        """
        LargeObject.unlink(self.loid)
        self.sa_session.delete(self)

    @classmethod
    def get_from_digest(cls, digest: str, session: Session) -> Self | None:
        """Return the FSObject with the specified digest, using the
        specified session.

        """
        return cls.get_from_id(digest, session)

    @classmethod
    def get_all(cls, session: Session) -> Iterable[Self]:
        """Iterate over all the FSObjects available in the database.

        """
        if cls.__table__.exists():
            return session.query(cls)
        else:
            return []

    @classmethod
    def delete_all(cls, session: Session):
        """Delete all files stored in the database. This cannot be
        undone. Large objects not linked by some FSObject cannot be
        detected at the moment, so they don't get deleted.

        """
        for fso in cls.get_all(session):
            fso.delete()
