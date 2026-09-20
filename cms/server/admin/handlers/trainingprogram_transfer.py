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

"""Export and import of whole training programs.

A training program archive is a contest archive in YamlLoader format
(contest.yaml + one directory per task of the managing contest) plus a
``training_program.yaml`` file describing everything that is specific to
the training program: students, archived training days, and the ranking
and attendance data archived for them.

Database ids never survive a round trip, so every reference is expressed
by name: tasks by task name, students by username, training days by
training day name. The archived ranking JSON (``archived_tasks_data``,
``task_scores``, ``submissions``, ``history``) is keyed by task id in the
database; the archive keeps those keys as-is and ships a per-training-day
``task_keys`` mapping from key to task name so that the importer can
rewrite them to the ids of the freshly imported tasks.
"""

import logging
import os
import typing
from collections.abc import Callable
from datetime import datetime, timedelta

import yaml
from sqlalchemy.orm import Session

from cms.db import (
    ArchivedAttendance,
    ArchivedStudentRanking,
    Contest,
    Participation,
    Student,
    StudentTask,
    Task,
    TrainingDay,
    TrainingDayGroup,
    TrainingProgram,
    User,
)
from cmscommon.datetime import make_datetime, make_timestamp
from cmscontrib.importing import ImportDataError

if typing.TYPE_CHECKING:
    from cmscontrib.ImportContest import ContestImporter


logger = logging.getLogger(__name__)

TRAINING_PROGRAM_YAML = "training_program.yaml"

# Archived training days imported from CSV reference tasks that do not
# exist in the database; they use synthetic ids above this base (see
# import_td_from_csv.py). We reuse the same scheme for archived tasks
# whose Task row cannot be found after import.
_SYNTHETIC_ID_BASE = 10_000_000

Notifier = Callable[[str, str], None]


def _ts(value: datetime | None) -> float | None:
    return make_timestamp(value) if value is not None else None


def _from_ts(value: float | int | None) -> datetime | None:
    return make_datetime(value) if value is not None else None


def _seconds(value: timedelta | None) -> float | None:
    return value.total_seconds() if value is not None else None


def _from_seconds(value: float | int | None) -> timedelta | None:
    return timedelta(seconds=value) if value is not None else None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _export_student(student: Student, task_names: dict[int, str],
                    training_day_indexes: dict[int, int]) -> dict:
    participation = student.participation
    data: dict = {
        "username": participation.user.username,
        "tags": list(student.student_tags or []),
        "hidden": participation.hidden,
    }
    student_tasks = []
    for student_task in sorted(student.student_tasks,
                               key=lambda st: st.assigned_at):
        task_name = task_names.get(student_task.task_id)
        if task_name is None:
            continue
        entry: dict = {
            "task": task_name,
            "assigned_at": _ts(student_task.assigned_at),
        }
        source_index = training_day_indexes.get(
            student_task.source_training_day_id)
        if source_index is not None:
            entry["source_training_day"] = source_index
        student_tasks.append(entry)
    if student_tasks:
        data["tasks"] = student_tasks
    return data


def _export_ranking(ranking: ArchivedStudentRanking) -> dict:
    return {
        "username": ranking.student.participation.user.username,
        "student_tags": list(ranking.student_tags or []),
        "task_scores": ranking.task_scores,
        "submissions": ranking.submissions,
        "history": ranking.history,
    }


def _export_attendance(attendance: ArchivedAttendance) -> dict:
    return {
        "username": attendance.student.participation.user.username,
        "status": attendance.status,
        "location": attendance.location,
        "delay_time": _seconds(attendance.delay_time),
        "delay_reasons": attendance.delay_reasons,
        "justified": attendance.justified,
        "declared_bad_day": attendance.declared_bad_day,
        "comment": attendance.comment,
        "recorded": attendance.recorded,
    }


