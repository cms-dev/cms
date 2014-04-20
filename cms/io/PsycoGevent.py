#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# This file was taken from
# https://bitbucket.org/zzzeek/green_sqla/src/2732bb7ea9d06b9d4a61e8c \
# d587a95148ce2599b/green_sqla/psyco_gevent.py?at=default

"""A wait callback to allow psycopg2 cooperation with gevent.

Use `make_psycopg_green()` to enable gevent support in Psycopg.

"""

# Copyright (C) 2010 Daniele Varrazzo <daniele.varrazzo@gmail.com>
# Copyright (C) 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# and licensed under the MIT license:
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from contextlib import contextmanager

import psycopg2
from psycopg2 import extensions

from gevent.socket import wait_read, wait_write


def make_psycopg_green():
    """Configure Psycopg to be used with gevent in non-blocking way."""
    if not hasattr(extensions, 'set_wait_callback'):
        raise ImportError(
            "support for coroutines not available in this Psycopg version (%s)"
            % psycopg2.__version__)

    extensions.set_wait_callback(gevent_wait_callback)


def unmake_psycopg_green():
    """Undo make_psycopg_green()."""
    if not hasattr(extensions, 'set_wait_callback'):
        raise ImportError(
            "support for coroutines not available in this Psycopg version (%s)"
            % psycopg2.__version__)

    extensions.set_wait_callback(None)


def is_psycopg_green():
    """Test whether gevent compatibility layer is installed in psycopg."""
    if not hasattr(extensions, 'set_wait_callback'):
        raise ImportError(
            "support for coroutines not available in this Psycopg version (%s)"
            % psycopg2.__version__)

    return extensions.get_wait_callback() == gevent_wait_callback


def gevent_wait_callback(conn, timeout=None):
    """A wait callback useful to allow gevent to work with Psycopg."""
    while 1:
        state = conn.poll()
        if state == extensions.POLL_OK:
            break
        elif state == extensions.POLL_READ:
            wait_read(conn.fileno(), timeout=timeout)
        elif state == extensions.POLL_WRITE:
            wait_write(conn.fileno(), timeout=timeout)
        else:
            raise psycopg2.OperationalError(
                "Bad result from poll: %r" % state)


@contextmanager
def ungreen_psycopg():
    """Temporarily disable gevent support in psycopg.

    Inside this context manager you can use psycopg's features that
    are not compatible with coroutine support, such as large
    objects. Of course, at the expense of being blocking, so please
    stay inside the context manager as short as possible.

    """
    is_green = is_psycopg_green()
    if is_green:
        unmake_psycopg_green()
    try:
        yield
    finally:
        if is_green:
            make_psycopg_green()
