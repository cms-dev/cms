#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# As this package initialization code is run by all code that imports
# something in cms.* it's the best place to setup the logging handlers.
# By importing the log module we install a handler on stdout. Other
# handlers will be added by services by calling initialize_logging.
import cms.log

import subprocess

# Define what this package will provide.

__all__ = [
    "LANG_C", "LANG_CPP", "LANG_PASCAL", "LANG_PYTHON2", "LANG_PYTHON3", "LANG_PHP", "LANG_CS"
    "LANGUAGE_NAMES", "LANGUAGES", "DEFAULT_LANGUAGES", "PYTHON3_COMPILE_NAME",
    "SOURCE_EXT_TO_LANGUAGE_MAP",
    "LANGUAGE_TO_SOURCE_EXT_MAP", "LANGUAGE_TO_HEADER_EXT_MAP",
    "LANGUAGE_TO_OBJ_EXT_MAP", "LANGUAGE_TO_MAX_PROCCESSORS", "JAVA_CLASS_NAME",
    "SCORE_MODE_MAX", "SCORE_MODE_MAX_TOKENED_LAST",
    # log
    # Nothing intended for external use, no need to advertise anything.
    # util
    "ConfigError", "mkdir", "utf8_decoder", "Address", "ServiceCoord",
    "get_safe_shard", "get_service_address", "get_service_shards",
    "default_argument_parser",
    # conf
    "config",
    # plugin
    "plugin_list", "plugin_lookup",
]


# Instantiate or import these objects.

# Shorthand codes for all supported languages.
LANG_C = "c"
LANG_CPP = "cpp"
LANG_CS = "cs"
LANG_PASCAL = "pas"
LANG_PYTHON2 = "py2"
LANG_PYTHON3 = "py3"
LANG_PHP = "php"
LANG_JAVA = "java"

# Python 3 py_compile outputs to __pycache__/filename.<PYTHON3_COMPILE_NAME>.pyc
# Using a '*' in this place does not appear to work correctly.
# Format seems standard as cpython-<MAJOR><MINOR> for cpython.
# Fetch python3 minor version to make compile PYTHON3_COMPILE_NAME correct for local setup
# python3 -V returns "Python M.m.p\n"
try:
    PYTHON3_COMPILE_NAME = "cpython-3" + subprocess.check_output(["python3", "-V"], stderr=subprocess.STDOUT).split()[1].split('.')[1]
except (subprocess.CalledProcessError, OSError):
    # Python 3 not installed, no point in handling here as it will fail anyway when trying to submit
    PYTHON3_COMPILE_NAME = None

LANGUAGE_NAMES = {
    LANG_C: "C",
    LANG_CPP: "C++",
    LANG_CS: "C#",
    LANG_PASCAL: "Pascal",
    LANG_PYTHON2: "Python 2",
    LANG_PYTHON3: "Python 3",
    LANG_PHP: "PHP",
    LANG_JAVA: "Java",
}

LANGUAGES = [LANG_C, LANG_CPP, LANG_CS, LANG_PASCAL, LANG_PYTHON2, LANG_PYTHON3, LANG_PHP, LANG_JAVA]
DEFAULT_LANGUAGES = [LANG_C, LANG_CPP, LANG_PASCAL]

# Language specific max_processor requirements
# C# requires a second thread to be able to run a basic program, to be safe we're allowing 20
LANGUAGE_TO_MAX_PROCCESSORS = {
    LANG_CS: 20,
    'default': 1
}

# A reference for extension-based automatic language detection.
# (It's more difficult with headers because ".h" is ambiguous.)
SOURCE_EXT_TO_LANGUAGE_MAP = {
    ".c": LANG_C,
    ".cpp": LANG_CPP,
    ".cxx": LANG_CPP,
    ".cc": LANG_CPP,
    ".C": LANG_CPP,
    ".c++": LANG_CPP,
    ".cs": LANG_CS,
    ".pas": LANG_PASCAL,
    ".py2": LANG_PYTHON2,
    ".py3": LANG_PYTHON3,
    ".php": LANG_PHP,
    ".java": LANG_JAVA,
}

# Our preferred source file and header file extension for each language.
LANGUAGE_TO_SOURCE_EXT_MAP = {
    LANG_C: ".c",
    LANG_CPP: ".cpp",
    LANG_CS: ".cs",
    LANG_PASCAL: ".pas",
    LANG_PYTHON2: ".py2",
    LANG_PYTHON3: ".py3",
    LANG_PHP: ".php",
    LANG_JAVA: ".java",
}
LANGUAGE_TO_HEADER_EXT_MAP = {
    LANG_C: ".h",
    LANG_CPP: ".h",
    LANG_PASCAL: "lib.pas",
}
LANGUAGE_TO_OBJ_EXT_MAP = {
    LANG_C: ".o",
    LANG_CPP: ".o",
    LANG_PASCAL: ".o",
}

# Language specific class names.
JAVA_CLASS_NAME = "Solution"

# Task score modes.

# Maximum score amongst all submissions.
SCORE_MODE_MAX = "max"
# Maximum score among all tokened submissions and the last submission.
SCORE_MODE_MAX_TOKENED_LAST = "max_tokened_last"

from .util import ConfigError, mkdir, utf8_decoder, Address, ServiceCoord, \
    get_safe_shard, get_service_address, get_service_shards, \
    default_argument_parser
from .conf import config
from .plugin import plugin_list, plugin_lookup