def _export_training_day(training_day: TrainingDay,
                         task_names: dict[int, str]) -> dict:
    data: dict = {
        "name": training_day.name,
        "description": training_day.description,
        "position": training_day.position,
        "start_time": _ts(training_day.start_time),
        "duration": _seconds(training_day.duration),
        "types": list(training_day.training_day_types or []),
        "scoreboard_sharing": (dict(training_day.scoreboard_sharing)
                               if training_day.scoreboard_sharing else None),
        "groups": [
            {
                "tag_name": group.tag_name,
                "start_time": _ts(group.start_time),
                "end_time": _ts(group.end_time),
                "alphabetical_task_order": group.alphabetical_task_order,
            }
            for group in sorted(training_day.groups, key=lambda g: g.tag_name)
        ],
        "tasks": [
            {
                "name": task.name,
                "training_day_num": task.training_day_num,
                "visible_to_tags": list(task.visible_to_tags or []),
            }
            for task in training_day.tasks
        ],
    }

    archived_tasks_data = training_day.archived_tasks_data or {}
    task_keys: dict[str, str | None] = {}
    for key in archived_tasks_data:
        try:
            task_keys[key] = task_names.get(int(key))
        except ValueError:
            task_keys[key] = None
    data["archived_tasks_data"] = archived_tasks_data
    data["task_keys"] = task_keys

    data["rankings"] = [
        _export_ranking(ranking)
        for ranking in sorted(
            training_day.archived_student_rankings,
            key=lambda r: r.student.participation.user.username)
    ]
    data["attendance"] = [
        _export_attendance(attendance)
        for attendance in sorted(
            training_day.archived_attendances,
            key=lambda a: a.student.participation.user.username)
    ]
    return data


def build_training_program_config(
    training_program: TrainingProgram,
) -> tuple[dict, list[TrainingDay]]:
    """Build the training_program.yaml content.

    return: the config dict and the list of training days that were not
        exported because they are still active (have a live contest).
    """
    contest = training_program.managing_contest
    task_names = {task.id: task.name for task in contest.tasks}

    archived_days = [td for td in training_program.training_days
                     if td.contest is None]
    skipped_days = [td for td in training_program.training_days
                    if td.contest is not None]
    # Training day names are not unique; student tasks reference their
    # source training day by index in the exported training_days list.
    training_day_indexes = {td.id: i for i, td in enumerate(archived_days)}

    students = sorted(
        (s for s in training_program.students if s.participation is not None),
        key=lambda s: s.participation.user.username)

    config = {
        "name": training_program.name,
        "description": training_program.description,
        "managing_contest": contest.name,
        "students": [
            _export_student(student, task_names, training_day_indexes)
            for student in students
        ],
        "training_days": [
            _export_training_day(td, task_names) for td in archived_days
        ],
    }
    return config, skipped_days


def write_training_program_yaml(config: dict, export_dir: str) -> None:
    path = os.path.join(export_dir, TRAINING_PROGRAM_YAML)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False,
                       allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def load_training_program_yaml(root_path: str) -> dict:
    path = os.path.join(root_path, TRAINING_PROGRAM_YAML)
    if not os.path.exists(path):
        raise ImportDataError(
            f"File missing: \"{TRAINING_PROGRAM_YAML}\". The archive does "
            "not look like a training program export.")
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict) or not config.get("name"):
        raise ImportDataError(
            f"\"{TRAINING_PROGRAM_YAML}\" is malformed: missing name.")
    return config


