#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the ImportContest script"""

import unittest

from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import Contest, SessionGen, Submission, Team, User
from cmscontrib.ImportContest import ContestImporter
from cmscontrib.loaders.base_loader import (
    ContestLoader,
    TaskLoader,
    TeamLoader,
    UserLoader,
)


def fake_loader_factory(
    contest: Contest,
    contest_has_changed: bool = False,
    tasks: list[tuple[str, bool]] | None = None,
    participations: list[dict] | None = None,
    users: list[User] | None = None,
    teams: list[Team] | None = None,
):
    """Return a Loader class always returning the same information

    contest: the contest to return
    contest_has_changed: what to return from contest_has_changed
    tasks: list of task names and whether they have changed
    participations: list of participations
    users: list of importable users
    teams: list of importable teams

    """

    tasks = tasks if tasks is not None else []
    participations = participations if participations is not None else []
    users = users if users is not None else []
    teams = teams if teams is not None else []

    task_name_list = [t.name for t, has_changed in tasks]
    tasks_by_name = dict((t.name, {
        "task": t,
        "has_changed": has_changed
    }) for t, has_changed in tasks)
    users_by_name = (
        users if isinstance(users, dict) else dict((u.username, u) for u in users)
    )
    teams_by_code = (
        teams if isinstance(teams, dict) else dict((t.code, t) for t in teams)
    )

    class FakeLoader(ContestLoader):
        @staticmethod
        def detect(path):
            return True

        def get_contest(self):
            return contest, task_name_list, participations

        def contest_has_changed(self):
            return contest_has_changed

        def get_task_loader(self, taskname):

            class FakeTaskLoader(TaskLoader):
                @staticmethod
                def detect(path):
                    return True

                def get_task(self, get_statement):
                    return tasks_by_name.get(taskname, None)["task"]

                def task_has_changed(self):
                    return tasks_by_name.get(taskname, None)["has_changed"]

            return FakeTaskLoader(self.path, self.file_cacher)

        def get_user_loader(self, username):

            class FakeUserLoader(UserLoader):
                @staticmethod
                def detect(path):
                    return True

                def get_user(self):
                    return users_by_name.get(username, None)

                def user_has_changed(self):
                    return True

            return FakeUserLoader(self.path, self.file_cacher)

        def get_team_loader(self, teamcode):

            class FakeTeamLoader(TeamLoader):
                @staticmethod
                def detect(path):
                    return True

                def get_team(self):
                    return teams_by_code.get(teamcode, None)

                def team_has_changed(self):
                    return True

            return FakeTeamLoader(self.path, self.file_cacher)

    return FakeLoader


