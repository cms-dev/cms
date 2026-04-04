#!/usr/bin/env python3
import tempfile

import json
import logging
import os
import sys
import subprocess

from cms import config
from cms.db import Executable
from cms.grading.ParameterTypes import (
    ParameterTypeChoice,
    ParameterTypeInt,
    ParameterTypeFloat,
    ParameterTypeBool,
)
from cms.grading.languagemanager import get_language, LANGUAGES
from cms.grading.steps import compilation_step
from .abc import TaskType
from .util import (
    check_executables_number,
    check_manager_present,
    create_sandbox,
    delete_sandbox,
    is_manager_for_compilation,
)

logger = logging.getLogger(__name__)


class Interactive(TaskType):
    """Task type class for interactive tasks where a controller dynamically
    spawns solution instances.
    """

    CONTROLLER_FILENAME = "controller"
    COMPILATION_ALONE = "alone"
    COMPILATION_STUB = "stub"
    STUB_BASENAME = "stub"

    _COMPILATION = ParameterTypeChoice(
        "Compilation",
        "compilation",
        "",
        {
            COMPILATION_ALONE: "Submissions are self-sufficient",
            COMPILATION_STUB: "Submissions are compiled with a stub",
        },
    )

    _PROCESS_LIMIT = ParameterTypeInt(
        "Process limit",
        "process_limit",
        "Maximum number of solution instances the controller can spawn",
    )

    _CONCURRENT = ParameterTypeBool(
        "Concurrent solutions",
        "concurrent",
        "Whether solutions are assumed to be run concurrently or not",
    )

    _CONTROLLER_MEMORY_LIMIT = ParameterTypeFloat(
        "Controller memory limit (MB)",
        "controller_memory_limit",
        "Maximum memory (in MB) that the controller can use",
    )

    _CONTROLLER_TIME_LIMIT = ParameterTypeFloat(
        "Controller time limit (s)",
        "controller_time_limit",
        "Maximum CPU time (in seconds) that the controller can use",
    )

    _CONTROLLER_WALL_LIMIT = ParameterTypeFloat(
        "Controller wall time limit (s)",
        "controller_wall_limit",
        "Maximum wall time (in seconds) that the controller can use",
    )

    ACCEPTED_PARAMETERS = [
        _PROCESS_LIMIT,
        _COMPILATION,
        _CONCURRENT,
        _CONTROLLER_MEMORY_LIMIT,
        _CONTROLLER_TIME_LIMIT,
        _CONTROLLER_WALL_LIMIT,
    ]

    def __init__(self, parameters):
        super().__init__(parameters)
        self.process_limit = self.parameters[0]
        self.compilation_type = self.parameters[1]
        self.concurrent = self.parameters[2]
        # Note: isolate wants the memory limit in *bytes*!
        self.controller_memory_limit = self.parameters[3] * 2**20
        self.controller_time_limit = self.parameters[4]
        self.controller_wall_limit = self.parameters[5]

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        codenames_to_compile = []
        if self._uses_stub():
            codenames_to_compile.append(self.STUB_BASENAME + ".%l")
        codenames_to_compile.extend([x for x in submission_format if x.endswith(".%l")])
        res = dict()
        for language in LANGUAGES:
            source_ext = language.source_extension
            executable_filename = self._executable_filename(submission_format, language)
            res[language.name] = language.get_compilation_commands(
                [
                    codename.replace(".%l", source_ext)
                    for codename in codenames_to_compile
                ],
                executable_filename,
            )
        return res

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        if self._uses_stub():
            return [self.STUB_BASENAME + ".%l"]
        else:
            return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def _uses_stub(self) -> bool:
        return self.compilation_type == self.COMPILATION_STUB

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        if not check_executables_number(job, 0):
            return

        language = get_language(job.language)

        source_ext = language.source_extension
        filenames_to_compile = []
        filenames_and_digests_to_get = {}

        # Grader (if needed).
        if self._uses_stub():
            grader_filename = self.STUB_BASENAME + source_ext
            if not check_manager_present(job, grader_filename):
                return
            filenames_to_compile.append(grader_filename)
            filenames_and_digests_to_get[grader_filename] = job.managers[
                grader_filename
            ].digest

        # User's submitted file(s).
        for codename, file_ in job.files.items():
            filename = codename.replace(".%l", source_ext)
            filenames_to_compile.append(filename)
            filenames_and_digests_to_get[filename] = file_.digest

        # Any other useful manager (just copy).
        for filename, manager in job.managers.items():
            if is_manager_for_compilation(filename, language):
                filenames_and_digests_to_get[filename] = manager.digest

        executable_filename = self._executable_filename(job.files.keys(), language)
        commands = language.get_compilation_commands(
            filenames_to_compile, executable_filename
        )

        sandbox = create_sandbox(0, file_cacher, name="compile")
        job.sandboxes.append(sandbox.get_root_path())

        for filename, digest in filenames_and_digests_to_get.items():
            sandbox.create_file_from_storage(filename, digest, file_cacher)

        box_success, compilation_success, text, stats = compilation_step(
            sandbox, commands
        )

        job.success = box_success
        job.compilation_success = compilation_success
        job.text = text
        job.plus = stats
        if box_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                file_cacher,
                "Executable %s for %s" % (executable_filename, job.info),
            )
            job.executables[executable_filename] = Executable(
                executable_filename, digest
            )

        delete_sandbox(sandbox, job)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        if not check_executables_number(job, 1):
            return
        executable_filename = next(iter(job.executables.keys()))
        executable_digest = job.executables[executable_filename].digest

        if not check_manager_present(job, self.CONTROLLER_FILENAME):
            return
        controller_digest = job.managers[self.CONTROLLER_FILENAME].digest

        language = get_language(job.language)
        controller_command = ["./%s" % self.CONTROLLER_FILENAME]
        solution_commands = language.get_evaluation_commands(executable_filename)

        # We need absolute paths for the keeper.
        with tempfile.TemporaryDirectory(
            dir=config.global_.temp_dir, prefix="interactive"
        ) as tempdir:
            with open(os.path.join(tempdir, self.CONTROLLER_FILENAME), "wb") as f:
                file_cacher.get_file_to_fobj(controller_digest, f)

            with open(os.path.join(tempdir, executable_filename), "wb") as f:
                file_cacher.get_file_to_fobj(executable_digest, f)

            with open(os.path.join(tempdir, "input.txt"), "wb") as f:
                file_cacher.get_file_to_fobj(job.input, f)

            keeper_config = {
                "controller_command": controller_command,
                "solution_commands": solution_commands,
                "controller_files": [
                    self.CONTROLLER_FILENAME,
                    "input.txt",
                ],
                "solution_files": [executable_filename],
                "controller_wall_limit": self.controller_wall_limit,
                "controller_time_limit": self.controller_time_limit,
                "controller_memory_limit": self.controller_memory_limit,
                "solution_time_limit": job.time_limit,
                "solution_memory_limit": job.memory_limit,
                "process_limit": self.process_limit,
                "concurrent": self.concurrent,
                "temp_dir": tempdir,
                "shard": file_cacher.service.shard if file_cacher.service else None,
                "delete_sandbox": not (job.keep_sandbox or job.archive_sandbox),
            }

            keeper_path = os.path.join(
                os.path.dirname(__file__), "interactive_keeper.py"
            )

            p = subprocess.Popen(
                [sys.executable, keeper_path, json.dumps(keeper_config)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
            stdout, _ = p.communicate(timeout=self.controller_wall_limit * 2)

            KEEPER_ERROR_MESSAGE = "Internal error in interactive keeper"

            if p.returncode != 0:
                logger.error("Keeper failed with return code %d", p.returncode)
                logger.error(
                    "Keeper output: %s", stdout.decode("utf-8", errors="replace")
                )
                job.success = False
                job.text = [KEEPER_ERROR_MESSAGE]
                return

            try:
                stdout_str = stdout.decode("utf-8")
                result = json.loads(stdout_str)
                logger.info("Parsed keeper result: %s", result)
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(
                    "Failed to parse keeper output: %s. Output: %r",
                    e,
                    stdout.decode("utf-8", errors="replace"),
                )
                job.success = False
                job.text = [KEEPER_ERROR_MESSAGE]
                return

            job.success = result["success"]
            job.outcome = str(result["outcome"])
            job.text = result["text"]
            job.admin_text = result.get("admin_text")
            job.plus = result.get("stats", {})

    def _executable_filename(self, codenames, language):
        """Return the filename of the executable."""
        name = "_".join(sorted(codename.replace(".%l", "") for codename in codenames))
        return name + language.executable_extension
