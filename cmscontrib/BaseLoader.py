#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""Base class for deriving loaders.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals


class Loader(object):
    """Base class for deriving loaders.

    Each loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

      * Once a loader is instatiated, get_contest() can be called on
        it, only once.

      * After get_contest() has been called, at the caller's will,
        get_task() and get_user() can be called, in any order and for
        how many times the caller want. The resource intensive
        operations that are not needed for get_contest() are better
        left in get_task() or get_user(), so that no time is wasted if
        the caller isn't interested in users or tasks.

    """

    # Short name of this loader, meant to be a unique identifier.
    short_name = None

    # Description of this loader, meant to be human readable.
    description = None

    def __init__(self, path, file_cacher):
        """Initialize the Loader.

        path (str): the filesystem location given by the user.
        file_cacher (FileCacher): the file cacher to use to store
                                  files (i.e. statements, managers,
                                  testcases, etc.).

        """
        self.path = path
        self.file_cacher = file_cacher

    @classmethod
    def detect(cls, path):
        """Detect whether this loader is able to interpret a path.

        If the loader chooses to not support autodetection, just
        always return False.

        path (string): the path to scan.

        return (bool): True if the loader is able to interpret the
                       given path.

        """
        raise NotImplementedError("Please extend Loader")

    def get_contest(self):
        """Produce a Contest object.

        Do what is needed (i.e. search directories and explore files
        in the location given to the constructor) to produce a Contest
        object. Also get a minimal amount of information on tasks and
        users, at least enough to produce the list of all task names
        and the list of all usernames.

        return (tuple): the Contest object and the two lists described
                        above.

        """
        raise NotImplementedError("Please extend Loader")

    def get_user(self, username):
        """Produce a User object.

        username (string): the username.

        return (User): the User object.

        """
        raise NotImplementedError("Please extend Loader")

    def get_task(self, name):
        """Produce a Task object.

        name (string): the task name.

        return (Task): the Task object.

        """
        raise NotImplementedError("Please extend Loader")

    def has_changed(self, name):
        """Detect if a Task has been changed since its last import.

        This is expected to happen by saving, at every import, some
        piece of data about the last importation time. Then, when
        has_changed() is called, such time is compared with the last
        modification time of the files describing the task. Anyway,
        the Loader may choose the heuristic better suited for its
        case.

        If this task is being imported for the first time or if the
        Loader decides not to support changes detection, just return
        True.

        name (string): the task name.

        return (bool): True if the task was changed, False otherwise.

        """
        raise NotImplementedError("Please extend Loader")
