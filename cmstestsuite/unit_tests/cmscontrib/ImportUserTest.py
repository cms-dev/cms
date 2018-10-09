#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the ImportUser script"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import Participation, SessionGen, User
from cmscontrib.ImportUser import UserImporter
from cmscontrib.loaders.base_loader import UserLoader


def fake_loader_factory(user):
    """Return a Loader class always returning the same information"""
    class FakeLoader(UserLoader):
        @staticmethod
        def detect(path):
            return True

        def get_user(self):
            return user

        def user_has_changed(self):
            return True

    return FakeLoader


class TestImportUser(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        # DB already contains a user participating in a contest.
        self.contest = self.add_contest()
        self.user = self.add_user()
        self.participation = self.add_participation(
            user=self.user, contest=self.contest)

        self.session.commit()
        self.contest_id = self.contest.id
        self.username = self.user.username
        self.last_name = self.user.last_name

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    @staticmethod
    def do_import(user, contest_id):
        """Create an importer and call do_import in a convenient way"""
        return UserImporter(
            "path", contest_id, fake_loader_factory(user)).do_import()

    def assertUserInDb(self, username, last_name, contest_ids):
        """Assert that the user with the given data is in the DB

        The query is done by username, and to avoid caching, we query from a
        brand new session.

        """
        with SessionGen() as session:
            db_users = session.query(User) \
                .filter(User.username == username).all()
            self.assertEqual(len(db_users), 1)
            u = db_users[0]
            self.assertEqual(u.username, username)
            self.assertEqual(u.last_name, last_name)

            if contest_ids is not None:
                db_participations = session.query(Participation) \
                    .filter(Participation.user_id == u.id).all()
                self.assertCountEqual(
                    contest_ids,
                    (p.contest_id for p in db_participations))

    def test_clean_import(self):
        # Completely new user, import and attach it to the contest.
        username = "new_username"
        last_name = "last_name"
        new_user = self.get_user(username=username, last_name=last_name)
        ret = self.do_import(new_user, self.contest_id)

        self.assertTrue(ret)
        self.assertUserInDb(username, last_name, [self.contest_id])

    def test_clean_import_no_contest(self):
        # Completely new user, import but don't create any participation.
        username = "new_username"
        last_name = "last_name"
        new_user = self.get_user(username=username, last_name=last_name)
        ret = self.do_import(new_user, None)

        self.assertTrue(ret)
        self.assertUserInDb(username, last_name, [])

    def test_user_exists(self):
        # Username already present, should not update.
        last_name = "last_name"
        new_user = self.get_user(username=self.username, last_name=last_name)
        ret = self.do_import(new_user, self.contest_id)

        self.assertFalse(ret)
        self.assertUserInDb(self.username, self.last_name, [self.contest_id])


if __name__ == "__main__":
    unittest.main()
