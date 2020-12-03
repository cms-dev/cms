#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Base handler classes for CWS.

"""

import logging
import traceback

try:
    import tornado4.web as tornado_web
except ImportError:
    import tornado.web as tornado_web
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from cms.db import Contest
from cms.locale import DEFAULT_TRANSLATION, choose_language_code
from cms.server import CommonRequestHandler
from cmscommon.datetime import utc as utc_tzinfo


logger = logging.getLogger(__name__)


class BaseHandler(CommonRequestHandler):
    """Base RequestHandler for this application.

    This will also handle the contest list on the homepage.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The list of interface translations the user can choose from.
        self.available_translations = self.service.translations
        # The translation that best matches the user's system settings
        # (as reflected by the browser in the HTTP request's
        # Accept-Language header).
        self.automatic_translation = DEFAULT_TRANSLATION
        # The translation that the user specifically manually picked.
        self.cookie_translation = None
        # The translation that we are going to use.
        self.translation = DEFAULT_TRANSLATION
        self._ = self.translation.gettext
        self.n_ = self.translation.ngettext

    def render(self, template_name, **params):
        t = self.service.jinja2_environment.get_template(template_name)
        for chunk in t.generate(**params):
            self.write(chunk)

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        super().prepare()
        self.setup_locale()

    def setup_locale(self):
        lang_codes = list(self.available_translations.keys())

        browser_langs = parse_accept_header(
            self.request.headers.get("Accept-Language", ""),
            LanguageAccept).values()
        automatic_lang = choose_language_code(browser_langs, lang_codes)
        if automatic_lang is None:
            automatic_lang = lang_codes[0]
        self.automatic_translation = \
            self.available_translations[automatic_lang]

        cookie_lang = self.get_cookie("language", None)
        if cookie_lang is not None:
            chosen_lang = \
                choose_language_code([cookie_lang, automatic_lang], lang_codes)
            if chosen_lang == cookie_lang:
                self.cookie_translation = \
                    self.available_translations[cookie_lang]
        else:
            chosen_lang = automatic_lang
        self.translation = self.available_translations[chosen_lang]

        self._ = self.translation.gettext
        self.n_ = self.translation.ngettext

        self.set_header("Content-Language", chosen_lang)

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        ret = {}
        ret["now"] = self.timestamp
        ret["utc"] = utc_tzinfo
        ret["url"] = self.url

        ret["available_translations"] = self.available_translations

        ret["cookie_translation"] = self.cookie_translation
        ret["automatic_translation"] = self.automatic_translation

        ret["translation"] = self.translation
        ret["gettext"] = self._
        ret["ngettext"] = self.n_

        # FIXME The handler provides too broad an access: its usage
        # should be extracted into with narrower-scoped parameters.
        ret["handler"] = self

        ret["xsrf_form_html"] = self.xsrf_form_html()

        return ret

    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs and \
                kwargs["exc_info"][0] != tornado_web.HTTPError:
            exc_info = kwargs["exc_info"]
            logger.error(
                "Uncaught exception (%r) while processing a request: %s",
                exc_info[1], ''.join(traceback.format_exception(*exc_info)))

        # We assume that if r_params is defined then we have at least
        # the data we need to display a basic template with the error
        # information. If r_params is not defined (i.e. something went
        # *really* bad) we simply return a basic textual error notice.
        if self.r_params is not None:
            self.render("error.html", status_code=status_code, **self.r_params)
        else:
            self.write("A critical error has occurred :-(")
            self.finish()

    def is_multi_contest(self):
        """Return whether CWS serves all contests."""
        return self.service.contest_id is None


class ContestListHandler(BaseHandler):
    def get(self):
        self.r_params = self.render_params()
        # We need this to be computed for each request because we want to be
        # able to import new contests without having to restart CWS.
        contest_list = dict()
        for contest in self.sql_session.query(Contest).all():
            contest_list[contest.name] = contest
        self.render("contest_list.html", contest_list=contest_list,
                    **self.r_params)
