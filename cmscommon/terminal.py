#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Luca Versari <veluca93@gmail.com>
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

from __future__ import print_function
import curses
import sys


class colors(object):
    BLACK = curses.COLOR_BLACK
    RED = curses.COLOR_RED
    GREEN = curses.COLOR_GREEN
    YELLOW = curses.COLOR_YELLOW
    BLUE = curses.COLOR_BLUE
    MAGENTA = curses.COLOR_MAGENTA
    CYAN = curses.COLOR_CYAN
    WHITE = curses.COLOR_WHITE


class directions(object):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4


def has_color_support(stream):
    """Try to determine if the given stream supports colored output.

    Return True only if the stream declares to be a TTY, if it has a
    file descriptor on which ncurses can initialize a terminal and if
    that terminal's entry in terminfo declares support for colors.

    stream (fileobj): a file-like object (that adheres to the API
        declared in the `io' package).

    return (bool): True if we're sure that colors are supported, False
        if they aren't or if we can't tell.

    """
    if stream.isatty():
        try:
            curses.setupterm(fd=stream.fileno())
            # See `man terminfo` for capabilities' names and meanings.
            if curses.tigetnum("colors") > 0:
                return True
        # fileno() can raise IOError or OSError (since Python 3.3).
        except Exception:
            pass
    return False


def add_color_to_string(string, color, stream=sys.stdout, bold=False,
                        force=False):
    """Format the string to be printed with the given color.

    Insert formatting characters that, when printed on a terminal, will
    make the given string appear with the given foreground color if the
    stream passed has color support. Else return the string as it is.

    string (string): the string to color.
    color (int): the color as a colors constant, like colors.BLACK.
    stream (fileobj): a file-like object (that adheres to the API
        declared in the `io' package). Defaults to sys.stdout.
    bold (bool): True if the string should be bold.
    force (bool): True if the string should be formatted even if the
        given stream has no color support.

    return (string): the formatted string.

    """
    if force or has_color_support(stream):
        return "%s%s%s%s" % (
            curses.tparm(
                curses.tigetstr("setaf"), color
            ) if color != colors.BLACK else "",
            curses.tparm(curses.tigetstr("bold")) if bold else "",
            string,
            curses.tparm(curses.tigetstr("sgr0"))
        )
    else:
        return string


def move_cursor(direction, amount=1, stream=sys.stdout, erase=False):
    """Move the cursor.

    If the stream is a TTY, print characters that will move the cursor
    in the given direction and optionally erase the line. Else do nothing.

    direction (int): the direction as a directions constant, like
        directions.UP.
    stream (fileobj): a file-like object (that adheres to the API
        declared in the `io' package). Defaults to sys.stdout.
    erase (bool): True if the line the cursor ends on should be erased.

    """
    if stream.isatty():
        if direction == directions.UP:
            print(curses.tparm(curses.tigetstr("cuu"), amount),
                  file=stream, end='')
        elif direction == directions.DOWN:
            print(curses.tparm(curses.tigetstr("cud"), amount),
                  file=stream, end='')
        elif direction == directions.LEFT:
            print(curses.tparm(curses.tigetstr("cub"), amount),
                  file=stream, end='')
        elif direction == directions.RIGHT:
            print(curses.tparm(curses.tigetstr("cuf"), amount),
                  file=stream, end='')
        if erase:
            print(curses.tparm(curses.tigetstr("el")), file=stream, end='')
        stream.flush()
