#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2014-2015 William Di Luigi <williamdiluigi@gmail.com>
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

from abc import ABCMeta, abstractmethod


class BaseLoader(metaclass=ABCMeta):
    """Base class for deriving loaders.

    Each loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

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

    @staticmethod
    @abstractmethod
    def detect(path):
        """Detect whether this loader is able to interpret a path.

        If the loader chooses to not support autodetection, just
        always return False.

        path (string): the path to scan.

        return (bool): True if the loader is able to interpret the
                       given path.

        """
        pass


class TaskLoader(BaseLoader):
    """Base class for deriving task loaders.

    Each task loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

      * Once a loader is instatiated, get_task() can be called on it,
        for how many times the caller want.

    """

    def __init__(self, path, file_cacher):
        super().__init__(path, file_cacher)

    @abstractmethod
    def get_task(self, get_statement):
        """Produce a Task object.

        get_statement (boolean): whether the statement should be imported.

        return (Task): the Task object.

        """
        pass

    @abstractmethod
    def task_has_changed(self):
        """Detect if the task has been changed since its last import.

        This is expected to happen by saving, at every import, some
        piece of data about the last importation time. Then, when
        task_has_changed() is called, such time is compared with the
        last modification time of the files describing the task. Anyway,
        the TaskLoader may choose the heuristic better suited for its
        case.

        If this task is being imported for the first time or if the
        TaskLoader decides not to support changes detection, just return
        True.

        return (bool): True if the task was changed, False otherwise.

        """
        pass


class UserLoader(BaseLoader):
    """Base class for deriving user loaders.

    Each user loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

      * Once a loader is instatiated, get_user() can be called on it,
        for how many times the caller want.

    """

    def __init__(self, path, file_cacher):
        super().__init__(path, file_cacher)

    @abstractmethod
    def get_user(self):
        """Produce a User object.

        return (User): the User object.

        """
        pass

    @abstractmethod
    def user_has_changed(self):
        """Detect if the user has been changed since its last import.

        This is expected to happen by saving, at every import, some
        piece of data about the last importation time. Then, when
        user_has_changed() is called, such time is compared with the
        last modification time of the files describing the user. Anyway,
        the UserLoader may choose the heuristic better suited for its
        case.

        If this user is being imported for the first time or if the
        UserLoader decides not to support changes detection, just return
        True.

        return (bool): True if the user was changed, False otherwise.

        """
        pass


class TeamLoader(BaseLoader):
    """Base class for deriving team loaders.

    Each team loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

      * Once a loader is instatiated, get_team() can be called on it,
        for how many times the caller want.

    """

    def __init__(self, path, file_cacher):
        super().__init__(path, file_cacher)

    @abstractmethod
    def get_team(self):
        """Produce a Team object.

        return (Team): the Team object.

        """
        pass

    @abstractmethod
    def team_has_changed(self):
        """Detect if the team has been changed since its last import.

        This is expected to happen by saving, at every import, some
        piece of data about the last importation time. Then, when
        team_has_changed() is called, such time is compared with the
        last modification time of the files describing the team. Anyway,
        the TeamLoader may choose the heuristic better suited for its
        case.

        If this team is being imported for the first time or if the
        TeamLoader decides not to support changes detection, just return
        True.

        return (bool): True if the team was changed, False otherwise.

        """
        pass


class ContestLoader(BaseLoader):
    """Base class for deriving contest loaders.

    Each contest loader must extend this class and support the following
    access pattern:

      * The class method detect() can be called at any time.

      * Once a loader is instatiated, get_contest() can be called on it,
        for how many times the caller want.

    """

    def __init__(self, path, file_cacher):
        super().__init__(path, file_cacher)

    @abstractmethod
    def get_contest(self):
        """Produce a Contest object.

        Do what is needed (i.e. search directories and explore files
        in the location given to the constructor) to produce a Contest
        object. Also get a minimal amount of information on tasks and
        participations, at least enough to produce a list of all task
        names and a list of dict objects that will represent all the
        participations in the contest (each participation should have
        at least the "username" field).

        return (tuple): the Contest object and the two lists described
                        above.

        """
        pass

    @abstractmethod
    def contest_has_changed(self):
        """Detect if the contest has been changed since its last import.

        This is expected to happen by saving, at every import, some
        piece of data about the last importation time. Then, when
        contest_has_changed() is called, such time is compared with the
        last modification time of the files describing the contest.
        Anyway the ContestLoader may choose the heuristic better suited
        for its case.

        If this contest is being imported for the first time or if the
        ContestLoader decides not to support changes detection, just
        return True.

        return (bool): True if the contset was changed, False otherwise.

        """
        pass

    @abstractmethod
    def get_task_loader(self, taskname):
        """Return a loader class for the task with the given name.

        taskname (string): name of the task.

        return (TaskLoader): loader for the task with name taskname.

        """
        pass
