#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Manage translations and localization stuff.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *
import six

import pkg_resources
import gettext
import logging
import os
import string

import babel.core
import babel.support

from cms import config


logger = logging.getLogger(__name__)


def get_system_translations(lang):
    """Return the translation catalogs for our dependencies.

    Some strings we use come from external software (e.g. language and
    country names, mimetype descriptions, etc.) and their translations
    are thus provided by these packages' catalogs. This function has to
    return the gettext.*Translations classes that translate a string
    according to these message catalogs.

    lang (string): the language we want translations for

    return ([gettext.NullTranslations]): the translation catalogs

    """
    iso_639_locale = gettext.translation(
        "iso_639",
        os.path.join(config.iso_codes_prefix, "share", "locale"),
        [lang],
        fallback=True)
    iso_3166_locale = gettext.translation(
        "iso_3166",
        os.path.join(config.iso_codes_prefix, "share", "locale"),
        [lang],
        fallback=True)
    shared_mime_info_locale = gettext.translation(
        "shared-mime-info",
        os.path.join(config.shared_mime_info_prefix, "share", "locale"),
        [lang],
        fallback=True)

    return [iso_639_locale, iso_3166_locale, shared_mime_info_locale]


class Translation(object):
    """A shim that bundles all sources of translations for a language

    This class is a thin wrapper that collects all message catalogs and
    other pieces of information about a locale and centralizes access
    to them providing a more object-oriented interface.

    """

    def __init__(self, lang_code, mofile=None):
        self.locale = babel.core.Locale.parse(lang_code)
        if mofile is not None:
            self.translation = babel.support.Translations(mofile, domain="cms")
        else:
            self.translation = babel.support.NullTranslations()
        for sys_translation in get_system_translations(lang_code):
            self.translation.add_fallback(sys_translation)

    @property
    def identifier(self):
        return babel.core.get_locale_identifier(
            (self.locale.language, self.locale.territory,
             self.locale.script, self.locale.variant))

    @property
    def name(self):
        return self.locale.display_name

    def gettext(self, msgid):
        if six.PY3:
            return self.translation.gettext(msgid)
        else:
            return self.translation.ugettext(msgid)

    def ngettext(self, msgid1, msgid2, n):
        if six.PY3:
            return self.translation.ngettext(msgid1, msgid2, n)
        else:
            return self.translation.ungettext(msgid1, msgid2, n)


DEFAULT_TRANSLATION = Translation("en")


def get_translations():
    """Return the translations for all the languages we support.

    Search for the message catalogs that were installed and load them.

    return ({string: Translation}): for each language its message
        catalog

    """
    result = {"en": DEFAULT_TRANSLATION}

    for lang_code in sorted(pkg_resources.resource_listdir("cms.locale", "")):
        mofile_path = os.path.join(lang_code, "LC_MESSAGES", "cms.mo")
        if pkg_resources.resource_exists("cms.locale", mofile_path):
            with pkg_resources.resource_stream("cms.locale", mofile_path) as f:
                t = Translation(lang_code, f)
                logger.info("Found translation %s", t.identifier)
                result[t.identifier] = t

    return result


def filter_language_codes(lang_codes, prefix_filter):
    """Keep only codes that begin with one of the given prefixes.

    lang_codes ([string]): list of language codes
    prefix_filter ([string]): whitelist of prefix

    return ([string]): the codes that match one of the prefixes

    """
    # TODO Be more fussy with prefix checking: validate strings
    # (match with "[A-Za-z]+(_[A-Za-z]+)*") and verify that the
    # prefix is on the underscores.
    useless = [prefix for prefix in prefix_filter
               if all(not lang_code.startswith(prefix)
                      for lang_code in lang_codes)]
    if useless:
        logger.warning("The following allowed localizations don't match any "
                       "installed one: %s", ",".join(useless))

    # We just check if a prefix of each language is allowed
    # because this way one can just type "en" to include also
    # "en_US" (and similar cases with other languages). It's
    # the same approach promoted by HTTP in its Accept header
    # parsing rules.
    # TODO Be more fussy with prefix checking: validate strings
    # (match with "[A-Za-z]+(_[A-Za-z]+)*") and verify that the
    # prefix is on the underscores.
    # It needs to maintain order of allowed_localizations(prefix_filter)
    lang_codes = [lang_code for prefix in prefix_filter
                  for lang_code in lang_codes
                  if lang_code.startswith(prefix)]

    if not lang_codes:
        logger.warning("No allowed localization matches any installed one."
                       "Resorting to en.")
        lang_codes = ["en"]

    return lang_codes


class Formatter(string.Formatter):
    """Locale-aware string formatter class.

    Currently it handles locale-specific decimal marks in decimal numbers.

    """
    def __init__(self, _):
        """Initializer.

        _ (function): translation function.

        """
        # translators: decimal mark in decimal numbers (e.g., in "3.14")
        self.decimal_mark = _(".")

    def format_field(self, value, format_spec):
        """Customized format_field() override."""
        res = super(Formatter, self).format_field(value, format_spec)
        if isinstance(value, float):
            return res.replace(".", self.decimal_mark)
        else:
            return res


def locale_format(_, fmt, *args, **kwargs):
    """Locale-aware format function. See the Formatter class
    for more information.

    _ (function): translation function.
    fmt (string): format string.

    """
    return Formatter(_).format(fmt, *args, **kwargs)
