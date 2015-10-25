#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
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
from __future__ import print_function
from __future__ import unicode_literals

import pkg_resources
import gettext
import io
import logging
import os

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


def get_translations():
    """Return the translations for all the languages we support.

    Search for the message catalogs that were installed and load them.

    return ({string: gettext.NullTranslations}): for each language its
        message catalog

    """
    locale_dir = None
    result = {"en": gettext.NullTranslations()}

    locale_dir = pkg_resources.resource_filename("cms.locale", "")
    for lang_code in os.listdir(locale_dir):
        if os.path.isdir(os.path.join(locale_dir, lang_code)):
            mo_file_path = os.path.join(locale_dir, lang_code,
                    "LC_MESSAGES", "cms.mo")
            if os.path.exists(mo_file_path):
                with io.open(mo_file_path, "rb") as mo_file:
                    result[lang_code] = gettext.GNUTranslations(mo_file)

    for lang_code, trans in result.iteritems():
        for sys_trans in get_system_translations(lang_code):
            trans.add_fallback(sys_trans)

    return result


def wrap_translations_for_tornado(trans):
    """Make a message catalog compatible with Tornado.

    Add the necessary methods to give a gettext.*Translations object
    the interface of a tornado.locale.GettextLocale object.

    trans (gettext.NullTranslations): a message catalog

    return (object): a message catalog disguised as a
        tornado.locale.GettextLocale

    """
    # Add translate method
    def translate(message, plural_message=None, count=None):
        if plural_message is not None:
            assert count is not None
            return trans.ungettext(message, plural_message, count)
        else:
            return trans.ugettext(message)
    trans.translate = translate

    # Add a "dummy" pgettext method (that ignores the context)
    # (Since v4.2)
    def pgettext(_, message, plural_message=None, count=None):
        return translate(message, plural_message, count)
    trans.pgettext = pgettext

    return trans


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
    lang_codes = [lang_code for lang_code in lang_codes
                  if any(lang_code.startswith(prefix)
                         for prefix in prefix_filter)]

    if not lang_codes:
        logger.warning("No allowed localization matches any installed one."
                       "Resorting to en.")
        lang_codes = ["en"]

    return lang_codes
