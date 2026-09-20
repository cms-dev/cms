#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
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

"""Admin handler for Training Day Archive.

This module contains the handler for archiving training days.
Analytics handlers (attendance, ranking) are in training_analytics.py.
Excel export handlers are in excel.py.
"""

import ipaddress
import logging
import typing
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlparse

import tornado.web

from cms.db import (
    Contest,
    TrainingProgram,
    Submission,
    Student,
    StudentTask,
    Task,
    TrainingDay,
    TrainingDayGroup,
    Participation,
    ArchivedAttendance,
    ArchivedStudentRanking,
    ScoreHistory,
    DelayRequest,
)
from cms.db.training_day import get_managing_participation
from cms.grading.scorecache import get_cached_score_entry
from cms.server.util import can_access_task, check_training_day_eligibility
from cms.server.admin.handlers.utils import (
    build_task_data_for_archive,
    build_user_to_student_map,
)
from cmscommon.datetime import make_datetime

from .base import BaseHandler, require_permission
from .contestdelayrequest import compute_participation_status

from .training_analytics import (
    TrainingProgramFilterMixin,
    get_attendance_view_data,
    get_ranking_view_data,
    FilterContext,
    TrainingProgramAttendanceHandler,
    TrainingProgramCombinedRankingHandler,
    TrainingProgramCombinedRankingHistoryHandler,
    TrainingProgramCombinedRankingDetailHandler,
    UpdateAttendanceHandler,
)
from .excel import (
    ExportAnalysedRankingHandler,
    ExportArchivedTaskScoresHandler,
    ExportAttendanceHandler,
    ExportCombinedRankingHandler,
    build_filename,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ArchiveTrainingDayHandler",
    "ExportAnalysedRankingHandler",
    "ExportArchivedTaskScoresHandler",
    "ExportAttendanceHandler",
    "ExportCombinedRankingHandler",
    "TrainingProgramAttendanceHandler",
    "TrainingProgramCombinedRankingDetailHandler",
    "TrainingProgramCombinedRankingHandler",
    "TrainingProgramCombinedRankingHistoryHandler",
    "TrainingProgramFilterMixin",
    "UpdateAttendanceHandler",
    "compute_archive_modal_data",
    "get_attendance_view_data",
    "get_ranking_view_data",
    "FilterContext",
    "build_filename",
]


def compute_archive_modal_data(
    sql_session, training_day: "TrainingDay", contest: "Contest", timestamp
) -> dict:
    """Compute data needed for the archive training day modal.

    Returns a dict with 'network_hierarchy' and 'users_not_finished' keys.
    This is used by pages that include the modal_archive_training_day.html
    fragment directly (training days page, delays page).
    """
    ip_counts: dict[str, int] = {}
    for participation in contest.participations:
        if participation.hidden:
            continue
        ips = ArchiveTrainingDayHandler._parse_ip_addresses(
            participation.starting_ip_addresses
        )
        for ip in ips:
            ip_counts[ip] = ip_counts.get(ip, 0) + 1

    network_hierarchy = ArchiveTrainingDayHandler._build_network_hierarchy(
        ip_counts
    )

    users_not_finished = []
    training_program = training_day.training_program
    user_to_student = build_user_to_student_map(training_program)

    for participation in contest.participations:
        if participation.hidden:
            continue
        student = user_to_student.get(participation.user_id)
        if student is None:
            continue
        is_eligible, main_group, _ = check_training_day_eligibility(
            sql_session, participation, training_day, student=student
        )
        if not is_eligible:
            continue
        main_group_start = main_group.start_time if main_group else None
        main_group_end = main_group.end_time if main_group else None
        status_class, status_label = compute_participation_status(
            contest, participation, timestamp,
            main_group_start, main_group_end
        )
        if status_class not in ('finished', 'missed'):
            users_not_finished.append({
                'participation': participation,
                'status_class': status_class,
                'status_label': status_label,
            })

    return {
        'network_hierarchy': network_hierarchy,
        'users_not_finished': users_not_finished,
    }


