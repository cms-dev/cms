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

"""Round-trip tests for the training program exporter/importer."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

from cms.db import (
    ArchivedAttendance,
    ArchivedStudentRanking,
    Student,
    StudentTask,
    TrainingDay,
    TrainingDayGroup,
    TrainingProgram,
)
from cms.server.admin.handlers.trainingprogram_transfer import (
    TrainingProgramImporter,
    build_training_program_config,
    load_training_program_yaml,
    write_training_program_yaml,
)
from cmscontrib.importing import ImportDataError
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin


class FakeContestImporter:
    """Stands in for ContestImporter: creates a fresh contest with tasks
    of the given names, as importing the contest archive would."""

    def __init__(self, test, contest_name, task_names):
        self.test = test
        self.contest_name = contest_name
        self.task_names = task_names

    def import_into_session(self, session):
        contest = self.test.add_contest(name=self.contest_name)
        for num, name in enumerate(self.task_names):
            self.test.add_task(contest=contest, name=name, num=num)
        session.flush()
        return contest


class TestTrainingProgramTransfer(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.notifications = []
        self.contest = self.add_contest(name="tp_contest")
        self.program = TrainingProgram(
            name="program", description="A program",
            managing_contest=self.contest)
        self.session.add(self.program)

        self.task_a = self.add_task(contest=self.contest, name="task_a", num=0)
        self.task_b = self.add_task(contest=self.contest, name="task_b", num=1)

        self.students = {}
        for username in ("alice", "bob"):
            user = self.add_user(username=username)
            participation = self.add_participation(
                user=user, contest=self.contest)
            student = Student(training_program=self.program,
                              participation=participation,
                              student_tags=["group_%s" % username])
            self.session.add(student)
            self.students[username] = student
        self.session.flush()

        self.archived_day = TrainingDay(
            training_program=self.program, position=0, name="day_one",
            description="First day",
            start_time=datetime(2024, 1, 10, 9, 0),
            duration=timedelta(hours=5),
            training_day_types=["contest"],
            scoreboard_sharing={"mode": "tags"},
        )
        self.session.add(self.archived_day)
        self.session.flush()
        self.session.add(TrainingDayGroup(
            training_day=self.archived_day, tag_name="group_alice",
            start_time=datetime(2024, 1, 10, 9, 0),
            end_time=datetime(2024, 1, 10, 14, 0),
            alphabetical_task_order=True))
        self.task_a.training_day = self.archived_day
        self.task_a.training_day_num = 0
        self.task_a.visible_to_tags = ["group_alice"]
        # Key "999" is a task that no longer exists in this database.
        self.archived_day.archived_tasks_data = {
            str(self.task_a.id): {"name": "task_a", "title": "Task A"},
            "999": {"name": "gone", "title": "Gone"},
        }

        alice = self.students["alice"]
        self.session.add(ArchivedStudentRanking(
            training_day=self.archived_day, student=alice,
            student_tags=["group_alice"],
            task_scores={str(self.task_a.id): 70.0, "999": 10.0},
            submissions={str(self.task_a.id): [
                {"task": str(self.task_a.id), "time": 120, "score": 70.0,
                 "token": False, "extra": []}]},
            history=[[alice.participation.user_id, self.task_a.id, 120, 70.0],
                     [alice.participation.user_id, 999, 200, 10.0]],
        ))
        self.session.add(ArchivedAttendance(
            training_day=self.archived_day, student=alice,
            status="participated", location="room 1",
            delay_time=timedelta(minutes=15), delay_reasons="bus",
            justified=True, declared_bad_day=False, comment="late",
            recorded=True))
        self.session.add(ArchivedAttendance(
            training_day=self.archived_day, student=self.students["bob"],
            status="missed", justified=False, declared_bad_day=True,
            recorded=True))
        self.session.add(StudentTask(
            student=alice, task=self.task_a,
            source_training_day=self.archived_day,
            assigned_at=datetime(2024, 1, 10, 9, 0)))
        self.session.add(StudentTask(
            student=self.students["bob"], task=self.task_b,
            assigned_at=datetime(2024, 2, 1, 9, 0)))

        # An active training day with a live contest is not exported.
        active_contest = self.add_contest(name="active_day")
        self.active_day = TrainingDay(
            training_program=self.program, contest=active_contest,
            position=1, training_day_types=[])
        self.session.add(self.active_day)
        self.session.flush()

    def tearDown(self):
        self.session.rollback()
        self.delete_data()
        super().tearDown()

    def notify(self, title, text):
        self.notifications.append((title, text))

    def _roundtrip_config(self):
        config, skipped = build_training_program_config(self.program)
        self.assertEqual(skipped, [self.active_day])
        with tempfile.TemporaryDirectory() as tmp:
            write_training_program_yaml(config, tmp)
            self.assertTrue(
                os.path.exists(os.path.join(tmp, "training_program.yaml")))
            return load_training_program_yaml(tmp)

    def test_export_config(self):
        config = self._roundtrip_config()
        self.assertEqual(config["name"], "program")
        self.assertEqual(config["managing_contest"], "tp_contest")
        self.assertEqual([s["username"] for s in config["students"]],
                         ["alice", "bob"])
        self.assertEqual(len(config["training_days"]), 1)
        day = config["training_days"][0]
        self.assertEqual(day["name"], "day_one")
        self.assertEqual(day["duration"], 5 * 3600)
        self.assertEqual(day["task_keys"],
                         {str(self.task_a.id): "task_a", "999": None})
        self.assertEqual(len(day["rankings"]), 1)
        self.assertEqual(len(day["attendance"]), 2)
        self.assertEqual(day["attendance"][0]["delay_time"], 15 * 60)

    def _prepare_import_config(self):
        """Export, then make room for importing into the same database
        (task names are globally unique) as if it were another one."""
        config = self._roundtrip_config()
        config["name"] = "program_copy"
        self.task_a.name = "old_task_a"
        self.task_b.name = "old_task_b"
        self.session.flush()
        return config

    def test_import_roundtrip(self):
        config = self._prepare_import_config()
        old_task_a_id = self.task_a.id

        importer = TrainingProgramImporter(
            self.session,
            FakeContestImporter(self, "tp_contest_copy", ["task_a", "task_b"]),
            config, self.notify)
        program = importer.do_import()
        self.session.flush()

        self.assertEqual(program.name, "program_copy")
        self.assertEqual(program.managing_contest.name, "tp_contest_copy")
        self.assertEqual(self.notifications, [])

        students = {s.participation.user.username: s for s in program.students}
        self.assertEqual(set(students), {"alice", "bob"})
        self.assertEqual(students["alice"].student_tags, ["group_alice"])

        self.assertEqual(len(program.training_days), 1)
        day = program.training_days[0]
        self.assertIsNone(day.contest)
        self.assertEqual(day.name, "day_one")
        self.assertEqual(day.description, "First day")
        self.assertEqual(day.start_time, datetime(2024, 1, 10, 9, 0))
        self.assertEqual(day.duration, timedelta(hours=5))
        self.assertEqual(day.training_day_types, ["contest"])
        self.assertEqual(day.scoreboard_sharing, {"mode": "tags"})
        self.assertEqual([g.tag_name for g in day.groups], ["group_alice"])
        self.assertTrue(day.groups[0].alphabetical_task_order)

        new_tasks = {t.name: t for t in program.managing_contest.tasks}
        new_task_a = new_tasks["task_a"]
        self.assertNotEqual(new_task_a.id, old_task_a_id)
        self.assertEqual(day.tasks, [new_task_a])
        self.assertEqual(new_task_a.visible_to_tags, ["group_alice"])

        # Archived task keys are rewritten to the new ids (synthetic for
        # tasks that do not exist).
        self.assertEqual(set(day.archived_tasks_data),
                         {str(new_task_a.id), "10000000"})
        self.assertEqual(day.archived_tasks_data[str(new_task_a.id)]["name"],
                         "task_a")

        self.assertEqual(len(day.archived_student_rankings), 1)
        ranking = day.archived_student_rankings[0]
        self.assertEqual(ranking.student, students["alice"])
        self.assertEqual(ranking.task_scores,
                         {str(new_task_a.id): 70.0, "10000000": 10.0})
        self.assertEqual(list(ranking.submissions), [str(new_task_a.id)])
        self.assertEqual(ranking.submissions[str(new_task_a.id)][0]["task"],
                         str(new_task_a.id))
        user_id = students["alice"].participation.user_id
        self.assertEqual(ranking.history,
                         [[user_id, new_task_a.id, 120, 70.0],
                          [user_id, 10000000, 200, 10.0]])

        attendance = {a.student.participation.user.username: a
                      for a in day.archived_attendances}
        self.assertEqual(attendance["alice"].status, "participated")
        self.assertEqual(attendance["alice"].location, "room 1")
        self.assertEqual(attendance["alice"].delay_time, timedelta(minutes=15))
        self.assertEqual(attendance["alice"].delay_reasons, "bus")
        self.assertTrue(attendance["alice"].justified)
        self.assertEqual(attendance["alice"].comment, "late")
        self.assertEqual(attendance["bob"].status, "missed")
        self.assertTrue(attendance["bob"].declared_bad_day)

        alice_tasks = {st.task.name: st for st in students["alice"].student_tasks}
        self.assertEqual(set(alice_tasks), {"task_a"})
        self.assertEqual(alice_tasks["task_a"].source_training_day, day)
        self.assertEqual(alice_tasks["task_a"].assigned_at,
                         datetime(2024, 1, 10, 9, 0))
        bob_tasks = [st.task.name for st in students["bob"].student_tasks]
        self.assertEqual(bob_tasks, ["task_b"])

    def test_import_skips_unknown_users(self):
        config = self._prepare_import_config()
        config["students"][0]["username"] = "nobody"
        config["training_days"][0]["rankings"][0]["username"] = "nobody"

        importer = TrainingProgramImporter(
            self.session,
            FakeContestImporter(self, "tp_contest_copy", ["task_a", "task_b"]),
            config, self.notify)
        program = importer.do_import()
        self.session.flush()

        self.assertEqual([s.participation.user.username
                          for s in program.students], ["bob"])
        day = program.training_days[0]
        self.assertEqual(day.archived_student_rankings, [])
        self.assertEqual(len(day.archived_attendances), 1)
        self.assertEqual(self.notifications, [])
        importer.notify_skipped()
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("nobody", self.notifications[0][1])

    def test_import_rejects_existing_name(self):
        config = self._roundtrip_config()
        with self.assertRaises(ImportDataError):
            TrainingProgramImporter(
                self.session,
                FakeContestImporter(self, "other", []),
                config, self.notify).do_import()

    def test_load_missing_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ImportDataError):
                load_training_program_yaml(tmp)


if __name__ == "__main__":
    unittest.main()
