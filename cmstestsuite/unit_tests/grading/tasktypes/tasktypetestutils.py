#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import functools

from collections import deque
from mock import patch, MagicMock

from cms import config


def fake_compilation_commands(base, srcs, exe):
    return base + sorted(srcs) + [exe]


def fake_evaluation_commands(base, exe, main=None, args=None):
    cmd = base + [exe]
    if main is not None:
        cmd += [main]
    if args is not None:
        cmd += args
    return cmd


def make_language(name, source_extensions, header_extensions,
                  compilation_command, evaluation_command):
    """Create a language (actually a MagicMock) with the given data."""
    language = MagicMock()
    language.configure_mock(name=name,
                            source_extensions=source_extensions,
                            source_extension=source_extensions[0],
                            header_extensions=header_extensions,
                            header_extension=header_extensions[0])
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
LANG_1 = make_language("L1", [".l1"], [".hl1"],
                       COMPILATION_COMMAND_1, EVALUATION_COMMAND_1)
LANG_2 = make_language("L2", [".l2"], [".hl2"],
                       COMPILATION_COMMAND_2, EVALUATION_COMMAND_2)


# Some other sample data.
OUTCOME = 0.75
TEXT = ["text %s", "A"]
STATS_OK = {"exit_status": "OK"}
STATS_RE = {"exit_status": "RE"}


class TaskTypeTestMixin(object):
    """A test mixin to make it easier to test task types."""

    def setUpMocks(self, tasktype):
        """To be called on the test's setUp.

        tasktype (str): the name of the task type we are testing.

        """
        self.tasktype = tasktype
        tasktype_pkg = "cms.grading.tasktypes.%s" % tasktype

        # Ensure we don't retain all sandboxes so we can verify delete().
        patcher = patch.object(config, "keep_sandbox", False)
        self.addCleanup(patcher.stop)
        patcher.start()

        # Mock the set of languages. Child classes can update this dict before
        # the test to change the set of languages CMS understands.
        self.languages = set()
        patcher = patch("%s.LANGUAGES" % tasktype_pkg, self.languages)
        self.addCleanup(patcher.stop)
        patcher.start()
        patcher = patch("%s.get_language" % tasktype_pkg,
                        MagicMock(side_effect=self._mock_get_language))
        self.addCleanup(patcher.stop)
        self.get_language = patcher.start()

        # Mock the sandboxes, assuming that all are created via create_sandbox.
        # Child classes can append to this deque to add sandboxes (probably
        # actually MagicMocks) that each call to create_sandbox will return.
        self.sandboxes = deque()
        patcher = patch("cms.grading.TaskType.Sandbox",
                        MagicMock(side_effect=self._mock_sandbox))
        self.addCleanup(patcher.stop)
        self.Sandbox = patcher.start()

        # Mock various steps
        patcher = patch("%s.compilation_step" % tasktype_pkg)
        self.addCleanup(patcher.stop)
        self.compilation_step = patcher.start()
        patcher = patch("%s.evaluation_step" % tasktype_pkg)
        self.addCleanup(patcher.stop)
        self.evaluation_step = patcher.start()
        patcher = patch("%s.human_evaluation_message" % tasktype_pkg)
        self.addCleanup(patcher.stop)
        self.human_evaluation_message = patcher.start()
        patcher = patch("%s.eval_output" % tasktype_pkg)
        self.addCleanup(patcher.stop)
        self.eval_output = patcher.start()

    def tearDown(self):
        super(TaskTypeTestMixin, self).tearDown()
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