class TrainingProgramImporter:
    """Create a training program (and all its archived data) from a
    training program archive, inside a caller-provided session.

    Nothing is committed here; the caller decides, and should call
    notify_skipped() once the transaction has been committed.
    """

    def __init__(self, session: Session, importer: "ContestImporter",
                 config: dict, notify: Notifier):
        self.session = session
        self.importer = importer
        self.config = config
        self.notify = notify
        self.skipped_usernames: list[str] = []

    def do_import(self) -> TrainingProgram:
        name = self.config["name"]
        existing = (self.session.query(TrainingProgram)
                    .filter(TrainingProgram.name == name).first())
        if existing is not None:
            raise ImportDataError(
                f"Training program \"{name}\" already exists in database.")

        contest = self.importer.import_into_session(self.session)
        if contest.training_program is not None:
            raise ImportDataError(
                f"Contest \"{contest.name}\" already manages training "
                f"program \"{contest.training_program.name}\".")

        training_program = TrainingProgram(
            name=name,
            description=self.config.get("description") or name,
            managing_contest=contest,
        )
        self.session.add(training_program)
        self.session.flush()

        tasks_by_name = {task.name: task for task in contest.tasks}

        students_by_username = self._import_students(
            training_program, contest)

        training_days: list[TrainingDay] = []
        for td_config in self.config.get("training_days") or []:
            training_days.append(self._import_training_day(
                training_program, td_config, tasks_by_name,
                students_by_username))

        for student_config in self.config.get("students") or []:
            student = students_by_username.get(student_config.get("username"))
            if student is None:
                continue
            self._import_student_tasks(
                student, student_config.get("tasks") or [],
                tasks_by_name, training_days)

        return training_program

    def notify_skipped(self) -> None:
        if self.skipped_usernames:
            shown = ", ".join(self.skipped_usernames[:5])
            if len(self.skipped_usernames) > 5:
                shown += f" and {len(self.skipped_usernames) - 5} more"
            self.notify(
                "Some students not imported",
                f"Skipped {len(self.skipped_usernames)} student(s) whose "
                f"user does not exist in the database: {shown}")

    def _import_students(
        self, training_program: TrainingProgram, contest: Contest
    ) -> dict[str, Student]:
        students_by_username: dict[str, Student] = {}
        for student_config in self.config.get("students") or []:
            username = student_config.get("username")
            if not username or username in students_by_username:
                continue
            user = (self.session.query(User)
                    .filter(User.username == username).first())
            if user is None:
                self.skipped_usernames.append(username)
                continue

            participation = (
                self.session.query(Participation)
                .filter(Participation.contest == contest)
                .filter(Participation.user == user)
                .first())
            if participation is None:
                participation = Participation(
                    contest=contest,
                    user=user,
                    starting_time=make_datetime(),
                )
                self.session.add(participation)
            participation.hidden = bool(student_config.get("hidden", False))

            student = Student(
                training_program=training_program,
                participation=participation,
                student_tags=list(student_config.get("tags") or []),
            )
            self.session.add(student)
            students_by_username[username] = student

        self.session.flush()
        return students_by_username

    def _import_student_tasks(
        self, student: Student, tasks_config: list[dict],
        tasks_by_name: dict[str, Task],
        training_days: list[TrainingDay],
    ) -> None:
        seen: set[int] = set()
        for entry in tasks_config:
            task = tasks_by_name.get(entry.get("task"))
            if task is None or task.id in seen:
                continue
            seen.add(task.id)
            assigned_at = _from_ts(entry.get("assigned_at")) or make_datetime()
            student_task = StudentTask(assigned_at=assigned_at)
            student_task.student = student
            student_task.task = task
            source_index = entry.get("source_training_day")
            if (isinstance(source_index, int)
                    and 0 <= source_index < len(training_days)):
                student_task.source_training_day = training_days[source_index]
            self.session.add(student_task)

    def _build_task_id_map(
        self, td_config: dict, tasks_by_name: dict[str, Task]
    ) -> dict[str, int]:
        """Map archived task keys of the source database to task ids in
        this database (synthetic ids for tasks without a Task row)."""
        archived_tasks_data = td_config.get("archived_tasks_data") or {}
        task_keys = td_config.get("task_keys") or {}
        id_map: dict[str, int] = {}
        next_synthetic = _SYNTHETIC_ID_BASE
        for key in archived_tasks_data:
            task = tasks_by_name.get(task_keys.get(key))
            if task is not None:
                id_map[str(key)] = task.id
            else:
                id_map[str(key)] = next_synthetic
                next_synthetic += 1
        return id_map

    def _import_training_day(
        self, training_program: TrainingProgram, td_config: dict,
        tasks_by_name: dict[str, Task],
        students_by_username: dict[str, Student],
    ) -> TrainingDay:
        training_day = TrainingDay(
            training_program=training_program,
            position=td_config.get("position"),
            name=td_config.get("name"),
            description=td_config.get("description"),
            start_time=_from_ts(td_config.get("start_time")),
            duration=_from_seconds(td_config.get("duration")),
            training_day_types=list(td_config.get("types") or []),
            scoreboard_sharing=td_config.get("scoreboard_sharing"),
        )
        self.session.add(training_day)

        for group_config in td_config.get("groups") or []:
            group = TrainingDayGroup(
                tag_name=group_config["tag_name"],
                start_time=_from_ts(group_config.get("start_time")),
                end_time=_from_ts(group_config.get("end_time")),
                alphabetical_task_order=bool(
                    group_config.get("alphabetical_task_order", False)),
            )
            group.training_day = training_day
            self.session.add(group)

        for task_config in td_config.get("tasks") or []:
            task = tasks_by_name.get(task_config.get("name"))
            if task is None:
                continue
            task.training_day = training_day
            task.training_day_num = task_config.get("training_day_num")
            task.visible_to_tags = list(task_config.get("visible_to_tags") or [])

        self.session.flush()

        id_map = self._build_task_id_map(td_config, tasks_by_name)
        archived_tasks_data = td_config.get("archived_tasks_data") or {}
        training_day.archived_tasks_data = {
            str(id_map[str(key)]): value
            for key, value in archived_tasks_data.items()
        } or None

        for ranking_config in td_config.get("rankings") or []:
            student = students_by_username.get(ranking_config.get("username"))
            if student is None:
                continue
            self._import_ranking(training_day, student, ranking_config, id_map)

        for attendance_config in td_config.get("attendance") or []:
            student = students_by_username.get(
                attendance_config.get("username"))
            if student is None:
                continue
            self._import_attendance(training_day, student, attendance_config)

        return training_day

    @staticmethod
    def _remap_key(key, id_map: dict[str, int]) -> str:
        return str(id_map.get(str(key), key))

    def _import_ranking(
        self, training_day: TrainingDay, student: Student,
        ranking_config: dict, id_map: dict[str, int],
    ) -> None:
        task_scores = ranking_config.get("task_scores")
        if task_scores:
            task_scores = {self._remap_key(k, id_map): v
                           for k, v in task_scores.items()}

        submissions = ranking_config.get("submissions")
        if submissions:
            remapped: dict = {}
            for key, entries in submissions.items():
                new_key = self._remap_key(key, id_map)
                remapped[new_key] = [
                    {**entry, "task": new_key} if "task" in entry else entry
                    for entry in entries
                ]
            submissions = remapped

        history = ranking_config.get("history")
        if history:
            user_id = student.participation.user_id
            history = [
                [user_id, id_map.get(str(entry[1]), entry[1])] + list(entry[2:])
                for entry in history
            ]

        ranking = ArchivedStudentRanking(
            student_tags=list(ranking_config.get("student_tags") or []),
            task_scores=task_scores or None,
            submissions=submissions or None,
            history=history or None,
        )
        ranking.training_day = training_day
        ranking.student = student
        self.session.add(ranking)

    def _import_attendance(
        self, training_day: TrainingDay, student: Student,
        attendance_config: dict,
    ) -> None:
        attendance = ArchivedAttendance(
            status=attendance_config.get("status") or "participated",
            location=attendance_config.get("location"),
            delay_time=_from_seconds(attendance_config.get("delay_time")),
            delay_reasons=attendance_config.get("delay_reasons"),
            justified=bool(attendance_config.get("justified", False)),
            declared_bad_day=bool(
                attendance_config.get("declared_bad_day", False)),
            comment=attendance_config.get("comment"),
            recorded=bool(attendance_config.get("recorded", False)),
        )
        attendance.training_day = training_day
        attendance.student = student
        self.session.add(attendance)