class ArchiveTrainingDayHandler(BaseHandler):
    """Archive a training day, extracting attendance and ranking data."""

    @staticmethod
    def _parse_ip_addresses(ip_string: str | None) -> list[str]:
        """Parse a comma-separated string of IP addresses."""
        if not ip_string:
            return []
        return [ip.strip() for ip in ip_string.split(",") if ip.strip()]

    @staticmethod
    def _get_network_prefix(ip_str: str) -> str:
        """Get the network prefix for an IP address.

        Returns the network string (e.g. "192.168.1.0/24" for IPv4 or
        "2001:db8::/64" for IPv6) or the original string under an "Other"
        key if parsing fails.
        """
        try:
            addr = ipaddress.ip_address(ip_str)
            # Use /24 for IPv4 (standard LAN subnet) and /64 for IPv6 (standard subnet)
            prefix = "/24" if addr.version == 4 else "/64"
            network = ipaddress.ip_network(f"{addr}{prefix}", strict=False)
            return str(network)
        except ValueError:
            return "Other"

    @staticmethod
    def _build_network_hierarchy(
        ip_counts: dict[str, int],
    ) -> list[dict[str, object]]:
        """Group IPs by /24 network and return networks with multiple entries.

        Returns a sorted list of dicts, each with:
          - "network": the network string (e.g. "192.168.1.0/24")
          - "total_count": sum of student counts across all IPs in the network
          - "ips": list of {"ip": str, "count": int} sorted by count desc
        Only networks whose total student count > 1 are included.
        """
        networks: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for ip, count in ip_counts.items():
            prefix = ArchiveTrainingDayHandler._get_network_prefix(ip)
            networks[prefix].append((ip, count))

        result: list[dict[str, object]] = []
        for network, ip_list in networks.items():
            total = sum(c for _, c in ip_list)
            if total <= 1:
                continue
            ip_list.sort(key=lambda x: x[1], reverse=True)
            result.append({
                "network": network,
                "total_count": total,
                "ips": [{"ip": ip, "count": count} for ip, count in ip_list],
            })
        result.sort(key=lambda x: x["total_count"], reverse=True)
        return result

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, training_program_id: str, training_day_id: str):
        """Perform the archiving operation."""
        fallback_page = self.url(
            "training_program", training_program_id, "training_days"
        )

        training_program = self.safe_get_item(TrainingProgram, training_program_id)
        training_day = self.safe_get_item(TrainingDay, training_day_id)

        if training_day.training_program_id != training_program.id:
            raise tornado.web.HTTPError(404, "Training day not in this program")

        if training_day.contest is None:
            self.service.add_notification(
                make_datetime(), "Error", "Training day is already archived"
            )
            self.redirect(fallback_page)
            return

        contest = training_day.contest

        # Get selected class IPs from form
        class_ips = set(self.get_arguments("class_ips"))

        try:
            # Save name, description, and start_time from contest before archiving
            training_day.name = contest.name
            training_day.description = contest.description
            training_day.start_time = contest.start

            # Calculate and store the training day duration
            # Use max duration among main groups (if any), or training day duration
            training_day.duration = self._calculate_training_day_duration(
                training_day, contest
            )

            # Archive attendance data for each student
            self._archive_attendance_data(training_day, contest, class_ips)

            # Archive ranking data for each student
            self._archive_ranking_data(training_day, contest)

            # Reset submission limits on all tasks assigned to this training day
            for task in training_day.tasks:
                task.max_submission_number = None
                task.min_submission_interval = None

            # Delete the contest (this will cascade delete participations)
            self.sql_session.delete(contest)

        except Exception as error:
            self.sql_session.rollback()
            self.service.add_notification(
                make_datetime(), "Archive failed", repr(error)
            )
            self.redirect(fallback_page)
            return

        if self.try_commit():
            self.service.add_notification(
                make_datetime(),
                "Training day archived",
                f"Training day '{training_day.name}' has been archived successfully"
            )

        self.redirect(fallback_page)

    def _calculate_training_day_duration(
        self,
        training_day: TrainingDay,
        contest: Contest
    ) -> timedelta | None:
        """Calculate the training day duration for archiving.

        Returns the max training duration among main groups (if any),
        or the training day duration (if no main groups).

        training_day: the training day being archived.
        contest: the contest associated with the training day.

        return: the duration as a timedelta, or None if not calculable.
        """
        # Check if there are main groups with custom timing
        main_groups = training_day.groups
        # Calculate max duration among main groups
        max_duration: timedelta | None = None
        for group in main_groups:
            if group.start_time is not None and group.end_time is not None:
                group_duration = group.end_time - group.start_time
                if max_duration is None or group_duration > max_duration:
                    max_duration = group_duration
        if max_duration is not None:
            return max_duration

        # Fall back to training day (contest) duration
        return contest.stop - contest.start

    def _iterate_eligible_students(
        self, training_day: TrainingDay, contest: Contest
    ) -> typing.Iterator[tuple[Student, Participation, TrainingDayGroup | None]]:
        """Iterate over all non-hidden students eligible for the training day.

        Yields (student, participation, main_group) tuples for all students who:
        1. Have a user associated with a participation in the contest
        2. Are not hidden
        3. Are eligible for the training day (check_training_day_eligibility)
        """
        training_program = training_day.training_program
        user_to_student = build_user_to_student_map(training_program)

        for participation in contest.participations:
            if participation.hidden:
                continue

            # Find the student for this user in the training program
            # Note: Student.participation_id points to the managing contest participation,
            # not the training day participation, so we need to look up by user_id
            student = user_to_student.get(participation.user_id)

            if student is None:
                logger.warning(
                    "Participation %s (user %s) has no corresponding student record "
                    "in training program %s",
                    participation.id,
                    participation.user_id,
                    training_program.id,
                )
                continue

            # Skip ineligible students (not in any main group)
            # These students were never supposed to participate in this training day
            is_eligible, main_group, _ = check_training_day_eligibility(
                self.sql_session, participation, training_day, student=student
            )
            if not is_eligible:
                continue

            yield student, participation, main_group

    def _archive_attendance_data(
        self, training_day: TrainingDay, contest: Contest, class_ips: set[str]
    ) -> None:
        """Extract and store attendance data for all students."""
        for student, participation, _ in self._iterate_eligible_students(
            training_day, contest
        ):
            # Determine status
            if participation.starting_time is None:
                status = "missed"
                location = None
            else:
                status = "participated"
                # Determine location based on starting IPs
                # If no class IPs were selected, everyone who participated is considered "home"
                # Also if there are no IPs recorded, assume "home"
                location = "home"
                ips = self._parse_ip_addresses(participation.starting_ip_addresses)
                if class_ips and ips:
                    has_class_ip = any(ip in class_ips for ip in ips)
                    has_home_ip = any(ip not in class_ips for ip in ips)
                    if has_class_ip and has_home_ip:
                        location = "both"
                    elif has_class_ip:
                        location = "class"

            # Get delay time
            delay_time = participation.delay_time

            # Concatenate delay reasons from all delay requests
            delay_requests = (
                self.sql_session.query(DelayRequest)
                .filter(DelayRequest.participation_id == participation.id)
                .order_by(DelayRequest.request_timestamp)
                .all()
            )
            delay_reasons = None
            if delay_requests:
                reasons = [dr.reason for dr in delay_requests if dr.reason]
                if reasons:
                    delay_reasons = "; ".join(reasons)

            # Create archived attendance record
            archived_attendance = ArchivedAttendance(
                status=status,
                location=location,
                delay_time=delay_time,
                delay_reasons=delay_reasons,
            )
            archived_attendance.training_day_id = training_day.id
            archived_attendance.student_id = student.id
            self.sql_session.add(archived_attendance)

    def _get_visible_tasks(
        self,
        training_day: TrainingDay,
        participation: Participation,
        training_day_tasks: list[Task],
    ) -> list[Task]:
        """Determine which tasks should be visible to this student."""
        visible_tasks: list[Task] = []
        for task in training_day_tasks:
            if can_access_task(self.sql_session, task, participation, training_day):
                visible_tasks.append(task)
        return visible_tasks

    def _ensure_student_tasks(
        self,
        student: Student,
        visible_tasks: list[Task],
        training_day: TrainingDay,
    ) -> None:
        """Add visible tasks to student's StudentTask records if not already present."""
        existing_task_ids = {st.task_id for st in student.student_tasks}
        for task in visible_tasks:
            if task.id not in existing_task_ids:
                student_task = StudentTask(assigned_at=make_datetime())
                student_task.student_id = student.id
                student_task.task_id = task.id
                student_task.source_training_day_id = training_day.id
                self.sql_session.add(student_task)

    def _collect_task_scores_and_submissions(
        self,
        training_day: TrainingDay,
        participation: Participation,
        managing_participation: Participation,
        visible_tasks: list[Task],
        student_missed: bool,
    ) -> tuple[dict[str, float], dict[str, list[dict]]]:
        """Collect scores and submissions for visible tasks."""
        task_scores: dict[str, float] = {}
        submissions: dict[str, list[dict]] = {}

        for task in visible_tasks:
            task_id = task.id

            if student_missed:
                # Student missed the training - set score to 0
                task_scores[str(task_id)] = 0.0
            else:
                # Get score from the training day participation (for cache lookup)
                cache_entry = get_cached_score_entry(
                    self.sql_session, participation, task
                )
                task_scores[str(task_id)] = cache_entry.score

            # Get official submissions for this task from the managing participation
            task_submissions = (
                self.sql_session.query(Submission)
                .filter(Submission.participation_id == managing_participation.id)
                .filter(Submission.task_id == task_id)
                .filter(Submission.training_day_id == training_day.id)
                .filter(Submission.official.is_(True))
                .order_by(Submission.timestamp)
                .all()
            )

            # If student missed but has submissions, this is an error
            if student_missed and task_submissions:
                raise ValueError(
                    f"User {participation.user.username} (id={participation.user_id}) "
                    f"has no starting_time but has {len(task_submissions)} submission(s) "
                    f"for task '{task.name}' in training day '{training_day.name}'"
                )

            submissions[str(task_id)] = []
            for sub in task_submissions:
                result = sub.get_result()
                if result is None or not result.scored():
                    continue

                if sub.timestamp is not None:
                    time_offset = int(
                        (sub.timestamp - participation.starting_time).total_seconds()
                    )
                else:
                    time_offset = 0

                submissions[str(task_id)].append(
                    {
                        "task": str(task_id),
                        "time": time_offset,
                        "score": result.score,
                        "token": sub.tokened(),
                        "extra": result.ranking_score_details or [],
                    }
                )
        return task_scores, submissions

    def _collect_score_history(
        self,
        training_day: TrainingDay,
        participation: Participation,
        training_day_task_ids: set[int],
        student_missed: bool,
    ) -> list[list]:
        """Collect score history for the student."""
        history: list[list] = []
        score_histories = (
            self.sql_session.query(ScoreHistory)
            .filter(ScoreHistory.participation_id == participation.id)
            .filter(ScoreHistory.task_id.in_(training_day_task_ids))
            .order_by(ScoreHistory.timestamp)
            .all()
        )

        # If student missed but has score history, this is an error
        if student_missed and score_histories:
            raise ValueError(
                f"User {participation.user.username} (id={participation.user_id}) "
                f"has no starting_time but has {len(score_histories)} score history "
                f"record(s) in training day '{training_day.name}'"
            )

        for sh in score_histories:
            if sh.timestamp is not None:
                time_offset = (
                    sh.timestamp - participation.starting_time
                ).total_seconds()
            else:
                time_offset = 0
            history.append([participation.user_id, sh.task_id, time_offset, sh.score])
        return history

    def _process_student_ranking(
        self,
        training_day: TrainingDay,
        student: Student,
        participation: Participation,
        training_day_tasks: list[Task],
        training_day_task_ids: set[int],
    ) -> None:
        """Process and store ranking data for a single student."""
        # Get all student tags (as list for array storage)
        student_tags = list(student.student_tags) if student.student_tags else []

        # Determine which tasks should be visible to this student based on their tags
        visible_tasks = self._get_visible_tasks(
            training_day, participation, training_day_tasks
        )

        # Add visible tasks to student's StudentTask records if not already present
        self._ensure_student_tasks(student, visible_tasks, training_day)

        # Get the managing participation for this user
        managing_participation = get_managing_participation(
            self.sql_session, training_day, participation.user
        )
        if managing_participation is None:
            raise ValueError(
                f"User {participation.user.username} (id={participation.user_id}) "
                f"does not have a participation in the managing contest "
                f"'{training_day.training_program.managing_contest.name}' "
                f"for training day '{training_day.name}'"
            )

        # Check if student missed the training (no starting_time)
        student_missed = participation.starting_time is None

        # Get task scores for ALL visible tasks
        task_scores, submissions = self._collect_task_scores_and_submissions(
            training_day,
            participation,
            managing_participation,
            visible_tasks,
            student_missed,
        )

        # Get score history
        history = self._collect_score_history(
            training_day,
            participation,
            training_day_task_ids,
            student_missed,
        )

        # Create archived ranking record
        archived_ranking = ArchivedStudentRanking(
            student_tags=student_tags,
            task_scores=task_scores if task_scores else None,
            submissions=submissions if submissions else None,
            history=history if history else None,
        )
        archived_ranking.training_day_id = training_day.id
        archived_ranking.student_id = student.id
        self.sql_session.add(archived_ranking)

    def _archive_ranking_data(
        self, training_day: TrainingDay, contest: Contest
    ) -> None:
        """Extract and store ranking data for all students.

        Stores on TrainingDay:
        - archived_tasks_data: task metadata including extra_headers for submission table

        Stores on ArchivedStudentRanking (per student):
        - task_scores: scores for ALL visible tasks (including 0 scores)
          The presence of a task_id key indicates the task was visible.
        - submissions: submission data for each task in RWS format
        - history: score history in RWS format
        """
        # Get the tasks assigned to this training day
        training_day_tasks = training_day.tasks
        training_day_task_ids = {task.id for task in training_day_tasks}

        # Build and store tasks_data on the training day
        training_day.archived_tasks_data = {
            str(task.id): build_task_data_for_archive(task)
            for task in training_day_tasks
        }

        for student, participation, _ in self._iterate_eligible_students(
            training_day, contest
        ):
            self._process_student_ranking(
                training_day,
                student,
                participation,
                training_day_tasks,
                training_day_task_ids,
            )
