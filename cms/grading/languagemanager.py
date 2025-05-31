#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Provide utilities to work with programming language classes."""

from cms import plugin_list
from cms.grading.language import Language


__all__ = [
    "LANGUAGES",
    "HEADER_EXTS", "SOURCE_EXTS", "OBJECT_EXTS",
    "get_language", "filename_to_language"
]


LANGUAGES: list[Language] = list()
_BY_NAME: dict[str, Language] = dict()
HEADER_EXTS: set[str] = set()
OBJECT_EXTS: set[str] = set()
SOURCE_EXTS: set[str] = set()


def get_language(name: str) -> Language:
    """Return the language object corresponding to the given name.

    name: name of the requested language.
    return: language object.

    raise (KeyError): if the name does not correspond to a language.

    """
    if name not in _BY_NAME:
        raise KeyError("Language `%s' not supported." % name)
    return _BY_NAME[name]


def filename_to_language(filename: str) -> Language | None:
    """Return one of the languages inferred from the given filename.

    filename: the file to test.

    return: one (arbitrary, but deterministic) language
    matching the given filename, or None if none match.

    """
    ext_index = filename.rfind(".")
    if ext_index == -1:
        return None
    ext = filename[ext_index:]
    names = sorted(language.name
                   for language in LANGUAGES
                   if ext in language.source_extensions)
    return None if len(names) == 0 else get_language(names[0])


def _load_languages():
    """Load the available languages and fills all other data structures."""
    if len(LANGUAGES) > 0:
        return

    for cls in plugin_list("cms.grading.languages"):
        language = cls()
        LANGUAGES.append(language)
        _BY_NAME[language.name] = language
        HEADER_EXTS.update(language.header_extensions)
        OBJECT_EXTS.update(language.object_extensions)
        SOURCE_EXTS.update(language.source_extensions)


# Initialize!
_load_languages()
