#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
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


class Loader:
    """Base class for deriving loaders.

    Each loader must extend this class and support the following
    access pattern:

      * The class methods short_name(), description() and detect() can
        be called at any time.

      * Once a loader is instatiated, get_contest() can be called on
        it, only once.

      * After get_contest() has been called, at the caller's will,
        get_task() and get_user() can be called, in any order and for
        how many times the caller want. The resource intensive
        operations that are not needed for get_contest() are better
        left in get_task() or get_user(), so that no time is wasted if
        the caller isn't interested in users or tasks.

    """

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
    def short_name(cls):
        """Short name of this loader, meant to be a unique identifier.

        """
        raise NotImplementedError("Please extend Loader")

    @classmethod
    def description(cls):
        """Description of this loader, meant to be human readable.

        """
        raise NotImplementedError("Please extend Loader")

    @classmethod
    def detect(cls, path):
        """Detect whether this loader is able to interpret the given
        path. If the loader chooses to not support autodetection, just
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
        object. Also get a minimal amount of information on users and
        tasks, at least enough to produce two lists of dicts, one for
        each user/task in the contest, containing the username/user and
        every other information you think is useful. These dicts will
        then be given as arguments to get_user/get_task that have to
        produce fully-featured User/Task objects.

        return (tuple): Contest object and two lists of dicts. Each
                        element of the first list has to contain a
                        "username" item whereas the ones in the second
                        have to contain a "name" item.

        """
        raise NotImplementedError("Please extend Loader")

    def get_user(self, conf):
        """Produce a User object.

        Given an object of the first list returned by get_contest,
        construct a full User object and return it. Access the data on
        the filesystem if needed.

        return (User): the User object corresponding to the given dict.

        """
        raise NotImplementedError("Please extend Loader")

    def get_task(self, conf):
        """Produce a Task object.

        Given an object of the second list returned by get_contest,
        construct a full Task object (with all its dependencies) and
        return it. Access the data on the filesystem if needed.

        return (Task): the Task object corresponding to the given dict.

        """
        raise NotImplementedError("Please extend Loader")
