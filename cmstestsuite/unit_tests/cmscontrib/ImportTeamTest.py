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

"""Tests for the ImportTeam script"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import SessionGen, Team
from cmscontrib.ImportTeam import TeamImporter
from cmscontrib.loaders.base_loader import TeamLoader


def fake_loader_factory(team):
    """Return a Loader class always returning the same information"""
    class FakeLoader(TeamLoader):
        @staticmethod
        def detect(path):
            return True

        def get_team(self):
            return team

        def team_has_changed(self):
            return True

    return FakeLoader


class TestImportTeam(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        # DB already contains a team.
        self.team = self.add_team()

        self.session.commit()
        self.code = self.team.code
        self.name = self.team.name

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    @staticmethod
    def do_import(team):
        """Create an importer and call do_import in a convenient way"""
        return TeamImporter("path", fake_loader_factory(team)).do_import()

    def assertTeamInDb(self, code, name):
        """Assert that the team with the given data is in the DB

        The query is done by code, and to avoid caching, we query from a
        brand new session.

        """
        with SessionGen() as session:
            db_teams = session.query(Team).filter(Team.code == code).all()
            self.assertEqual(len(db_teams), 1)
            t = db_teams[0]
            self.assertEqual(t.code, code)
            self.assertEqual(t.name, name)

    def test_clean_import(self):
        # Completely new team, import it.
        code = "new_code"
        name = "new_name"
        new_team = self.get_team(code=code, name=name)
        ret = self.do_import(new_team)

        self.assertTrue(ret)
        self.assertTeamInDb(code, name)

    def test_team_exists(self):
        # Team already present, should not update.
        name = "new_name"
        new_team = self.get_team(code=self.code, name=name)
        ret = self.do_import(new_team)

        self.assertFalse(ret)
        self.assertTeamInDb(self.code, self.name)


if __name__ == "__main__":
    unittest.main()
