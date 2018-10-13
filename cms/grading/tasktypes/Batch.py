#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2017 Myungwoo Chun <mc.tamaki@gmail.com>
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

import logging

from cms.db import Executable
from cms.grading.ParameterTypes import ParameterTypeCollection, \
    ParameterTypeChoice, ParameterTypeString
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.steps import compilation_step, evaluation_step, \
    human_evaluation_message
from . import TaskType, \
    check_executables_number, check_files_number, check_manager_present, \
    create_sandbox, delete_sandbox, eval_output, is_manager_for_compilation


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Batch(TaskType):
    """Task type class for a unique standalone submission source, with
    comparator (or not).

    Parameters needs to be a list of three elements.

    The first element is 'grader' or 'alone': in the first
    case, the source file is to be compiled with a provided piece of
    software ('grader'); in the other by itself.

    The second element is a 2-tuple of the input file name and output file
    name. The input file may be '' to denote stdin, and similarly the
    output filename may be '' to denote stdout.

    The third element is 'diff' or 'comparator' and says whether the
    output is compared with a simple diff algorithm or using a
    comparator.

    Note: the first element is used only in the compilation step; the
    others only in the evaluation step.

    A comparator can read argv[1], argv[2], argv[3] (respectively,
    input, correct output and user output) and should write the
    outcome to stdout and the text to stderr.

    """
    # Codename of the checker, if it is used.
    CHECKER_CODENAME = "checker"
    # Basename of the grader, used in the manager filename and as the main
    # class in languages that require us to specify it.
    GRADER_BASENAME = "grader"
    # Default input and output filenames when not provided as parameters.
    DEFAULT_INPUT_FILENAME = "input.txt"
    DEFAULT_OUTPUT_FILENAME = "output.txt"

    # Constants used in the parameter definition.
    OUTPUT_EVAL_DIFF = "diff"
    OUTPUT_EVAL_CHECKER = "comparator"
    COMPILATION_ALONE = "alone"
    COMPILATION_GRADER = "grader"

    # Other constants to specify the task type behaviour and parameters.
    ALLOW_PARTIAL_SUBMISSION = False

    _COMPILATION = ParameterTypeChoice(
        "Compilation",
        "compilation",
        "",
        {COMPILATION_ALONE: "Submissions are self-sufficient",
         COMPILATION_GRADER: "Submissions are compiled with a grader"})

    _USE_FILE = ParameterTypeCollection(
        "I/O (blank for stdin/stdout)",
        "io",
        "",
        [
            ParameterTypeString("Input file", "inputfile", ""),
            ParameterTypeString("Output file", "outputfile", ""),
        ])

    _EVALUATION = ParameterTypeChoice(
        "Output evaluation",
        "output_eval",
        "",
        {OUTPUT_EVAL_DIFF: "Outputs compared with white diff",
         OUTPUT_EVAL_CHECKER: "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_COMPILATION, _USE_FILE, _EVALUATION]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a grader/comparator is used, etc...
        return "Batch"

    def __init__(self, parameters):
        super().__init__(parameters)

        # Data in the parameters.
        self.compilation = self.parameters[0]
        self.input_filename, self.output_filename = self.parameters[1]
        self.output_eval = self.parameters[2]

        # Actual input and output are the files used to store input and
        # where the output is checked, regardless of using redirects or not.
        self._actual_input = self.input_filename
        self._actual_output = self.output_filename
        if self.input_filename == "":
            self._actual_input = self.DEFAULT_INPUT_FILENAME
        if self.output_filename == "":
            self._actual_output = self.DEFAULT_OUTPUT_FILENAME

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        codenames_to_compile = []
        if self._uses_grader():
            codenames_to_compile.append(self.GRADER_BASENAME + ".%l")
        codenames_to_compile.extend(submission_format)
        executable_filename = self._executable_filename(submission_format)
        res = dict()
        for language in LANGUAGES:
            source_ext = language.source_extension
            res[language.name] = language.get_compilation_commands(
                [codename.replace(".%l", source_ext)
                 for codename in codenames_to_compile],
                executable_filename)
        return res

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        # In case the task uses a grader, we let the user provide their own
        # grader (which is usually a simplified grader provided by the admins).
        if self._uses_grader():
            return [self.GRADER_BASENAME + ".%l"]
        else:
            return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def _uses_grader(self):
        return self.compilation == self.COMPILATION_GRADER

    def _uses_checker(self):
        return self.output_eval == self.OUTPUT_EVAL_CHECKER

    @staticmethod
    def _executable_filename(codenames):
        """Return the chosen executable name computed from the codenames.

        codenames ([str]): submission format or codename of submitted files,
            may contain %l.

        return (str): a deterministic executable name.

        """
        return "_".join(sorted(codename.replace(".%l", "")
                               for codename in codenames))

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        language = get_language(job.language)
        source_ext = language.source_extension

        if not check_files_number(job, 1, or_more=True):
            return

        # Create the list of filenames to be passed to the compiler. If we use
        # a grader, it needs to be in first position in the command line, and
        # we check that it exists.
        filenames_to_compile = []
        filenames_and_digests_to_get = {}
        # The grader, that must have been provided (copy and add to
        # compilation).
        if self._uses_grader():
            grader_filename = self.GRADER_BASENAME + source_ext
            if not check_manager_present(job, grader_filename):
                return
            filenames_to_compile.append(grader_filename)
            filenames_and_digests_to_get[grader_filename] = \
                job.managers[grader_filename].digest
        # User's submitted file(s) (copy and add to compilation).
        for codename, file_ in job.files.items():
            filename = codename.replace(".%l", source_ext)
            filenames_to_compile.append(filename)
            filenames_and_digests_to_get[filename] = file_.digest
        # Any other useful manager (just copy).
        for filename, manager in job.managers.items():
            if is_manager_for_compilation(filename, language):
                filenames_and_digests_to_get[filename] = manager.digest

        # Prepare the compilation command.
        executable_filename = self._executable_filename(job.files.keys())
        commands = language.get_compilation_commands(
            filenames_to_compile, executable_filename)

        # Create the sandbox.
        sandbox = create_sandbox(file_cacher, name="compile")
        job.sandboxes.append(sandbox.get_root_path())

        # Copy required files in the sandbox (includes the grader if present).
        for filename, digest in filenames_and_digests_to_get.items():
            sandbox.create_file_from_storage(filename, digest)

        # Run the compilation.
        box_success, compilation_success, text, stats = \
            compilation_step(sandbox, commands)

        # Retrieve the compiled executables.
        job.success = box_success
        job.compilation_success = compilation_success
        job.text = text
        job.plus = stats
        if box_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                "Executable %s for %s" % (executable_filename, job.info))
            job.executables[executable_filename] = \
                Executable(executable_filename, digest)

        # Cleanup.
        delete_sandbox(sandbox, job.success, job.keep_sandbox)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        if not check_executables_number(job, 1):
            return

        # Prepare the execution
        executable_filename = next(iter(job.executables.keys()))
        language = get_language(job.language)
        main = self.GRADER_BASENAME \
            if self._uses_grader() else executable_filename
        commands = language.get_evaluation_commands(
            executable_filename, main=main)
        executables_to_get = {
            executable_filename: job.executables[executable_filename].digest
        }
        files_to_get = {
            self._actual_input: job.input
        }

        # Check which redirect we need to perform, and in case we don't
        # manage the output via redirect, the submission needs to be able
        # to write on it.
        files_allowing_write = []
        stdin_redirect = None
        stdout_redirect = None
        if self.input_filename == "":
            stdin_redirect = self._actual_input
        if self.output_filename == "":
            stdout_redirect = self._actual_output
        else:
            files_allowing_write.append(self._actual_output)

        # Create the sandbox
        sandbox = create_sandbox(file_cacher, name="evaluate")
        job.sandboxes.append(sandbox.get_root_path())

        # Put the required files into the sandbox
        for filename, digest in executables_to_get.items():
            sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in files_to_get.items():
            sandbox.create_file_from_storage(filename, digest)

        # Actually performs the execution
        box_success, evaluation_success, stats = evaluation_step(
            sandbox,
            commands,
            job.time_limit,
            job.memory_limit,
            writable_files=files_allowing_write,
            stdin_redirect=stdin_redirect,
            stdout_redirect=stdout_redirect,
            multiprocess=job.multithreaded_sandbox)

        outcome = None
        text = None

        # Error in the sandbox: nothing to do!
        if not box_success:
            pass

        # Contestant's error: the marks won't be good
        elif not evaluation_success:
            outcome = 0.0
            text = human_evaluation_message(stats)
            if job.get_output:
                job.user_output = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not sandbox.file_exists(self._actual_output):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"),
                        self._actual_output]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage.
                if job.get_output:
                    job.user_output = sandbox.get_file_to_storage(
                        self._actual_output,
                        "Output file in job %s" % job.info,
                        trunc_len=100 * 1024)

                # If just asked to execute, fill text and set dummy outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:
                    box_success, outcome, text = eval_output(
                        file_cacher, job,
                        self.CHECKER_CODENAME
                        if self._uses_checker() else None,
                        user_output_path=sandbox.relative_path(
                            self._actual_output),
                        user_output_filename=self.output_filename)

        # Fill in the job with the results.
        job.success = box_success
        job.outcome = str(outcome) if outcome is not None else None
        job.text = text
        job.plus = stats

        delete_sandbox(sandbox, job.success, job.keep_sandbox)
