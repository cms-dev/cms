#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Pasit Sangprachathanarak <ouipingpasit@gmail.com>
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

"""Migration script to add skip_failed_subtask field to the Task table.

This script adds a new boolean column 'skip_failed_subtask' to the Task table
with a default value of True (enabled by default).

Usage:
    python3 -m cms.db.add_skip_subtask_field

"""

import logging
import sys

try:
    from sqlalchemy.exc import OperationalError
except ImportError:
    # Handle case where SQLAlchemy is not available
    class OperationalError(Exception):
        pass

from cms import default_argument_parser
from cms.db import SessionGen


logger = logging.getLogger(__name__)


def add_skip_subtask_field():
    """Add the skip_failed_subtask field to the Task table."""

    logger.info("Starting migration to add skip_failed_subtask field")

    with SessionGen() as session:
        try:
            # Check if the column already exists
            result = session.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='tasks' AND column_name='skip_failed_subtask'"
            )

            if result.fetchone():
                logger.info("Column skip_failed_subtask already exists")
                return True

            # Add the new column with default value True
            logger.info("Adding skip_failed_subtask column to tasks table")
            session.execute(
                "ALTER TABLE tasks ADD COLUMN skip_failed_subtask BOOLEAN "
                "NOT NULL DEFAULT TRUE"
            )
            session.commit()

            logger.info("Successfully added skip_failed_subtask field")
            return True

        except OperationalError as e:
            logger.error(f"Failed to add skip_failed_subtask field: {e}")
            session.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error during migration: {e}")
            session.rollback()
            return False


def main():
    """Main function for the migration script."""

    parser = default_argument_parser(
        description="Add skip_failed_subtask field to Task table"
    )
    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    success = add_skip_subtask_field()

    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
