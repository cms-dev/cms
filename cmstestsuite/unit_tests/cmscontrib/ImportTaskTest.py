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

"""Tests for the ImportTask script"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import SessionGen, Submission, Task
from cmscontrib.ImportTask import TaskImporter
from cmscontrib.loaders.base_loader import TaskLoader


def fake_loader_factory(task, task_has_changed=False):
    """Return a Loader class always returning the same information"""
    class FakeLoader(TaskLoader):
        @staticmethod
        def detect(path):
            return True

        def get_task(self, get_statement):
            return task

        def task_has_changed(self):
            return task_has_changed

    return FakeLoader


class TestImportTask(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        # DB already contains a task in a contest with a submission.
        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)
        self.dataset = self.add_dataset(task=self.task)
        self.manager = self.add_manager(dataset=self.dataset,
                                        filename="checker")
        self.task.active_dataset = self.task.datasets[0]
        self.submission = self.add_submission(self.task, self.participation)

        self.session.commit()
        self.contest_id = self.contest.id
        self.task_id = self.task.id
        self.task_title = self.task.title
        self.task_name = self.task.name
        self.dataset_id = self.dataset.id
        self.dataset_description = self.dataset.description
        self.submission_id = self.submission.id

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    @staticmethod
    def do_import(task, contest_id, update,
                  prefix=None, override_name=None, task_has_changed=False):
        """Create an importer and call do_import in a convenient way"""
        return TaskImporter(
            "path", prefix, override_name, update, False, contest_id,
            fake_loader_factory(task, task_has_changed)).do_import()

    def assertTaskInDb(self, task_name, title, contest_id,
                       task_id=None, active_dataset_id=None, dataset_ids=None,
                       dataset_descriptions=None, dataset_task_types=None,
                       dataset_manager_digests=None):
        """Assert that the task with the given data is in the DB

        The query is done by task name, and to avoid caching, we query from a
        brand new session.

        From task_id on, parameters are checked only if not None.

        """
        with SessionGen() as session:
            db_tasks = session.query(Task) \
                .filter(Task.name == task_name).all()
            self.assertEqual(len(db_tasks), 1)
            t = db_tasks[0]
            self.assertEqual(t.name, task_name)
            self.assertEqual(t.title, title)
            self.assertEqual(t.contest_id, contest_id)
            if task_id is not None:
                self.assertEqual(t.id, task_id)
            if active_dataset_id is not None:
                self.assertEqual(active_dataset_id, t.active_dataset_id)
            if dataset_ids is not None:
                self.assertCountEqual(dataset_ids,
                                      (d.id for d in t.datasets))
            if dataset_descriptions is not None:
                self.assertCountEqual(dataset_descriptions,
                                      (d.description for d in t.datasets))
            if dataset_task_types is not None:
                self.assertCountEqual(dataset_task_types,
                                      (d.task_type for d in t.datasets))
            if dataset_manager_digests is not None:
                self.assertCountEqual(dataset_manager_digests,
                                      (m.digest
                                       for d in t.datasets
                                       for m in d.managers.values()))

    def test_clean_import(self):
        # Completely new task, import and attach it to the contest.
        prefix = "prefix"
        override_name = "overridden"
        new_title = "new_title"
        new_task = self.get_task(name="newtask", title=new_title)
        ret = self.do_import(new_task, self.contest_id, update=False,
                             prefix=prefix, override_name=override_name)

        self.assertTrue(ret)
        self.assertTaskInDb(prefix + override_name, new_title, self.contest_id,
                            dataset_ids=[])

    def test_clean_import_no_contest(self):
        # Completely new task, do not attach it to any contest.
        prefix = "prefix"
        override_name = "overridden"
        new_title = "new_title"
        new_task = self.get_task(name="newtask", title=new_title)
        ret = self.do_import(new_task, None, update=False,
                             prefix=prefix, override_name=override_name)

        self.assertTrue(ret)
        self.assertTaskInDb(prefix + override_name, new_title, None,
                            dataset_ids=[])

    def test_task_exists_no_update(self):
        # Task exists, but we don't ask to update it.
        new_task = self.get_task(name=self.task_name, title="new_title")
        ret = self.do_import(new_task, self.contest_id, update=False,
                             task_has_changed=True)

        self.assertFalse(ret)
        self.assertTaskInDb(self.task_name, self.task_title, self.contest_id,
                            task_id=self.task_id,
                            dataset_ids=[self.dataset_id])

    def test_task_exists_update(self):
        # Task exists, and we update it, attaching it to the same contest.
        # The existing dataset should be kept.
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        ret = self.do_import(new_task, self.contest_id, update=True,
                             task_has_changed=True)

        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, new_title, self.contest_id,
                            task_id=self.task_id,
                            dataset_ids=[self.dataset_id])

    def test_task_exists_update_new_dataset(self):
        # Task exists, and we update it, attaching it to the same contest.
        # The existing dataset should be kept, and the new one should be added.
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        new_desc = "new_desc"
        self.get_dataset(task=new_task, description=new_desc)
        ret = self.do_import(new_task, self.contest_id, update=True,
                             task_has_changed=True)

        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, new_title, self.contest_id,
                            task_id=self.task_id,
                            dataset_descriptions=[self.dataset_description,
                                                  new_desc],
                            active_dataset_id=self.dataset_id)

    def test_task_exists_update_overwrite_dataset(self):
        # Task exists, and we update it, attaching it to the same contest.
        # The existing dataset should be overwritten by the new one, and we
        # check by looking at the task type.
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        new_task_type = "Batch"
        self.get_dataset(task=new_task, description=self.dataset_description,
                         task_type=new_task_type)
        self.assertNotEqual(new_task_type, self.dataset.task_type)
        ret = self.do_import(new_task, self.contest_id, update=True,
                             task_has_changed=True)

        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, new_title, self.contest_id,
                            task_id=self.task_id,
                            dataset_descriptions=[self.dataset_description],
                            dataset_task_types=["Batch"])

    def test_task_exists_update_new_manager(self):
        # Task exists, and we update it, attaching it to the same contest.
        # The existing dataset should be overwritten by the new one, in
        # particular the new manager should be included.
        new_task = self.get_task(name=self.task_name, title=self.task_title)
        # New version of checker
        new_dataset = self.get_dataset(
            task=new_task, description=self.dataset.description)
        new_checker = self.get_manager(dataset=new_dataset, filename="checker")
        ret = self.do_import(new_task, self.contest_id, update=True,
                             task_has_changed=True)

        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, self.task_title, self.contest_id,
                            task_id=self.task_id,
                            dataset_descriptions=[self.dataset_description],
                            dataset_manager_digests=[new_checker.digest],
                            active_dataset_id=self.dataset_id)

    def test_task_exists_update_keep_contest(self):
        # Task exists, and we update it, not specifying which contest (should
        # remain attached to the same).
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        ret = self.do_import(new_task, None, update=True,
                             task_has_changed=True)

        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, new_title, self.contest_id,
                            task_id=self.task_id)

    def test_task_exists_update_change_contest(self):
        # Task exists, and we update it, but we try to attach it to a different
        # contest. This is not allowed.
        new_contest = self.add_contest()
        self.session.commit()
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        ret = self.do_import(new_task, new_contest.id, update=True,
                             task_has_changed=True)

        self.assertFalse(ret)
        self.assertTaskInDb(self.task_name, self.task_title, self.contest_id,
                            task_id=self.task_id)

    def test_task_exists_update_not_removing_submissions(self):
        # Task exists, and we update it. The submission should still be there.
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        ret = self.do_import(new_task, None, update=True,
                             task_has_changed=True)

        # Task is updated, but the submission remained.
        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, new_title, self.contest_id,
                            task_id=self.task_id)
        with SessionGen() as session:
            submissions = session.query(Submission)\
                .filter(Submission.id == self.submission_id).all()
            self.assertEqual(len(submissions), 1)

    def test_task_exists_not_tied(self):
        # Task exists, not tied to a contest, we update it.
        self.task.contest = None
        self.session.commit()
        new_title = "new_title"
        new_task = self.get_task(name=self.task_name, title=new_title)
        ret = self.do_import(new_task, None, update=True,
                             task_has_changed=True)

        self.assertTrue(ret)
        self.assertTaskInDb(self.task_name, new_title, None,
                            task_id=self.task_id)


if __name__ == "__main__":
    unittest.main()
