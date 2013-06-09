#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""A collection of misc utilities that behave nicely towards gevent,
yielding from time to time in order to pass the control to other
greenlets.

If gevent is not being used, these routines will behave in the common
blocking way.

"""

from contextlib import contextmanager

import gevent

from cms.async.PsycoGevent import make_psycopg_green, \
    unmake_psycopg_green


def copyfileobj(fsrc, fdst, length=16 * 1024):
    """As shutil.copyfilobj(), but with gevent support.

    """
    while True:
        buf = fsrc.read(length)
        if not buf:
            break
        fdst.write(buf)
        gevent.sleep(0)


def copyfile(src, dst):
    """As shutil.copyfile(), but with gevent support.

    There are actually some minor differences: this method doesn't
    perform some checks about file types that the method in shlib
    does.

    """
    with open(src, 'rb') as fsrc:
        with open(dst, 'wb') as fdst:
            copyfileobj(fsrc, fdst)


@contextmanager
def ungreen_psycopg():
    """Temporarily disable gevent support in psycopg.

    Inside this context manager you can use psycopg's features that
    are not compatible with coroutine support, such as large
    objects. Of course, at the expense of being blocking, so please
    stay inside the context manager as short as possible.

    """
    unmake_psycopg_green()
    try:
        yield
    finally:
        make_psycopg_green()
