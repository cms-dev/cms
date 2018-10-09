#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""This script works kind of like cmsImportTask, but it assumes that the task
already exists. Specifically, it will just add a new dataset (without
activating it).

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import logging
import os
import sys

from cms import utf8_decoder
from cms.db import Dataset, SessionGen
from cms.db.filecacher import FileCacher
from cmscontrib.importing import ImportDataError, task_from_db
from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class DatasetImporter:
    def __init__(self, path, description, loader_class):
        self.file_cacher = FileCacher()
        self.description = description
        self.loader = loader_class(os.path.abspath(path), self.file_cacher)

    def do_import(self):
        """Get the task from the TaskLoader, but store *just* its dataset."""

        # Get the task
        task = self.loader.get_task(get_statement=False)
        if task is None:
            return False

        # Keep the dataset (and the task name) and delete the task
        dataset = task.active_dataset
        dataset.task = None
        task_name = task.name
        del task

        dataset.description = self.description

        # Store the dataset
        logger.info("Creating new dataset (\"%s\") for task %s on the "
                    "database.", dataset.description, task_name)

        with SessionGen() as session:
            try:
                task = task_from_db(task_name, session)
                self._dataset_to_db(session, dataset, task)
            except ImportDataError as e:
                logger.error(str(e))
                logger.info("Error while importing, no changes were made.")
                return False

            session.commit()
            dataset_id = dataset.id

        logger.info("Import finished (dataset id: %s).", dataset_id)
        return True

    @staticmethod
    def _dataset_to_db(session, dataset, task):
        old_dataset = session.query(Dataset)\
            .filter(Dataset.task_id == task.id)\
            .filter(Dataset.description == dataset.description).first()
        if old_dataset is not None:
            raise ImportDataError("Dataset \"%s\" already exists."
                                  % dataset.description)
        dataset.task = task
        session.add(dataset)
        return dataset


def main():
    """Parse arguments and launch process."""

    parser = argparse.ArgumentParser(
        description="Import a new dataset for an existing task in CMS.",
        epilog=build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "-L", "--loader",
        action="store", type=utf8_decoder,
        default=None,
        help="use the specified loader (default: autodetect)"
    )
    parser.add_argument(
        "target",
        action="store", type=utf8_decoder,
        help="target file/directory from where to import the dataset"
    )

    args = parser.parse_args()

    args.description = input("Enter a description: ")

    loader_class = choose_loader(
        args.loader,
        args.target,
        parser.error
    )

    importer = DatasetImporter(path=args.target,
                               description=args.description,
                               loader_class=loader_class)
    success = importer.do_import()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