class TestImportContest(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        # DB already contains a contest in a contest with a submission.
        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)
        self.dataset = self.add_dataset(task=self.task)
        self.task.active_dataset = self.task.datasets[0]
        self.submission = self.add_submission(self.task, self.participation)

        self.session.commit()
        self.contest_id = self.contest.id
        self.name = self.contest.name
        self.description = self.contest.description
        self.task_id = self.task.id
        self.task_title = self.task.title
        self.task_name = self.task.name
        self.dataset_id = self.dataset.id
        self.dataset_description = self.dataset.description
        self.submission_id = self.submission.id
        self.username = self.participation.user.username
        self.last_name = self.participation.user.last_name

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    @staticmethod
    def do_import(contest, tasks, participations,
                  contest_has_changed=False, update_contest=False,
                  import_tasks=False, update_tasks=False,
                  delete_stale_participations=False,
                  auto_import_users=True, auto_import_teams=True,
                  users=None, teams=None):
        """Create an importer and call do_import in a convenient way"""
        participations = [
            p if isinstance(p, dict) else {"username": p}
            for p in participations
        ]
        return ContestImporter(
            "path", True, False, import_tasks, update_contest, update_tasks,
            False, delete_stale_participations,
            auto_import_users, auto_import_teams,
            fake_loader_factory(contest, contest_has_changed,
                                tasks, participations, users, teams)
        ).do_import()

    def assertContestInDb(self, name, description, task_names_and_titles,
                          usernames_and_last_names):
        """Assert that the contest with the given data is in the DB

        The query is done by contest name, and to avoid caching, we query from
        a brand new session.

        From contest_id on, parameters are checked only if not None.

        """
        with SessionGen() as session:
            db_contests = session.query(Contest) \
                .filter(Contest.name == name).all()
            self.assertEqual(len(db_contests), 1)
            c = db_contests[0]
            self.assertEqual(c.name, name)
            self.assertEqual(c.description, description)
            self.assertCountEqual([(t.name, t.title) for t in c.tasks],
                                  task_names_and_titles)
            self.assertCountEqual([(u.user.username, u.user.last_name)
                                   for u in c.participations],
                                  usernames_and_last_names)

    def assertSubmissionCount(self, count):
        """Assert that we have that many submissions in the DB"""
        with SessionGen() as session:
            self.assertEqual(session.query(Submission).count(), count)

    def assertTeamInDb(self, code, name):
        """Assert that the team with the given data is in the DB"""
        with SessionGen() as session:
            db_teams = session.query(Team).filter(Team.code == code).all()
            self.assertEqual(len(db_teams), 1)
            team = db_teams[0]
            self.assertEqual(team.code, code)
            self.assertEqual(team.name, name)

    def test_import_task_in_db_not_attached(self):
        # Completely new contest, the task is already in the DB, not attached
        # to any contest. The import should succeed and the task should made
        # part of the contest.
        task_name = "new_task_name"
        task_title = "new_task_title"
        task = self.add_task(name=task_name, title=task_title, contest=None)
        self.session.commit()
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        ret = self.do_import(contest, [(task, True)], [], import_tasks=False)

        self.assertTrue(ret)
        self.assertContestInDb(name, description,
                               [(task_name, task_title)],
                               [])

    def test_import_task_not_in_db_imported(self):
        # Completely new contest, the task is not in the DB, but we ask to
        # import it. The import should succeed and the task should made part of
        # the contest.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        task_name = "new_task_name"
        task_title = "new_task_title"
        task = self.get_task(name=task_name, title=task_title, contest=contest)
        ret = self.do_import(contest, [(task, True)], [], import_tasks=True)

        self.assertTrue(ret)
        self.assertContestInDb(name, description,
                               [(task_name, task_title)],
                               [])

    def test_import_task_not_in_db_fail(self):
        # Completely new contest, but the task is not in the DB and we do not
        # ask to import it, so import should fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        task_name = "new_task_name"
        task_title = "new_task_title"
        task = self.get_task(name=task_name, title=task_title, contest=contest)
        ret = self.do_import(contest, [(task, True)], [], import_tasks=False)

        self.assertFalse(ret)

    def test_import_task_in_db_already_attached_fail(self):
        # Completely new contest, but the task is already attached to another
        # contest in the DB.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        task = self.get_task(name=self.task_name, title=self.task_title,
                             contest=contest)
        ret = self.do_import(contest, [(task, True)], [],
                             import_tasks=True, update_tasks=True)

        self.assertFalse(ret)
        # Task still tied to the original contest.
        self.assertContestInDb(self.name, self.description,
                               [(self.task_name, self.task_title)],
                               [(self.username, self.last_name)])

    def test_contest_exists_fail(self):
        # Contest exists but we do not ask to update it, should fail.
        description = "new_desc"
        contest = self.get_contest(name=self.name, description=description)
        ret = self.do_import(contest, [], [], update_contest=False)

        self.assertFalse(ret)
        self.assertContestInDb(self.name, self.description,
                               [(self.task_name, self.task_title)],
                               [(self.username, self.last_name)])

    def test_update_contest(self):
        # Update the existing contest, task not updated, participations should
        # not change even if we do not pass any.
        description = "new_desc"
        contest = self.get_contest(name=self.name, description=description)
        task_title = "new_task_title"
        task = self.get_task(name=self.task_name, title=task_title,
                             contest=contest)
        ret = self.do_import(contest, [(task, True)], [],
                             contest_has_changed=True, update_contest=True,
                             import_tasks=False, update_tasks=False)

        self.assertTrue(ret)
        self.assertContestInDb(self.name, description,
                               [(self.task_name, self.task_title)],
                               [(self.username, self.last_name)])
        self.assertSubmissionCount(1)

    def test_update_contest_removing_task(self):
        # Update the existing contest, the existing task is untied, but we
        # keep the submission.
        description = "new_desc"
        contest = self.get_contest(name=self.name, description=description)
        ret = self.do_import(contest, [], [],
                             contest_has_changed=True, update_contest=True,
                             import_tasks=True, update_tasks=True)

        self.assertTrue(ret)
        self.assertContestInDb(self.name, description, [],
                               [(self.username, self.last_name)])
        self.assertSubmissionCount(1)

    def test_update_contest_updating_and_adding_task(self):
        # Update the existing contest and the task, also add a new one.
        description = "new_desc"
        contest = self.get_contest(name=self.name, description=description)
        task_title = "new_task_title"
        task = self.get_task(name=self.task_name, title=task_title,
                             contest=contest)
        new_task_name = "new_task_name"
        new_task_title = "new_task_title"
        new_task = self.get_task(name=new_task_name, title=new_task_title,
                                 contest=contest)
        ret = self.do_import(contest, [(task, True), (new_task, True)], [],
                             contest_has_changed=True, update_contest=True,
                             import_tasks=True, update_tasks=True)

        self.assertTrue(ret)
        self.assertContestInDb(self.name, description,
                               [(self.task_name, task_title),
                                (new_task_name, new_task_title)],
                               [(self.username, self.last_name)])
        self.assertSubmissionCount(1)

    def test_import_participation_in_db(self):
        # Completely new contest, no tasks, a new participation for an existing
        # user, whose existing submission should be retained.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        ret = self.do_import(contest, [], [self.username])

        self.assertTrue(ret)
        self.assertContestInDb(name, description,
                               [],
                               [(self.username, self.last_name)])
        self.assertSubmissionCount(1)

    def test_import_participation_not_in_db_imported(self):
        # Completely new contest, no tasks, a new participation whose user is
        # not in the DB but can be imported by the loader.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        username = "new_username"
        last_name = "new_last_name"
        user = self.get_user(username=username, last_name=last_name)
        ret = self.do_import(contest, [], [username], users=[user])

        self.assertTrue(ret)
        self.assertContestInDb(name, description, [], [(username, last_name)])
        self.assertSubmissionCount(1)

    def test_import_participation_not_in_db_fail_without_user_auto_import(self):
        # Completely new contest, no tasks, a new participation but the user
        # is not in the DB and auto import is disabled, so it should fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        username = "new_username"
        user = self.get_user(username=username)
        ret = self.do_import(
            contest, [], [username], auto_import_users=False, users=[user])

        self.assertFalse(ret)
        self.assertSubmissionCount(1)

    def test_import_participation_not_in_db_fail_if_user_loader_missing(self):
        # Completely new contest, no tasks, a new participation whose user is
        # neither in the DB nor available through the loader, so it should fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        username = "new_username"
        ret = self.do_import(contest, [], [username])

        self.assertFalse(ret)
        self.assertSubmissionCount(1)

    def test_import_participation_not_in_db_fail_if_user_loader_duplicates(self):
        # If the loader produces a user that already exists under a different
        # referenced username, treat it like cmsImportUser and fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        user = self.get_user(username=self.username)
        ret = self.do_import(
            contest, [], ["new_username"], users={"new_username": user})

        self.assertFalse(ret)
        self.assertSubmissionCount(1)

    def test_import_participation_team_not_in_db_imported(self):
        # Completely new contest, no tasks, a new participation whose team is
        # not in the DB but can be imported by the loader.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        team_code = "new_team_code"
        team_name = "new_team_name"
        team = self.get_team(code=team_code, name=team_name)
        ret = self.do_import(
            contest, [], [{"username": self.username, "team": team_code}],
            teams=[team])

        self.assertTrue(ret)
        self.assertContestInDb(name, description, [],
                               [(self.username, self.last_name)])
        self.assertTeamInDb(team_code, team_name)
        self.assertSubmissionCount(1)

    def test_import_participation_team_not_in_db_fail_without_team_auto_import(self):
        # Completely new contest, no tasks, a new participation whose team is
        # not in the DB and auto import is disabled, so it should fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        team_code = "new_team_code"
        team = self.get_team(code=team_code)
        ret = self.do_import(
            contest, [], [{"username": self.username, "team": team_code}],
            auto_import_teams=False, teams=[team])

        self.assertFalse(ret)
        self.assertSubmissionCount(1)

    def test_import_participation_team_not_in_db_fail_if_team_loader_missing(self):
        # Completely new contest, no tasks, a new participation whose team is
        # neither in the DB nor available through the loader, so it should fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        team_code = "new_team_code"
        ret = self.do_import(
            contest, [], [{"username": self.username, "team": team_code}])

        self.assertFalse(ret)
        self.assertSubmissionCount(1)

    def test_import_participation_team_not_in_db_fail_if_team_loader_duplicates(self):
        # If the loader produces a team that already exists under a different
        # referenced code, treat it like cmsImportTeam and fail.
        name = "new_name"
        description = "new_desc"
        contest = self.get_contest(name=name, description=description)
        team = self.get_team(code=self.add_team().code)
        self.session.commit()
        ret = self.do_import(
            contest, [], [{"username": self.username, "team": "new_team_code"}],
            teams={"new_team_code": team})

        self.assertFalse(ret)
        self.assertSubmissionCount(1)

    def test_delete_stale_participations(self):
        # Update the existing contest, task not updated, we also ask to
        # delete participations that we do not pass.

        # Add a new participation with some submissions
        other_participation = self.add_participation(contest=self.contest)
        self.add_submission(self.task, other_participation)
        self.add_submission(self.task, other_participation)
        self.add_submission(self.task, other_participation)
        self.session.commit()

        # Update the contest, deleting the original participation.
        description = "new_desc"
        contest = self.get_contest(name=self.name, description=description)
        task_title = "new_task_title"
        task = self.get_task(name=self.task_name, title=task_title,
                             contest=contest)
        ret = self.do_import(contest, [(task, True)],
                             [other_participation.user.username],
                             contest_has_changed=True, update_contest=True,
                             import_tasks=False, update_tasks=False,
                             delete_stale_participations=True)

        self.assertTrue(ret)
        self.assertContestInDb(self.name, description,
                               [(self.task_name, self.task_title)],
                               [(other_participation.user.username,
                                 other_participation.user.last_name)])
        self.assertSubmissionCount(3)
        # Even if the original participation has been deleted, the user should
        # remain.
        self.assertEqual(len(self.session.query(User).all()), 2)

    def test_update_contest_same_participations(self):
        # Update the existing contest, task not updated, participations passed.
        description = "new_desc"
        contest = self.get_contest(name=self.name, description=description)
        task_title = "new_task_title"
        task = self.get_task(name=self.task_name, title=task_title,
                             contest=contest)
        ret = self.do_import(contest, [(task, True)], [self.username],
                             contest_has_changed=True, update_contest=True,
                             import_tasks=False, update_tasks=False)

        self.assertTrue(ret)
        self.assertContestInDb(self.name, description,
                               [(self.task_name, self.task_title)],
                               [(self.username, self.last_name)])
        self.assertSubmissionCount(1)


if __name__ == "__main__":
    unittest.main()
