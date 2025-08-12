#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import functools
import os.path

import xdg.BaseDirectory
import xdg.Mime
import xdg.Locale


__all__ = [
    "get_icon_for_type", "get_name_for_type",
    "get_type_for_file_name",
    ]


def _retrieve_icons():
    res = dict()
    for d in reversed([xdg.BaseDirectory.xdg_data_home]
                      + xdg.BaseDirectory.xdg_data_dirs):
        try:
            # This is a system file: open it with default system encoding.
            with open(os.path.join(d, "mime", "generic-icons"), "rt") as f:
                res.update(tuple(l.strip().split(':')) for l in f.readlines())
        except FileNotFoundError:
            pass
    return res


_icons = _retrieve_icons()


def get_icon_for_type(typename: str) -> str:
    """Get a generic icon name for the given MIME type.

    typename: a MIME type, e.g., "application/pdf".

    return: the generic icon that best depicts the given MIME
        type, e.g., "x-office-document".

    """
    mimetype = xdg.Mime.lookup(typename).canonical()
    typename = "%s/%s" % (mimetype.media, mimetype.subtype)
    if typename in _icons:
        return _icons[typename]
    return mimetype.media + "-x-generic"

# xdg.Mime is by default memoized, but since we need to change the language, we
# need to wipe the cache to load the correct language. So use our own caching
# on top of it.
@functools.cache
def get_name_for_type(typename: str, language: str, alt_language: str) -> str:
    """Get the natural language description of the MIME type.

    typename: a MIME type, e.g., "application/pdf".
    language: the BCP47 code of the language for which to return the result.
    alt_language: underscore-separated form of the language code, to work
        around incorrect behavior in pyxdg.

    return: the human-readable description (also called comment)
        of the given MIME type, e.g., "PDF document".

    """
    # pyxdg expects the locale field to be provided as a posix-style locale
    # name, e.g. zh_CN. It assumes this in both the provided language name, and
    # in the xml:lang attribute of the mimetype xml files. Some distributions
    # instead use BCP47 language codes, e.g. zh-Hans-CN, in the mimetype xml
    # files (which is semantically more correct, as this is mandated by the xml
    # spec).
    # First parse the language from the posix format.
    xdg.Locale.update(alt_language)
    # Then, we make pyxdg think the BCP47 code is another variant of the
    # current language name.
    xdg.Locale.langs += [language]
    mimetype = xdg.Mime.lookup(typename).canonical()
    # Force reloading the comment, because the language might have changed.
    mimetype._comment = None
    return mimetype.get_comment()


def get_type_for_file_name(filename: str) -> str | None:
    """Guess the MIME type of a file given its name.

    filename: the name of a file (just the base name, without the
        directory name), e.g., "statement.pdf".

    return: a guess of what MIME type that file might have,
        e.g., "application/pdf".

    """
    mimetype = xdg.Mime.get_type_by_name(filename)
    if mimetype is None:
        return None
    mimetype = mimetype.canonical()
    return "%s/%s" % (mimetype.media, mimetype.subtype)
