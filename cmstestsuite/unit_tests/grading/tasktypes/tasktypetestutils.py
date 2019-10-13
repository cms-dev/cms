#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utilities for testing task types."""

import functools
from collections import deque
from unittest.mock import patch, MagicMock

from cms import config


def fake_compilation_commands(base, srcs, exe):
    return base + sorted(srcs) + [exe]


def fake_evaluation_commands(base, exe, main=None, args=None):
    cmd = base + [exe]
    if main is not None:
        cmd += [main]
    if args is not None:
        cmd += args
    return [cmd]


def make_language(name, source_extensions, header_extensions,
                  executable_extension, compilation_command,
                  evaluation_command):
    """Create a language (actually a MagicMock) with the given data."""
    language = MagicMock()
    language.configure_mock(name=name,
                            source_extensions=source_extensions,
                            source_extension=source_extensions[0],
                            header_extensions=header_extensions,
                            header_extension=header_extensions[0],
                            executable_extension=executable_extension)
    language.get_compilation_commands.side_effect = \
        functools.partial(fake_compilation_commands, compilation_command)
    language.get_evaluation_commands.side_effect = \
        functools.partial(fake_evaluation_commands, evaluation_command)
    return language


# Some sample languages with some compilation commands bases.
COMPILATION_COMMAND_1 = ["comp", "comm1"]
COMPILATION_COMMAND_2 = ["comp", "comm2"]
EVALUATION_COMMAND_1 = ["run1"]
EVALUATION_COMMAND_2 = ["run2"]
LANG_1 = make_language("L1", [".l1"], [".hl1"], "",
                       COMPILATION_COMMAND_1, EVALUATION_COMMAND_1)
LANG_2 = make_language("L2", [".l2"], [".hl2"], ".ext",
                       COMPILATION_COMMAND_2, EVALUATION_COMMAND_2)


# Some other sample data.
OUTCOME = 0.75
TEXT = ["text %s", "A"]
STATS_OK = {
    "exit_status": "OK",
    "execution_time": 0.01,
    "execution_wall_clock_time": 0.10,
    "execution_memory": 10,
}
STATS_RE = {
    "exit_status": "RE",
    "execution_time": 0.02,
    "execution_wall_clock_time": 0.20,
    "execution_memory": 20,
}


class TaskTypeTestMixin:
    """A test mixin to make it easier to test task types."""

    def setUpMocks(self, tasktype):
        """To be called on the test's setUp.

        tasktype (str): the name of the task type we are testing.

        """
        self.tasktype = tasktype

        # Ensure we don't retain all sandboxes so we can verify delete().
        patcher = patch.object(config, "keep_sandbox", False)
        self.addCleanup(patcher.stop)
        patcher.start()

        # Mock the set of languages (if the task type uses it). Child classes
        # can update this dict before the test to change the set of languages
        # CMS understands.
        self.languages = set()
        self._maybe_patch("LANGUAGES", new=self.languages)
        self.get_language = self._maybe_patch(
            "get_language", new=MagicMock(side_effect=self._mock_get_language))

        # Mock the sandboxes, assuming that all are created via create_sandbox.
        # Child classes can append to this deque to add sandboxes (probably
        # actually MagicMocks) that each call to create_sandbox will return.
        self.sandboxes = deque()
        patcher = patch("cms.grading.tasktypes.util.Sandbox",
                        MagicMock(side_effect=self._mock_sandbox))
        self.addCleanup(patcher.stop)
        self.Sandbox = patcher.start()

        # Mock various steps, if the task type uses them.
        self.compilation_step = self._maybe_patch("compilation_step")
        self.evaluation_step = self._maybe_patch("evaluation_step")
        self.evaluation_step_before_run = self._maybe_patch(
            "evaluation_step_before_run")
        self.evaluation_step_after_run = self._maybe_patch(
            "evaluation_step_after_run")
        self.human_evaluation_message = self._maybe_patch(
            "human_evaluation_message")
        self.eval_output = self._maybe_patch("eval_output")
        self.extract_outcome_and_text = self._maybe_patch(
            "extract_outcome_and_text")

    def _maybe_patch(self, name, *args, **kwargs):
        """Patch name inside the task type if it exists.

        name (str): name of the symbol to patch.
        args (list): additional positional arguments passed to patch.
        kwargs (dict): additional keyword arguments passed to patch.

        return (MagicMock|None): the mock that replaced the symbol, or None if
            the symbol did not exist in the task type.

        """
        patcher = patch("cms.grading.tasktypes.%s.%s" % (self.tasktype, name),
                        *args, **kwargs)
        try:
            patched = patcher.start()
        except AttributeError:
            return None
        self.addCleanup(patcher.stop)
        return patched

    def tearDown(self):
        super().tearDown()
        # Make sure the test used all declared sandboxes.
        self.assertEqual(len(self.sandboxes), 0)

    def expect_sandbox(self):
        """Declare that the SUT will use a new sandbox, and return its mock."""
        sandbox = MagicMock()
        sandbox_idx = len(self.sandboxes)
        sandbox.relative_path.side_effect = \
            lambda p: "/path/%d/%s" % (sandbox_idx, p)
        self.sandboxes.append(sandbox)
        return self.sandboxes[-1]

    def _mock_get_language(self, language_name):
        for language in self.languages:
            if language.name == language_name:
                return language
        raise KeyError()

    def _mock_sandbox(self, *args, **kwargs):
        self.assertGreater(len(self.sandboxes), 0)
        return self.sandboxes.popleft()
