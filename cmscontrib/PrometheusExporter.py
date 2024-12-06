#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2020 Edoardo Morassutto <edoardo.morassutto@gmail.com>
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

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey

from cms.db.contest import Contest

gevent.monkey.patch_all()  # noqa

import argparse
import logging

from prometheus_client import start_http_server
from prometheus_client.core import REGISTRY, CounterMetricFamily, GaugeMetricFamily
from sqlalchemy import func, distinct

from cms import ServiceCoord
from cms import config
from cms.db import (
    Announcement,
    Dataset,
    Message,
    Participation,
    Question,
    SessionGen,
    Submission,
    SubmissionResult,
    Task,
)
from cms.io.service import Service
from cms.io.rpc import RPCError
from cms.server.admin.server import AdminWebServer

logger = logging.getLogger(__name__)

class PrometheusExporter(Service):
    def __init__(self, args):
        super().__init__()

        self.host = args.host
        self.port = args.port

        self.export_submissions = not args.no_submissions
        self.export_workers = not args.no_workers
        self.export_queue = not args.no_queue
        self.export_communiactions = not args.no_communications
        self.export_users = not args.no_users
        self.evaluation_service = None

    def run(self):
        REGISTRY.register(self)
        start_http_server(self.port, addr=self.host)
        logger.info("Started at http://%s:%s/metric", self.host, self.port)
        super().run()

    def collect(self):
        with SessionGen() as session:
            if self.export_submissions:
                yield from self._collect_submissions(session)
            if self.export_communiactions:
                yield from self._collect_communications(session)
            if self.export_users:
                yield from self._collect_users(session)

            if self.evaluation_service is None:
                try:
                    self.evaluation_service = self.connect_to(ServiceCoord("EvaluationService", 0))
                except RPCError:
                    pass
            if self.evaluation_service is not None:
                try:
                    if self.export_workers:
                        yield from self._collect_workers()
                    if self.export_queue:
                        yield from self._collect_queue()
                except RPCError:
                    self.evaluation_service = None

            metric = GaugeMetricFamily("cms_es_is_up", "Whether the Evaluation Service is currently up")
            metric.add_metric([], 1 if self.evaluation_service is not None else 0)
            yield metric

    def _collect_submissions(self, session):
        # compiling / max_compilations / compilation_fail / evaluating /
        # max_evaluations / scoring / scored / total
        stats = AdminWebServer.submissions_status(None)
        metric = GaugeMetricFamily(
            "cms_submissions",
            "Number of submissions per category",
            labels=["status"],
        )
        for status, count in stats.items():
            metric.add_metric([status], count)
        yield metric

        metric = CounterMetricFamily(
            "cms_task_submissions",
            "Number of submissions per task",
            labels=["task"],
        )
        data = (
            session.query(Task.name, func.count(SubmissionResult.submission_id))
            .select_from(SubmissionResult)
            .join(Dataset)
            .join(Task, Dataset.task_id == Task.id)
            .filter(Task.active_dataset_id == SubmissionResult.dataset_id)
            .group_by(Task.name)
            .all()
        )
        for task_name, count in data:
            metric.add_metric([task_name], count)
        yield metric

        metric = CounterMetricFamily(
            "cms_submissions_language",
            "Number of submissions per language",
            labels=["language"],
        )
        data = (
            session.query(Submission.language, func.count(Submission.id))
            .select_from(Submission)
            .group_by(Submission.language)
            .all()
        )
        for language, count in data:
            metric.add_metric([language], count)
        yield metric

    def _collect_workers(self):
        status = self.evaluation_service.workers_status().get()
        metric = GaugeMetricFamily(
            "cms_workers",
            "Number of cmsWorker instances",
            labels=["status"],
        )
        metric.add_metric(["total"], len(status))
        metric.add_metric(
            ["connected"], sum(1 for worker in status.values() if worker["connected"])
        )
        metric.add_metric(
            ["working"], sum(1 for worker in status.values() if worker["operations"])
        )
        yield metric

    def _collect_queue(self):
        status = self.evaluation_service.queue_status().get()

        metric = GaugeMetricFamily("cms_queue_length", "Number of entries in the queue")
        metric.add_metric([], len(status))
        yield metric

        metric = GaugeMetricFamily(
            "cms_queue_item_types",
            "Types of items in the queue",
            labels=["type"],
        )
        types = {}
        for item in status:
            typ = item["item"]["type"]
            types.setdefault(typ, 0)
            types[typ] += 1
        for typ, count in types.items():
            metric.add_metric([typ], count)
        yield metric

        metric = GaugeMetricFamily(
            "cms_queue_oldest_job",
            "Timestamp of the oldest job in the queue",
        )
        if status:
            oldest = min(status, key=lambda x: x["timestamp"])
            metric.add_metric([], oldest["timestamp"])
        yield metric

    def _collect_communications(self, session):
        metric = CounterMetricFamily(
            "cms_questions",
            "Number of questions",
            labels=["status"],
        )
        data = session.query(func.count(Question.id)).select_from(Question).all()
        metric.add_metric(["total"], data[0][0])
        data = (
            session.query(func.count(Question.id))
            .select_from(Question)
            .filter(Question.ignored == True)
            .all()
        )
        metric.add_metric(["ignored"], data[0][0])
        data = (
            session.query(func.count(Question.id))
            .select_from(Question)
            .filter(Question.reply_timestamp != None)
            .all()
        )
        metric.add_metric(["answered"], data[0][0])
        yield metric

        metric = CounterMetricFamily("cms_messages", "Number of private messages")
        data = session.query(func.count(Message.id)).select_from(Message).all()
        metric.add_metric([], data[0][0])
        yield metric

        metric = CounterMetricFamily("cms_announcements", "Number of announcements")
        data = (
            session.query(func.count(Announcement.id)).select_from(Announcement).all()
        )
        metric.add_metric([], data[0][0])
        yield metric

    def _collect_users(self, session):
        metric = GaugeMetricFamily(
            "cms_participations",
            "Number of participations grouped by category and contest",
            labels=["category", "contest"],
        )
        data = (
            session.query(Participation.contest_id, func.count(Participation.id))
            .select_from(Participation)
            .group_by(Participation.contest_id)
            .all()
        )
        for contest_id, count in data:
            metric.add_metric(["total", str(contest_id)], count)
        data = (
            session.query(Participation.contest_id, func.count(Participation.id))
            .select_from(Participation)
            .filter(Participation.hidden == True)
            .group_by(Participation.contest_id)
            .all()
        )
        for contest_id, count in data:
            metric.add_metric(["hidden", str(contest_id)], count)
        data = (
            session.query(Participation.contest_id, func.count(Participation.id))
            .select_from(Participation)
            .filter(Participation.unrestricted == True)
            .group_by(Participation.contest_id)
            .all()
        )
        for contest_id, count in data:
            metric.add_metric(["unrestricted", str(contest_id)], count)
        data = (
            session.query(Participation.contest_id, func.count(Participation.id))
            .select_from(Participation)
            .filter(Participation.starting_time != None)
            .group_by(Participation.contest_id)
            .all()
        )
        for contest_id, count in data:
            metric.add_metric(["started", str(contest_id)], count)
        data = (
            session.query(
                Participation.contest_id, func.count(distinct(Participation.id))
            )
            .select_from(Participation)
            .join(Submission)
            .group_by(Participation.contest_id)
            .all()
        )
        for contest_id, count in data:
            metric.add_metric(["submitted", str(contest_id)], count)
        data = (
            session.query(
                Participation.contest_id, func.count(distinct(Participation.id))
            )
            .select_from(Participation)
            .join(Submission)
            .join(SubmissionResult)
            .join(Dataset)
            .join(Task, Dataset.task_id == Task.id)
            .filter(Task.active_dataset_id == SubmissionResult.dataset_id)
            .filter(SubmissionResult.score > 0)
            .group_by(Participation.contest_id)
            .all()
        )
        for contest_id, count in data:
            metric.add_metric(["non_zero", str(contest_id)], count)
        yield metric


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(description="Prometheus exporter.")
    parser.add_argument(
        "--host",
        help="IP address to bind to",
        default=config.prometheus_listen_address,
    )
    parser.add_argument(
        "--port",
        help="Port to use",
        default=config.prometheus_listen_port,
        type=int,
    )
    parser.add_argument(
        "--no-submissions",
        help="Do not export submissions metrics",
        action="store_true",
    )
    parser.add_argument(
        "--no-workers",
        help="Do not export workers metrics",
        action="store_true",
    )
    parser.add_argument(
        "--no-queue",
        help="Do not export queue metrics",
        action="store_true",
    )
    parser.add_argument(
        "--no-communications",
        help="Do not export communications metrics",
        action="store_true",
    )
    parser.add_argument(
        "--no-users",
        help="Do not export users metrics",
        action="store_true",
    )

    # unsed, but passed by ResourceService
    parser.add_argument("shard", default="", help="unused")
    parser.add_argument("-c", "--contest", default="", help="unused")

    args = parser.parse_args()

    service = PrometheusExporter(args)
    service.run()


if __name__ == "__main__":
    main()
