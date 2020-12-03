#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
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

"""Communication-related handlers for CWS.

"""

import logging

try:
    import tornado4.web as tornado_web
except ImportError:
    import tornado.web as tornado_web

from cms.server import multi_contest
from cms.server.contest.communication import accept_question, \
    UnacceptableQuestion, QuestionsNotAllowed
from .contest import ContestHandler


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class CommunicationHandler(ContestHandler):
    """Displays the private conversations between the logged in user
    and the contest managers..

    """
    @tornado_web.authenticated
    @multi_contest
    def get(self):
        self.render("communication.html", **self.r_params)


class QuestionHandler(ContestHandler):
    """Called when the user submits a question.

    """
    @tornado_web.authenticated
    @multi_contest
    def post(self):
        try:
            accept_question(self.sql_session, self.current_user, self.timestamp,
                            self.get_argument("question_subject", ""),
                            self.get_argument("question_text", ""))
            self.sql_session.commit()
        except QuestionsNotAllowed:
            raise tornado_web.HTTPError(404)
        except UnacceptableQuestion as e:
            self.notify_error(e.subject, e.text, e.text_params)
        else:
            self.notify_success(N_("Question received"),
                                N_("Your question has been received, you "
                                   "will be notified when it is answered."))

        self.redirect(self.contest_url("communication"))
