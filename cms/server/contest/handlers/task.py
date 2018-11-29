#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2018 William Di Luigi <williamdiluigi@gmail.com>
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

"""Task-related handlers for CWS.

"""

import logging

import tornado.web

from cms import STATEMENT_TYPE_HTML, STATEMENT_TYPE_MD, STATEMENT_TYPE_PDF
from cms.server import multi_contest
from cmscommon.mimetypes import get_type_for_file_name
from .contest import ContestHandler, FileHandler
from ..phase_management import actual_phase_required


logger = logging.getLogger(__name__)


class TaskDescriptionHandler(ContestHandler):
    """Shows the data of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name):
        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        main_languages = set()
        other_languages = set()
        statements = dict()
        for statement in task.statements.values():
            if statement.language in self.r_params["participation"]\
                                         .user.preferred_languages \
                    or statement.language in task.primary_statements:
                main_languages.add(statement.language)
            else:
                other_languages.add(statement.language)

            if statement.language not in statements:
                statements[statement.language] = []

            statements[statement.language].append(statement.statement_type)

        main_languages = list(sorted(main_languages))
        other_languages = list(sorted(other_languages))

        self.render("task_description.html", task=task,
                    main_languages=main_languages,
                    other_languages=other_languages,
                    statements=statements, **self.r_params)


class TaskStatementViewHandler(FileHandler):
    """Shows the statement file of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name, lang_code, statement_type):
        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        if (lang_code, statement_type) not in task.statements:
            raise tornado.web.HTTPError(404)

        statement = task.statements[(lang_code, statement_type)].digest
        self.sql_session.close()

        if statement_type == STATEMENT_TYPE_PDF:
            if len(lang_code) > 0:
                filename = "%s (%s).pdf" % (task.name, lang_code)
            else:
                filename = "%s.pdf" % task.name

            self.fetch(statement, "application/pdf", filename)
        elif statement_type == STATEMENT_TYPE_HTML:
            self.fetch(statement, "text/html", "statement.html")
        elif statement_type == STATEMENT_TYPE_MD:
            self.fetch(statement, "text/html", "statement.md")
        else:
            raise tornado.web.HTTPError(404)


class TaskAttachmentViewHandler(FileHandler):
    """Shows an attachment file of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name, filename):
        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        if filename not in task.attachments:
            raise tornado.web.HTTPError(404)

        attachment = task.attachments[filename].digest
        self.sql_session.close()

        mimetype = get_type_for_file_name(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(attachment, mimetype, filename)


class TaskAssetViewHandler(FileHandler):
    """Return an asset file of a task statement in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name, filename):
        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        if filename not in task.statement_assets:
            raise tornado.web.HTTPError(404)

        asset = task.statement_assets[filename].digest
        self.sql_session.close()

        mimetype = get_type_for_file_name(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(asset, mimetype, filename)
