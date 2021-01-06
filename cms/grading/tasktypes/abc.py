#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from abc import ABCMeta, abstractmethod

from cms.grading.Job import CompilationJob, EvaluationJob


class TaskType(metaclass=ABCMeta):
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
    ALLOW_SUBMISSION = True

    # A list of all the accepted parameters for this task type.
    # Each item is an instance of TaskTypeParameter.
    ACCEPTED_PARAMETERS = []

    @classmethod
    def parse_handler(cls, handler, prefix):
        """Ensure that the parameters list template agrees with the
        parameters actually passed.

        handler (type): the Tornado handler with the parameters.
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
                                 % (parameter.name, error))
        return new_parameters

    def __init__(self, parameters):
        """Instantiate a new TaskType with the given parameters.

        parameters (list): a list of data structures that matches the
            format described in ACCEPTED_PARAMETERS (they often come
            from Dataset.task_type_parameters and, in that case, they
            have to be already decoded from JSON).

        """
        self.parameters = parameters
        self.validate_parameters()

    def validate_parameters(self):
        """Validate the parameters syntactically.

        raise (ValueError): if the parameters are malformed.

        """
        if not isinstance(self.parameters, list):
            raise ValueError(
                "Task type parameters for %s are not a list" % self.__class__)

        if len(self.parameters) != len(self.ACCEPTED_PARAMETERS):
            raise ValueError(
                "Task type %s should have %s parameters, received %s" %
                (self.__class__,
                 len(self.ACCEPTED_PARAMETERS),
                 len(self.parameters)))

        for value, parameter in zip(self.parameters, self.ACCEPTED_PARAMETERS):
            parameter.validate(value)

    @property
    def name(self):
        """Returns the name of the TaskType.

        Returns a human-readable name that is shown to the user in CWS
        to describe this TaskType.

        return (str): the name

        """
        # de-CamelCase the name, capitalize it and return it
        return re.sub("([A-Z])", r" \g<1>",
                      self.__class__.__name__).strip().capitalize()

    # Whether user tests are enabled for task of this type (provided they are
    # enabled in the contest).
    testable = True

    @abstractmethod
    def get_compilation_commands(self, submission_format):
        """Return the compilation commands for all supported languages

        submission_format ([string]): the list of files provided by the
            user that have to be compiled (the compilation command may
            contain references to other files like graders, stubs, etc...);
            they may contain the string ".%l" as a language-wildcard.

        return ({string: [[string]]}|None): for each language (indexed
            by its name) provide a list of commands, each as a list of
            tokens. That is because some languages may require
            multiple operations to compile or because some task types
            may require multiple independent compilations
            (e.g. encoder and decoder); return None if no compilation
            is required (e.g. output only).

        """
        pass

    @abstractmethod
    def get_user_managers(self):
        """Return the managers that must be provided by the user when
        requesting a user test.

        return (list of str): a list of filenames (they may include a
                              '%l' as a "language wildcard").

        """
        pass

    @abstractmethod
    def get_auto_managers(self):
        """Return the managers that must be provided by the
        EvaluationService (picking them from the Task) when compiling
        or evaluating a user test.

        return (list of str): a list of filenames (they may include a
                             '%l' as a "language wildcard").

        """
        pass

    @abstractmethod
    def compile(self, job, file_cacher):
        """Try to compile the given CompilationJob.

        Set job.success to True when *our infrastracture* is successful
        (i.e. the compilation may succeed or fail), and to False when
        the compilation fails because of environmental problems (trying
        again to compile the same submission in a sane environment
        should lead to True).

        job (CompilationJob): the data structure that contains details
                              about the work that has to be done and
                              that will hold its results.
        file_cacher (FileCacher): the file cacher to use to obtain the
                                  required files and to store the ones
                                  that are produced.

        """
        pass

    @abstractmethod
    def evaluate(self, job, file_cacher):
        """Try to evaluate the given EvaluationJob.

        Set job.success to True when *our infrastracture* is successful
        (i.e. the actual program may score or not), and to False when
        the evaluation fails because of environmental problems (trying
        again to compile the same submission in a sane environment
        should lead to True).

        job (EvaluationJob): the data structure that contains details
                             about the work that has to be done and
                             that will hold its results.
        file_cacher (FileCacher): the file cacher to use to obtain the
                                  required files and to store the ones
                                  that are produced.

        """
        pass

    def execute_job(self, job, file_cacher):
        """Call compile() or execute() depending on the job passed
        when constructing the TaskType.

        """
        if isinstance(job, CompilationJob):
            self.compile(job, file_cacher)
        elif isinstance(job, EvaluationJob):
            self.evaluate(job, file_cacher)
        else:
            raise ValueError("The job isn't neither CompilationJob "
                             "or EvaluationJob")
