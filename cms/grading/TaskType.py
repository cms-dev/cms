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


## Automatic white diff. ##

WHITES = " \t\n\r"


def white_diff_canonicalize(string):
    """Convert the input string to a canonical form for the white diff
    algorithm; that is, the strings a and b are mapped to the same
    string by white_diff_canonicalize() if and only if they have to be
    considered equivalent for the purposes of the white_diff
    algorithm.

    More specifically, this function strips all the leading and
    trailing whitespaces from s and collapse all the runs of
    consecutive whitespaces into just one copy of one specific
    whitespace.

    string (string): the string to canonicalize.
    return (string): the canonicalized string.

    """
    # Replace all the whitespaces with copies of " ", making the rest
    # of the algorithm simpler
    for char in WHITES[1:]:
        string = string.replace(char, WHITES[0])

    # Split the string according to " ", filter out empty tokens and
    # join again the string using just one copy of the first
    # whitespace; this way, runs of more than one whitespaces are
    # collapsed into just one copy.
    string = WHITES[0].join([x for x in string.split(WHITES[0])
                             if x != ''])
    return string


def white_diff(output, res):
    """Compare the two output files. Two files are equal if for every
    integer i, line i of first file is equal to line i of second
    file. Two lines are equal if they differ only by number or type of
    whitespaces.

    Note that trailing lines composed only of whitespaces don't change
    the 'equality' of the two files. Note also that by line we mean
    'sequence of characters ending with \n or EOF and beginning right
    after BOF or \n'. In particular, every line has *at most* one \n.

    output (file): the first file to compare.
    res (file): the second file to compare.
    return (bool): True if the two file are equal as explained above.

    """

    while True:
        lout = output.readline()
        lres = res.readline()

        # Both files finished: comparison succeded
        if lres == '' and lout == '':
            return True

        # Only one file finished: ok if the other contains only blanks
        elif lres == '' or lout == '':
            lout = lout.strip(WHITES)
            lres = lres.strip(WHITES)
            if lout != '' or lres != '':
                return False

        # Both file still have lines to go: ok if they agree except
        # for the number of whitespaces
        else:
            lout = white_diff_canonicalize(lout)
            lres = white_diff_canonicalize(lres)
            if lout != lres:
                return False


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

    def _append_sandbox(self, path):
        """Add path to self.sandbox_paths in the correct way.

        path (str): the path of a new sandbox to record in the
                    dabatase.

        """
        if self.sandbox_paths == "":
            self.sandbox_paths = path
        else:
            paths = self.sandbox_paths.split(":")
            if path not in paths:
                self.sandbox_paths = ":".join(paths + [path])

    def finish_compilation(self, success, compilation_success=False,
                           text="", to_log=None):
        """Finalize the operation of compilation and build the
        dictionary to return to ES.

        success (bool): if the operation was successful (i.e., if cms
                        did everything in the right way).
        compilation_success (bool): if success = True, this is whether
                                    the compilation was successful
                                    (i.e., if the submission managed
                                    to compile).
        text (string): if success is True, stdout and stderr of the
                       compiler, or a message explaining why it
                       compilation_success is False.
        to_log (string): inform us that an unexpected event has
                         happened.

        return (dict): result collected during the evaluation.

        """
        if to_log is not None:
            logger.warning(to_log)
        self.result["success"] = success

        if success:
            if compilation_success:
                self.result["compilation_outcome"] = "ok"
            else:
                self.result["compilation_outcome"] = "fail"

            try:
                self.result["compilation_text"] = text.decode("utf-8")
            except UnicodeDecodeError:
                self.result["compilation_text"] = \
                    "Cannot decode compilation text."
                logger.error("Unable to decode UTF-8 for string %s." % text)

            self.result["compilation_shard"] = self.worker_shard
            self.result["compilation_sandbox"] = self.sandbox_paths
            self.sandbox_paths = ""

        self.ignore_job = False
        return self.result

    def finish_evaluation_testcase(self, test_number, success,
                                   outcome=0, text="", plus=None,
                                   to_log=None):
        """Finalize the operation of evaluating the submission on a
        testcase. Fill the information in the submission.

        test_number (int): number of testcase.
        success (bool): if the operation was successful.
        outcome (float): the outcome obtained by the submission on the
                         testcase.
        text (string): the reason of failure of the submission (if
                       any).
        plus (dict): additional information extracted from the logs of
                     the 'main' evaluation step - in particular,
                     memory and time information.
        to_log (string): inform us that an unexpected event has
                         happened.

        return (bool): success.

        """
        if to_log is not None:
            logger.warning(to_log)
        if "evaluations" not in self.result:
            self.result["evaluations"] = {}
        obj = self.result["evaluations"]
        obj[test_number] = {"success": success}
        if success:
            obj[test_number]["text"] = text
            obj[test_number]["outcome"] = outcome
            obj[test_number]["evaluation_shard"] = self.worker_shard
            obj[test_number]["evaluation_sandbox"] = self.sandbox_paths
            self.sandbox_paths = ""

        if plus is None:
            plus = {}
        for info in ["memory_used",
                     "execution_time",
                     "execution_wall_clock_time"]:
            obj[test_number][info] = plus.get(info, None)

        return success

    def build_response(self):
        """Build the `result' object to be returned back to
        EvaluationService. This metod is temporary: definitively, the
        Worker should return a reference to the Job itself, leaving to
        EvaluationService the task of extracting interesting data and
        pushing them to the Submission or wherever they belong to.

        """
        result = {}

        # Compilation
        if isinstance(self.job, CompilationJob):
            result['success'] = self.job.success
            if self.job.compilation_success:
                result['compilation_outcome'] = 'ok'
            else:
                result['compilation_outcome'] = 'fail'
            result['compilation_text'] = self.job.text
            result['compilation_shard'] = self.job.shard
            result['compilation_sandbox'] = ":".join(self.job.sandboxes)
            result['executables'] = self.job.executables.items()

        # Evaluation
        elif isinstance(self.job, EvaluationJob):
            result['success'] = self.job.success
            result['evaluations'] = {}
            for testcase in self.job.evaluations:
                evaluation = {}
                evaluation['text'] = \
                    self.job.evaluations[testcase]['text']
                evaluation['outcome'] = \
                    self.job.evaluations[testcase]['outcome']
                evaluation['evaluation_shard'] = self.job.shard
                evaluation['evaluation_sandbox'] = ":".join(
                    self.job.evaluations[testcase]['sandboxes'])
                for info in ['memory_used',
                             'execution_time',
                             'execution_wall_clock_time']:
                    evaluation[info] = \
                        self.job.evaluations[testcase]['plus'].get(info, None)
                result['evaluations'][testcase] = evaluation

        else:
            raise ValueError("The job isn't neither CompilationJob "
                             "or EvaluationJob")
        return result

    def finish_evaluation(self, success, to_log=None):
        """Finalize the operation of evaluating. Currently there is
        nothing to do.

        success (bool): if the evaluation was successful.
        to_log (string): inform us that an unexpected event has
                         happened.

        return (dict): result collected during the evaluation.

        """
        if to_log is not None:
            logger.warning(to_log)

        self.result["success"] = success
        if "evaluations" not in self.result:
            self.result["evaluations"] = {}

        self.ignore_job = False
        return self.result

    def white_diff_step(self, sandbox, output_filename,
                        correct_output_filename, files_to_get):
        """This is like an evaluation_step with final = True (i.e.,
        returns an outcome and a text). The outcome is 1.0 if and only
        if the two output files corresponds up to white_diff, 0.0
        otherwise.

        sandbox (Sandbox): the sandbox we consider.
        output_filename (string): the filename of user's output in the
                                  sandbox.
        correct_output_filename (string): the same with admin output.
        files_to_get (dict): files to get from storage.
        return (bool, float, string): see evaluation_step.

        """
        # Record the usage of the sandbox.
        self._append_sandbox(sandbox.path)

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)
        if sandbox.file_exists(output_filename):
            out_file = sandbox.get_file(output_filename)
            res_file = sandbox.get_file("res.txt")
            if white_diff(out_file, res_file):
                outcome = 1.0
                text = "Output is correct"
            else:
                outcome = 0.0
                text = "Output isn't correct"
        else:
            outcome = 0.0
            text = "Evaluation didn't produce file %s" % (output_filename)
        return True, outcome, text

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
