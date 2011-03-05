#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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
import subprocess
import tempfile
import stat
import select

import Utils
from FileStorageLib import FileStorageLib

class Sandbox:
    def __init__(self):
        self.path = tempfile.mkdtemp()
        self.FSL = FileStorageLib()
        self.info_file = "run.log"    # -M
        Utils.log("Sandbox in %s created" % (self.path), Utils.Logger.SEVERITY_DEBUG)

        # Default parameters for mo-box
        self.file_check = None        # -a
        self.chdir = None             # -c
        self.preserve_env = False     # -e
        self.inherit_env = []         # -E
        self.set_env = {}             # -E
        self.filter_syscalls = None   # -f
        self.allow_fork = False       # -F
        self.stdin_file = None        # -i
        self.stack_space = None       # -k
        self.address_space = None     # -m
        self.stdout_file = None       # -o
        self.allow_path = []          # -p
        self.set_path = {}            # -p
        self.stderr_file = None       # -r
        self.allow_syscall = []       # -s
        self.set_syscall = {}         # -s
        self.deny_timing = False      # -S
        self.timeout = None           # -t
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
        for var, value in self.set_env.items():
            res += ["-E", "%s=%s" % (var, value)]
        if self.filter_syscalls != None and self.filter_syscalls > 0:
            res += ["-%s" % ("f" * self.filter_syscalls)]
        if self.allow_fork:
            res += ["-F"]
        if self.stdin_file != None:
            res += ["-i", self.stdin_file]
        if self.stack_space != None:
            res += ["-k", str(self.stack_space)]
        if self.address_space != None:
            res += ["-m", str(self.address_space)]
        if self.stdout_file != None:
            res += ["-o", self.stdout_file]
        for path in self.allow_path:
            res += ["-p", path]
        for path, action in self.set_path.items():
            res += ["-p", "%s=%s" % (path, action)]
        if self.stderr_file != None:
            res += ["-r", self.stderr_file]
        for syscall in self.allow_syscall:
            res += ["-s", syscall]
        for syscall, action in self.set_syscall.items():
            res += ["-s", "%s=%s" % (syscall, action)]
        if self.deny_timing:
            res += ["-S"]
        if self.timeout != None:
            res += ["-t", str(self.timeout)]
        res += ["-v"] * self.verbosity
        if self.wallclock_timeout != None:
            res += ["-w", str(self.wallclock_timeout)]
        if self.extra_timeout != None:
            res += ["-x", str(self.extra_timeout)]
        res += ["-M", self.relative_path(self.info_file)]
        return res

    def get_log(self):
        if "log" not in self.__dict__:
            self.log = list()
            try:
                with self.get_file(self.info_file) as log_file:
                    for line in log_file:
                        self.log.append(line.strip().split(":", 2))
            except IOError:
                raise IOError("Error while reading execution log")
        #Utils.log("Execution log: %s" % (repr(self.log)), Utils.Logger.SEVERITY_DEBUG)
        return self.log

    def get_execution_time(self):
        for k, v in self.log:
            if k == 'time':
                return float(v)
        return None

    def get_execution_wall_clock_time(self):
        for k, v in self.log:
            if k == 'wall-time':
                return float(v)
        return None

    def get_memory_used(self):
        for k, v in self.log:
            if k == 'mem':
                return float(v)
        return None

    def get_status_list(self):
        if "status_list" not in self.__dict__:   # No better way to do this?
            self.status_list = list()
            for k, v in self.get_log():
                if k == 'status':
                    self.status_list.append(v)
        #Utils.log("Status list: %s" % (repr(self.status_list)), Utils.Logger.SEVERITY_DEBUG)
        return self.status_list

    EXIT_SANDBOX_ERROR = 'sandbox error'
    EXIT_OK = 'ok'
    EXIT_SIGNAL = 'signal'
    EXIT_TIMEOUT = 'timeout'
    EXIT_FILE_ACCESS = 'file access'
    EXIT_SYSCALL = 'syscall'

    def get_exit_status(self):
        self.get_status_list()
        if 'XX' in self.status_list:
            return self.EXIT_SANDBOX_ERROR
        # New version seems not to report OK
        #elif 'OK' in self.status_list:
        #    return self.EXIT_OK
        elif 'FO' in self.status_list:
            return self.EXIT_SYSCALL
        elif 'FA' in self.status_list:
            return self.EXIT_FILE_ACCESS
        elif 'TO' in self.status_list:
            return self.EXIT_TIMEOUT
        elif 'SG' in self.status_list:
            return self.EXIT_SIGNAL
        return self.EXIT_OK

    def get_killing_signal(self):
        for k, v in self.get_log():
            if k == 'exitsig':
                return int(v)
        return None

    def get_exit_code(self):
        for k, v in self.get_log():
            if k == 'exitcode':
                return int(v)
        return 0

    def get_human_exit_description(self):
        status = self.get_exit_status()
        if status == self.EXIT_OK:
            return "Execution successfully finished (with exit code %d)" % (self.get_exit_code())
        elif status == self.EXIT_SANDBOX_ERROR:
            return "Execution failed because of sandbox error"
        elif status == self.EXIT_SYSCALL:
            return "Execution killed because of forbidden syscall"
        elif status == self.EXIT_FILE_ACCESS:
            return "Execution killed because of forbidden file access"
        elif status == self.EXIT_TIMEOUT:
            return "Execution timed out"
        elif status == self.EXIT_SIGNAL:
            return "Execution killed with signal %d" % (self.get_killing_signal())

    def get_stats(self):
        return "[%.3f sec - %.2f MB]" % (self.get_execution_time(), float(self.get_memory_used()) / (1024 * 1024))

    def relative_path(self, path):
        return os.path.join(self.path, path)

    def create_file(self, path, executable = False):
        if executable:
            Utils.log("Creating executable file %s in sandbox" % (path), Utils.Logger.SEVERITY_DEBUG)
        else:
            Utils.log("Creating plain file %s in sandbox" % (path), Utils.Logger.SEVERITY_DEBUG)
        real_path = self.relative_path(path)
        fd = open(real_path, 'w')
        mod = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        if executable:
            mod |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(real_path, mod)
        return fd

    def create_file_from_storage(self, path, digest, executable = False):
        fd = self.create_file(path, executable)
        self.FSL.get_file(digest, fd)
        fd.close()

    def create_file_from_string(self, path, content, executable = False):
        fd = self.create_file(path, executable)
        fd.write(content)
        fd.close()

    def get_file(self, path):
        Utils.log("Retrieving file %s from sandbox" % (path), Utils.Logger.SEVERITY_DEBUG)
        real_path = self.relative_path(path)
        fd = open(real_path, 'r')
        return fd

    def get_file_to_string(self, path, maxlen=None):
        fd = self.get_file(path)
        if maxlen == None:
            contest = fd.read()
        else:
            content = fd.read(maxlen)
        fd.close()
        return content

    def get_file_to_storage(self, path, description = ""):
        fd = self.get_file(path)
        digest = self.FSL.put_file(fd, description)
        fd.close()
        return digest

    def stat_file(self, path):
        return os.stat(self.relative_path(path))

    def file_exists(self, path):
        return os.path.exists(self.relative_path(path))

    def remove_file(self, path):
        os.remove(self.relative_path(path))

    def clean(self):
        del self.log

    def execute(self, command):
        args = ["./mo-box"] + self.build_box_options() + ["--"] + command
        Utils.log("Executing program in sandbox with command: %s" % (" ".join(args)), Utils.Logger.SEVERITY_DEBUG)
        return subprocess.call(args)

    def popen(self, command, stdin = None, stdout = None, stderr = None, close_fds = False):
        args = ["./mo-box"] + self.build_box_options() + ["--"] + command
        Utils.log("Executing program in sandbox with command: %s" % (" ".join(args)), Utils.Logger.SEVERITY_DEBUG)
        return subprocess.Popen(args, stdin = stdin, stdout = stdout, stderr = stderr, close_fds = close_fds)

    def execute_without_std(self, command):
        popen = self.popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, close_fds = True)
        popen.stdin.close()

        # Read stdout and stderr to the end without having to block because of insufficient buffering
        # (and without allocating too much memory)
        # FIXME - Probably UNIX-specific (shouldn't work on Windows)
        to_consume = [popen.stdout, popen.stderr]
        while len(to_consume) > 0:
            read, tmp1, tmp2 = select.select(to_consume, [], [])
            finished = list()
            for f in read:
                if f.read(8192) == '':
                    to_consume.remove(f)

        return popen.wait()

    def delete(self):
        Utils.log("Deleting sandbox in %s" % (self.path), Utils.Logger.SEVERITY_DEBUG)
        shutil.rmtree(self.path)
