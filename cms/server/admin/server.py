#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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

"""Web server for administration of contests.

"""

import logging

from sqlalchemy import func, not_

from cms import config, ServiceCoord, get_service_shards
from cms.db import SessionGen, Dataset, Submission, SubmissionResult, Task
from cms.io import WebService, rpc_method
from cms.service import EvaluationService
from cmscommon.binary import hex_to_bin
from .authentication import AWSAuthMiddleware
from .handlers import HANDLERS
from .jinja2_toolbox import AWS_ENVIRONMENT
from .rpc_authorization import rpc_authorization_checker


logger = logging.getLogger(__name__)


class AdminWebServer(WebService):
    """Service that runs the web server serving the managers.

    """
    def __init__(self, shard):
        parameters = {
            "static_files": [("cms.server", "static"),
                             ("cms.server.admin", "static")],
            "cookie_secret": hex_to_bin(config.secret_key),
            "debug": config.tornado_debug,
            "num_proxies_used": config.admin_num_proxies_used,
            "auth_middleware": AWSAuthMiddleware,
            "rpc_enabled": True,
            "rpc_auth": self.is_rpc_authorized,
            "xsrf_cookies": True,
        }
        super().__init__(
            config.admin_listen_port,
            HANDLERS,
            parameters,
            shard=shard,
            listen_address=config.admin_listen_address)

        self.jinja2_environment = AWS_ENVIRONMENT

        # A list of pending notifications.
        self.notifications = []

        self.admin_web_server = self.connect_to(
            ServiceCoord("AdminWebServer", 0))
        self.evaluation_service = self.connect_to(
            ServiceCoord("EvaluationService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        ranking_enabled = len(config.rankings) > 0
        self.proxy_service = self.connect_to(
            ServiceCoord("ProxyService", 0),
            must_be_present=ranking_enabled)

        self.resource_services = []
        for i in range(get_service_shards("ResourceService")):
            self.resource_services.append(self.connect_to(
                ServiceCoord("ResourceService", i)))
        self.logservice = self.connect_to(ServiceCoord("LogService", 0))

    def is_rpc_authorized(self, service, shard, method):
        return rpc_authorization_checker(self.auth_handler.admin_id,
                                         service, shard, method)

    def add_notification(self, timestamp, subject, text):
        """Store a new notification to send at the first
        opportunity (i.e., at the first request for db notifications).

        timestamp (datetime): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.

        """
        self.notifications.append((timestamp, subject, text))

    @staticmethod
    @rpc_method
    def submissions_status(contest_id):
        """Returns a dictionary of statistics about the number of
        submissions on a specific status in the given contest.

        There are six statuses: evaluated, compilation failed,
        evaluating, compiling, maximum number of attempts of
        compilations reached, the same for evaluations. The last two
        should not happen and require a check from the admin.

        The status of a submission is checked on its result for the
        active dataset of its task.

        contest_id (int|None): counts are restricted to this contest,
            or None for no restrictions.

        return (dict): statistics on the submissions.

        """
        # TODO: at the moment this counts all submission results for
        # the live datasets. It is interesting to show also numbers
        # for the datasets with autojudge, and for all datasets.
        stats = {}
        with SessionGen() as session:
            base_query = session\
                .query(func.count(SubmissionResult.submission_id))\
                .select_from(SubmissionResult)\
                .join(Dataset)\
                .join(Task, Dataset.task_id == Task.id)\
                .filter(Task.active_dataset_id == SubmissionResult.dataset_id)
            if contest_id is not None:
                base_query = base_query\
                    .filter(Task.contest_id == contest_id)

            compiled = base_query.filter(SubmissionResult.filter_compiled())
            evaluated = compiled.filter(SubmissionResult.filter_evaluated())
            not_compiled = base_query.filter(
                not_(SubmissionResult.filter_compiled()))
            not_evaluated = compiled.filter(
                SubmissionResult.filter_compilation_succeeded(),
                not_(SubmissionResult.filter_evaluated()))

            queries = {}
            queries['compiling'] = not_compiled.filter(
                SubmissionResult.compilation_tries <
                EvaluationService.EvaluationService.MAX_COMPILATION_TRIES)
            queries['max_compilations'] = not_compiled.filter(
                SubmissionResult.compilation_tries >=
                EvaluationService.EvaluationService.MAX_COMPILATION_TRIES)
            queries['compilation_fail'] = base_query.filter(
                SubmissionResult.filter_compilation_failed())
            queries['evaluating'] = not_evaluated.filter(
                SubmissionResult.evaluation_tries <
                EvaluationService.EvaluationService.MAX_EVALUATION_TRIES)
            queries['max_evaluations'] = not_evaluated.filter(
                SubmissionResult.evaluation_tries >=
                EvaluationService.EvaluationService.MAX_EVALUATION_TRIES)
            queries['scoring'] = evaluated.filter(
                not_(SubmissionResult.filter_scored()))
            queries['scored'] = evaluated.filter(
                SubmissionResult.filter_scored())

            total_query = session\
                .query(func.count(Submission.id))\
                .select_from(Submission)\
                .join(Task, Submission.task_id == Task.id)
            if contest_id is not None:
                total_query = total_query\
                    .filter(Task.contest_id == contest_id)
            queries['total'] = total_query

            stats = {}
            keys = list(queries.keys())
            results = queries[keys[0]].union_all(
                *(queries[key] for key in keys[1:])).all()

        for i, k in enumerate(keys):
            stats[k] = results[i][0]
        stats['compiling'] += 2 * stats['total'] - sum(stats.values())

        return stats
