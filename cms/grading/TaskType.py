#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""In this file there is the basic infrastructure from which we can
build a task type.

Basically, a task type is a class that receives a submission and knows
how to compile and evaluate it. A worker creates a task type to work
on a submission, and all low-level details on how to implement the
compilation and the evaluation are contained in the task type class.

"""

import re
import traceback

from cms import config, logger
from cms.grading import JobException
from cms.grading.Sandbox import Sandbox
from cms.grading.Job import CompilationJob, EvaluationJob


## Sandbox lifecycle. ##

def create_sandbox(task_type):
    """Create a sandbox, and return it.

    task_type (TaskType): a task type instance.

    return (Sandbox): a sandbox.

    raise: JobException

    """
    try:
        sandbox = Sandbox(task_type.file_cacher)
    except (OSError, IOError):
        err_msg = "Couldn't create sandbox."
        logger.error("%s\n%s" % (err_msg, traceback.format_exc()))
        raise JobException(err_msg)
    return sandbox


def delete_sandbox(sandbox):
    """Delete the sandbox, if the configuration allows it to be
    deleted.

    sandbox (Sandbox): the sandbox to delete.

    """
    if not config.keep_sandbox:
        try:
            sandbox.delete()
        except (IOError, OSError):
            logger.warning("Couldn't delete sandbox.\n%s",
                           traceback.format_exc())


class TaskType:
    """Base class with common operation that (more or less) all task
    types must do sometimes.

    - finish_(compilation, evaluation_testcase, evaluation): these
      finalize the given operation, writing back to the submission the
      new information, and deleting the sandbox if needed;

    - *_sandbox_*: these are utility to create and delete the sandbox,
       and to ask it to do some operation. If the operation fails, the
       sandbox is deleted.

    - compile, evaluate_testcase, evaluate: these actually do the
      operations; must be overloaded.

    """
    # If ALLOW_PARTIAL_SUBMISSION is True, then we allow the user to
    # submit only some of the required files; moreover, we try to fill
    # the non-provided files with the one in the previous submission.
    ALLOW_PARTIAL_SUBMISSION = False

    # A list of all the accepted parameters for this task type.
    # Each item is an instance of TaskTypeParameter.
    ACCEPTED_PARAMETERS = []

    @classmethod
    def parse_handler(cls, handler, prefix):
        """Ensure that the parameters list template agrees with the
        parameters actually passed.

        handler (Class): the Tornado handler with the parameters.
        prefix (string): the prefix of the parameter names in the
                         handler.

        return (list): parameters list correctly formatted, or
                       ValueError if the parameters are not correct.

        """
        new_parameters = []
        for parameter in cls.ACCEPTED_PARAMETERS:
            try:
                new_value = parameter.parse_handler(handler, prefix)
                new_parameters.append(new_value)
            except ValueError as error:
                raise ValueError("Invalid parameter %s: %s."
                                 % (parameter.name, error.message))
        return new_parameters

    def __init__(self, job, file_cacher):
        """

        job (CompilationJob or EvaluationJob): the job describing what
                                               to do
        file_cacher (FileCacher): a FileCacher object to retrieve
                                  files from FS.

        """
        self.job = job
        self.file_cacher = file_cacher
        self.result = {}

        self.worker_shard = None
        self.sandbox_paths = ""

        # If ignore_job is True, we conclude as soon as possible.
        self.ignore_job = False

    @property
    def name(self):
        """Returns the name of the TaskType.

        Returns a human-readable name that is shown to the user in CWS
        to describe this TaskType.

        return (str): the name

        """
        # de-CamelCase the name, capitalize it and return it
        return re.sub("([A-Z])", " \g<1>",
                      self.__class__.__name__).strip().capitalize()

    testable = True

    def get_compilation_commands(self, submission_format):
        """Return the compilation command for all supported languages

        submission_format (list of str): the list of files provided by the
            user that have to be compiled (the compilation command may
            contain references to other files like graders, stubs, etc...);
            they may contain the string "%l" as a language-wildcard.
        return (dict of list of str): a dict whose keys are language codes
            and whose values are lists of compilation commands for that
            language (this is because the task type may require multiple
            compilations, e.g. encoder and decoder); return None if no
            compilation is required (e.g. output only).

        """
        raise NotImplementedError("Please subclass this class.")

    def get_user_managers(self):
        """Return the managers that must be provided by the user when
        requesting a user test.

        return (list of str): a list of filenames (they may include a
                              '%l' as a "language wildcard").

        """
        raise NotImplementedError("Please subclass this class.")

    def get_auto_managers(self):
        """Return the managers that must be provided by the
        EvaluationService (picking them from the Task) when compiling
        or evaluating a user test.

        return (list of str): a list of filenames (they may include a
                             '%l' as a "language wildcard").

        """
        raise NotImplementedError("Please subclass this class.")

    def compile(self):
        """Tries to compile the specified submission.

        It returns True when *our infrastracture* is successful (i.e.,
        the actual compilation may success or fail), and False when
        the compilation fails because of environmental problems
        (trying again to compile the same submission in a sane
        environment should lead to returning True).

        return (bool): success of operation.

        """
        raise NotImplementedError("Please subclass this class.")

    def evaluate_testcase(self, test_number):
        """Perform the evaluation of a single testcase.

        test_number (int): the number of the testcase to test.

        return (bool): True if the evaluation was successful.

        """
        raise NotImplementedError("Please subclass this class.")

    def evaluate(self):
        """Tries to evaluate the specified submission.

        It returns True when *our infrastracture* is successful (i.e.,
        the actual program may score or not), and False when the
        evaluation fails because of environmental problems (trying
        again to compile the same submission in a sane environment
        should lead to returning True).

        A default implementation which should suit most task types is
        provided.

        return (bool): success of operation.

        """
        for test_number in xrange(len(self.job.testcases)):
            success = self.evaluate_testcase(test_number)
            if not success or self.ignore_job:
                self.job.success = False
                return
        self.job.success = True

    def execute_job(self):
        """Call compile() or execute() depending on the job passed
        when constructing the TaskType.

        """
        if isinstance(self.job, CompilationJob):
            return self.compile()
        elif isinstance(self.job, EvaluationJob):
            return self.evaluate()
        else:
            raise ValueError("The job isn't neither CompilationJob "
                             "or EvaluationJob")
