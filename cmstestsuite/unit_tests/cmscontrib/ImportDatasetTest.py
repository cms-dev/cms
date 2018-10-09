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

"""Tests for the ImportDataset script"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import Dataset, SessionGen
from cmscontrib.ImportDataset import DatasetImporter
from cmscontrib.loaders.base_loader import TaskLoader


def fake_loader_factory(task, dataset):
    """Return a Loader class always returning the same information"""
    # DatasetImporter imports the active dataset of the task.
    task.active_dataset = dataset

    class FakeLoader(TaskLoader):
        @staticmethod
        def detect(path):
            return True

        def get_task(self, get_statement):
            return task

        def task_has_changed(self):
            return True

    return FakeLoader


class TestImportDataset(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        # DB already contains a dataset.
        self.task = self.add_task()
        self.task_type = "my_task_type"
        self.dataset = self.add_dataset(
            task=self.task, task_type=self.task_type)

        self.session.commit()
        self.task_id = self.task.id
        self.task_name = self.task.name
        self.dataset_desc = self.dataset.description

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    @staticmethod
    def do_import(task, dataset, description):
        """Create an importer and call do_import in a convenient way"""
        return DatasetImporter(
            "path", description,
            fake_loader_factory(task, dataset)).do_import()

    def assertDatasetInDb(self, task_id, description, task_type):
        """Assert that the dataset with the given data is in the DB

        The query is done by task_id and description, and to avoid caching,
        we query from a brand new session.

        """
        with SessionGen() as session:
            db_datasets = session.query(Dataset)\
                .filter(Dataset.task_id == task_id)\
                .filter(Dataset.description == description).all()
            self.assertEqual(len(db_datasets), 1)
            d = db_datasets[0]
            self.assertEqual(d.description, description)
            self.assertEqual(d.task_type, task_type)

    def test_clean_import(self):
        # Completely new dataset for the existing task, import and attach it
        # to the contest. The description in the dataset is ignored in favor
        # of the one passed to the DatasetImporter.
        desc_ignored = "new_desc_ignored"
        desc = "new_desc"
        task_type = "new_task_type"
        task = self.get_task(name=self.task_name)
        new_dataset = self.get_dataset(
            task=task, description=desc_ignored, task_type=task_type)
        ret = self.do_import(task, new_dataset, desc)

        self.assertTrue(ret)
        self.assertDatasetInDb(self.task_id, desc, task_type)

    def test_dataset_exists(self):
        # Dataset already present, should not update.
        task_type = "new_task_type"
        task = self.get_task(name=self.task_name)
        new_dataset = self.get_dataset(
            task=task, description="ignored", task_type=task_type)
        ret = self.do_import(task, new_dataset, self.dataset_desc)

        self.assertFalse(ret)
        self.assertDatasetInDb(self.task_id, self.dataset_desc, self.task_type)

    def test_task_does_not_exist(self):
        # Dataset for a task not in the DB.
        task_type = "new_task_type"
        task = self.get_task(name="new_name")
        new_dataset = self.get_dataset(
            task=task, description="ignored", task_type=task_type)
        ret = self.do_import(task, new_dataset, self.dataset_desc)

        self.assertFalse(ret)


if __name__ == "__main__":
    unittest.main()
