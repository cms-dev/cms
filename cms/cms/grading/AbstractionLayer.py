#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""Abstraction layer for treating tasks and submissions independently
from them being on the filesystem or in a database.

"""


class AbstractTask:
    """Represents some aspect of a task, independently from it being
    on the filesystem or in a database.

    """

    def get_input(self, num, file_obj):
        """Retrieve the specified input file from the task and write it
        to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        raise NotImplementedError("Please subclass AbstractTask")

    def get_output(self, num, file_obj):
        """Retrieve the specified output file from the task and write
        it to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        raise NotImplementedError("Please subclass AbstractTask")

    def get_manager(self, filename, file_obj):
        """Retrieve the specified manager from the task and write it to
        the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        raise NotImplementedError("Please subclass AbstractTask")

    def get_attachment(self, filename, file_obj):
        """Retrieve the specified attachment from the task and write it
        to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        raise NotImplementedError("Please subclass AbstractTask")


class AbstractTaskFromDB(AbstractTask):

    def __init__(self, task, FC):
        """Create an AbstractTask that shadows the specified task
        object from the database.

        """
        self.task = task
        self.FC = FC

    def get_input(self, num, file_obj):
        """Retrieve the specified input file from the task and write it
        to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        try:
            self.FC.get_file(self.task.testcases[num].input, file_obj=file_obj)
            return True
        except IndexError:
            return False

    def get_output(self, num, file_obj):
        """Retrieve the specified output file from the task and write
        it to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        try:
            self.FC.get_file(self.task.testcases[num].output, file_obj=file_bj)
            return True
        except IndexError:
            return False

    def get_manager(self, filename, file_obj):
        """Retrieve the specified manager from the task and write it to
        the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        try:
            self.FC.get_file(self.task.managers[filename].digest,
                             file_obj=file_obj)
            return True
        except KeyError:
            return False

    def get_attachment(self, filename, file_obj):
        """Retrieve the specified attachment from the task and write it
        to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        try:
            self.FC.get_file(self.task.attachments[filename].digest,
                             file_obj=file_obj)
            return True
        except KeyError:
            return False


class AbstractSubmission:
    """Represents some aspect of a submission, independently from it
    being on the filesystem or in a database.

    """

    def get_task(self):
        """Return the AbstractTask linked to this AbstractSubmissions.

        """
        raise NotImplementedError("Please subclass AbstractSubmission")

    def get_language(self):
        """Return the language of this submission.

        """
        raise NotImplementedError("Please subclass AbstractSubmission")

    def get_file(self, filename, file_obj):
        """Retrieve the specified submitted file from the submission
        and write it to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        raise NotImplementedError("Please subclass AbstractSubmission")

    def get_executable(self, filename, file_obj):
        """Retrieve the specified compiled executable from the
        submission and write it to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        raise NotImplementedError("Please subclass AbstractSubmission")

    def put_executable(self, filename, file_obj, description=""):
        """Add the specified compiled executable to the submission,
        overwriting, if necessary, the previous entry with the same
        filename. The file is read from the file-like object file_obj.

        """
        raise NotImplementedError("Please subclass AbstractSubmission")


class AbstractSubmissionFromDB:

    def __init__(self, submission, FC):
        """Create an AbstractSubmission that shadows the specified
        submission object from the database.

        """
        self.submission = submission
        self.FC = FC

    def get_task(self):
        """Return the AbstractTask linked to this AbstractSubmissions.

        """
        return AbstractTaskFromDB(self.submission.task)

    def get_language(self):
        """Return the language of this submission.

        """
        return self.submission.language

    def get_file(self, filename, file_obj):
        """Retrieve the specified manager from the task and write it to
        the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        try:
            self.FC.get_file(self.submission.files[filename].digest,
                             file_obj=file_obj)
            return True
        except KeyError:
            return False

    def get_executable(self, filename, file_obj):
        """Retrieve the specified compiled executable from the
        submission and write it to the file-like object file_obj.

        Returns True if the file was found, False otherwise.

        """
        try:
            self.FC.get_file(self.submission.executables[filename].digest,
                             file_obj=file_obj)
            return True
        except KeyError:
            return False

    def put_executable(self, filename, file_obj, description=""):
        """Add the specified compiled executable to the submission,
        overwriting, if necessary, the previous entry with the same
        filename. The file is read from the file-like object file_obj.

        """
        digest = self.FC.put_file(self, description=description,
                                  file_obj=file_obj)
        if filename in self.submission.executables:
            del self.submission.executables[filename]
        self.submission.get_session().add(Executable(digest, filename,
                                                     self.submission))
