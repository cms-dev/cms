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
from cms.log import has_color_support


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


def print_with_color(string, color, stream=sys.stdout, bold=False, end="\n"):
    if has_color_support(stream):
        print("%s%s%s%s" % (
            curses.tparm(
                curses.tigetstr("setaf"), color
            ) if color != colors.BLACK else "",
            curses.tparm(curses.tigetstr("bold")) if bold else "",
            string,
            curses.tparm(curses.tigetstr("sgr0"))
        ), end=end, file=stream)
    else:
        print(string, end=end, file=stream)
    stream.flush()


def move_cursor(direction, amount=1, stream=sys.stdout, erase=False):
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
