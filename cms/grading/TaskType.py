#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import with_metaclass

import io
import logging
import os
import re
import shutil
from abc import ABCMeta, abstractmethod

from cms import config
from cms.grading import JobException
from cms.grading.Sandbox import Sandbox
from cms.grading.Job import CompilationJob, EvaluationJob
from cms.grading.steps import EVALUATION_MESSAGES, checker_step, \
    white_diff_fobj_step


logger = logging.getLogger(__name__)


EVAL_USER_OUTPUT_FILENAME = "user_output.txt"


def create_sandbox(file_cacher, name=None):
    """Create a sandbox, and return it.

    file_cacher (FileCacher): a file cacher instance.
    name (str): name to include in the path of the sandbox.

    return (Sandbox): a sandbox.

    raise (JobException): if the sandbox cannot be created.

    """
    try:
        sandbox = Sandbox(file_cacher, name=name)
    except (OSError, IOError):
        err_msg = "Couldn't create sandbox."
        logger.error(err_msg, exc_info=True)
        raise JobException(err_msg)
    return sandbox


def delete_sandbox(sandbox, success=True):
    """Delete the sandbox, if the configuration and job was ok.

    sandbox (Sandbox): the sandbox to delete.
    success (boolean): if the job succeeded (no system errors).

    """
    sandbox.cleanup()
    # If the job was not successful, we keep the sandbox around.
    if not success:
        logger.warning("Sandbox %s kept around because job did not succeeded.",
                       sandbox.outer_temp_dir)
    elif not config.keep_sandbox:
        try:
            sandbox.delete()
        except (IOError, OSError):
            err_msg = "Couldn't delete sandbox."
            logger.warning(err_msg, exc_info=True)


def is_manager_for_compilation(filename, language):
    """Return whether a manager should be copied in the compilation sandbox.

    Only return true for managers required by the language of the submission.

    filename (str): filename of the manager.
    language (Language): the programming language of the submission.

    return (bool): whether the manager is required for the compilation.

    """
    return (
        any(filename.endswith(source)
            for source in language.source_extensions)
        or any(filename.endswith(header)
               for header in language.header_extensions)
        or any(filename.endswith(obj)
               for obj in language.object_extensions))


def set_configuration_error(job, msg, *args):
    """Log a configuration error and set the correct results in the job.

    job (CompilationJob|EvaluationJob): the job currently executing
    msg (str): the message to log.
    args ([object]): formatting parameters for msg.

    """
    logger.error("Configuration error: " + msg, *args,
                 extra={"operation": job.info})

    job.success = False
    job.text = None
    if isinstance(job, CompilationJob):
        job.compilation_success = None
    elif isinstance(job, EvaluationJob):
        job.outcome = None
    else:
        raise ValueError("Unexpected type of job: %s.", job.__class__)


def check_executables_number(job, n_executables):
    """Check that the required number of executables were generated.

    Since it depends only on the task type being correct, a mismatch here
    should not happen. It might be caused (with a lot of effort) by compiling
    under one task type and evaluating under another.

    If there is a mismatch, log and store a configuration error in the job. In
    this case, callers should terminate immediately the current operation.

    job (Job): the job currently running.
    n_executables (int): the required number of executables.

    return (bool): whether there is the right number of executables in the job.

    """
    if len(job.executables) != n_executables:
        msg = "submission contains %d executables, exactly %d are expected; " \
              "consider invalidating compilations."
        set_configuration_error(job, msg, len(job.executables), n_executables)
        return False
    return True


def check_files_number(job, n_files):
    """Check that the required number of files were provided by the user.

    A mismatch here is likely caused by having had, at submission time, a wrong
    submission format for the task type.

    If there is a mismatch, log and store a configuration error in the job. In
    this case, callers should terminate immediately the current operation.

    job (Job): the job currently running.
    n_files (int): the required number of files.

    return (bool): whether there is the right number of files in the job.

    """
    if len(job.files) != n_files:
        msg = "submission contains %d files, exactly %d are required; " \
              "ensure the submission format is correct."
        set_configuration_error(job, msg, len(job.files), n_files)
        return False
    return True


def check_manager_present(job, codename):
    """Check that the required manager was provided in the dataset.

    If not provided, log and store a configuration error in the job. In this
    case, callers should terminate immediately the current operation.

    job (Job): the job currently running.
    codename (str): the codename of the required manager.

    return (bool): whether the required manager is in the job's managers.

    """
    if codename not in job.managers:
        msg = "dataset is missing manager '%s'."
        set_configuration_error(job, msg, codename)
        return False
    return True


def eval_output(file_cacher, job, checker_codename,
                user_output_path=None, user_output_digest=None,
                user_output_filename=""):
    """Evaluate ("check") a user output using a white diff or a checker.

    file_cacher (FileCacher): file cacher to use to get files.
    job (Job): the job triggering this checker run.
    checker_codename (str|None): codename of the checker amongst the manager,
        or None to use white diff.
    user_output_path (str|None): full path of the user output file, None if
        using the digest (exactly one must be non-None).
    user_output_digest (str|None): digest of the user output file, None if
        using the path (exactly one must be non-None).
    user_output_filename (str): the filename the user was expected to write to,
        or empty if stdout (used to return an error to the user).

    return (bool, float|None, [str]|None): success (true if the checker was
        able to check the solution successfully), outcome and text (both None
        if success is False).

    """
    if (user_output_path is None) == (user_output_digest is None):
        raise ValueError(
            "Exactly one of user_output_{path,digest} should be None.")

    if user_output_path is not None:
        # If a path was passed, it might not exist. First, check it does. We
        # also assume links are potential attacks, and therefore treat them
        # as if the file did not exist.
        if not os.path.exists(user_output_path) \
                or os.path.islink(user_output_path):
            return True, 0.0, [EVALUATION_MESSAGES.get("nooutput").message,
                               user_output_filename]

    if checker_codename is not None:
        if not check_manager_present(job, checker_codename):
            return False, None, None

        # Create a brand-new sandbox just for checking.
        sandbox = create_sandbox(file_cacher, name="check")
        job.sandboxes.append(sandbox.path)

        # Put user output in the sandbox.
        if user_output_path is not None:
            shutil.copyfile(user_output_path,
                            sandbox.relative_path(EVAL_USER_OUTPUT_FILENAME))
        else:
            sandbox.create_file_from_storage(EVAL_USER_OUTPUT_FILENAME,
                                             user_output_digest)

        checker_digest = job.managers[checker_codename].digest \
            if checker_codename in job.managers else None
        success, outcome, text = checker_step(
            sandbox, checker_digest, job.input, job.output,
            EVAL_USER_OUTPUT_FILENAME)

        delete_sandbox(sandbox, success)
        return success, outcome, text

    else:
        if user_output_path is not None:
            user_output_fobj = io.open(user_output_path, "rb")
        else:
            user_output_fobj = file_cacher.get_file(user_output_digest)
        with user_output_fobj:
            with file_cacher.get_file(job.output) as correct_output_fobj:
                outcome, text = white_diff_fobj_step(
                    user_output_fobj, correct_output_fobj)
        return True, outcome, text


class TaskType(with_metaclass(ABCMeta, object)):
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
