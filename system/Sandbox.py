#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

import os
import shutil
import sys
import StringIO
import subprocess
import Utils

class Sandbox:
    def __init__(self):
        self.path = tempfile.mkdtemp()

        # Default parameters for mo-box
        self.file_check = None        # -a
        self.chdir = None             # -c
        self.preserve_env = False     # -e
        self.inherit_env = []         # -E
        self.set_env = {}             # -E
        self.filter_syscalls = None   # -f
        self.stdin_file = None        # -i
        self.address_space = None     # -m
        self.info_file = None         # -M
        self.stdout_file = None       # -o
        self.allow_path = []          # -p
        self.set_path = {}            # -p
        self.sterr_file = None        # -r
        self.allow_syscall = []       # -s
        self.set_stscall = {}         # -s
        self.deny_timing = False      # -S
        self.timeout = 0              # -t, mandatory
        self.verbosity = 0            # -v
        self.wallclock_timeout = None # -w
        self.extra_timeout = None     # -x

    def build_box_options(self):
        res = list()
        if self.file_check != None:
            res += ["-a", str(self.file_check)]
        if self.chdir != None:
            res += ["-c", self.chdir]
        if self.preserve_env:
            res += ["-e"]
        for var in self.inherit_env:
            res += ["-E", var]
        for var, value in self.set_env:
            res += ["-E", "%s=%s" % (var, value)]
        if self.filter_syscalls != None:
            res += ["-f", str(self.filter_syscalls)]
        if self.stdin_file != None:
            res += ["-i", self.stdin_file]
        if self.address_space != None:
            res += ["-m", str(self.address_space)]
        if self.info_file != None:
            res += ["-M", self.info_file]
        if self.stdout_file != None:
            res += ["-o", self.stdout_file]
        for path in self.allow_path:
            res += ["-p", path]
        for path, action in self.set_path:
            res += ["-p", "%s=%s" % (path, action)]
        if self.deny_timing:
            res += ["-S"]
        res += ["-t", str(self.timeout)]
        res += ["-v"] * self.verbosity
        if self.wallclock_timeout != None:
            res += ["-w", str(self.wallclock_timeout)]
        if self.extra_timeout != None:
            res += ["-x", str(self.extra_timeout)]
        return res

    def create_file(self, path, source):
        real_path = os.path.join(self.path, path)
        fd = open(real_path, 'w')
        shutil.copyfileobj(source, fd)
        fd.close()

    def create_file_from_string(self, path, content):
        source = StringIO.StringIO(content)
        self.create_file(path, source)
        source.close()

    def get_file(self, path):
        real_path = os.path.join(self.path, path)
        fd = open(real_path, 'r')
        return fd

    def get_file_to_string(self, path):
        fd = self.get_file(path)
        content = fd.read()
        return content

    def execute(self, command):
        return subprocess.call(["./mo-box"] +
                               self.build_box_options() +
                               ["--"] + command)

    def delete(self):
        shutil.rmtree(self.path)
