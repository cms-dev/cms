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

from cms.async.AsyncLibrary import logger, async_lock
from cms.async import ServiceCoord
from cms.service.FileStorage import FileCacher


class Sandbox:
    """This class creates, deletes and manages the interaction with a
    sandbox.

    """
    def __init__(self, file_cacher):
        """Initialization.

        file_cacher (FileCacher): an instance of the FileCacher class
                                  (to interact with FS).
        """
        self.FC = file_cacher

        self.path = tempfile.mkdtemp()
        self.exec_name = 'mo-box'
        self.box_exec = self.detect_box_executable()
        self.info_file = "run.log"    # -M
        logger.debug("Sandbox in `%s' created, using box `%s'" %
                     (self.path, self.box_exec))

        # Default parameters for mo-box
        self.file_check = None         # -a
        self.chdir = None              # -c
        self.preserve_env = False      # -e
        self.inherit_env = []          # -E
        self.set_env = {}              # -E
        self.filter_syscalls = None    # -f
        self.allow_fork = False        # -F
        self.stdin_file = None         # -i
        self.stack_space = None        # -k
        self.address_space = None      # -m
        self.stdout_file = None        # -o
        self.allow_path = []           # -p
        self.set_path = {}             # -p
        self.stderr_file = None        # -r
        self.allow_syscall = []        # -s
        self.set_syscall = {}          # -s
        self.deny_timing = False       # -S
        self.timeout = None            # -t
        self.verbosity = 0             # -v
        self.wallclock_timeout = None  # -w
        self.extra_timeout = None      # -x

    def detect_box_executable(self):
        """Try to find a mo-box executable. It looks before in the
        local directory, then in ./box, then in the system paths.

        return (string): the path to a valid (hopefully) mo-box.

        """
        PATHS = [os.path.join('.', self.exec_name),
                 os.path.join('.', 'box', self.exec_name),
                 self.exec_name]
        for p in PATHS:
            if os.path.exists(p):
                return p

        # As default, return self.exec_name alone, that means that
        # system path is used.
        return PATHS[-1]

    def build_box_options(self):
        """Translate the options defined in the instance to a string
        that can be postponed to mo-box as an arguments list.

        return (string): the arguments list as a string.

        """
        res = list()
        if self.file_check is not None:
            res += ["-a", str(self.file_check)]
        if self.chdir is not None:
            res += ["-c", self.chdir]
        if self.preserve_env:
            res += ["-e"]
        for var in self.inherit_env:
            res += ["-E", var]
        for var, value in self.set_env.items():
            res += ["-E", "%s=%s" % (var, value)]
        if self.filter_syscalls is not None and self.filter_syscalls > 0:
            res += ["-%s" % ("f" * self.filter_syscalls)]
        if self.allow_fork:
            res += ["-F"]
        if self.stdin_file is not None:
            res += ["-i", self.stdin_file]
        if self.stack_space is not None:
            res += ["-k", str(self.stack_space)]
        if self.address_space is not None:
            res += ["-m", str(self.address_space)]
        if self.stdout_file is not None:
            res += ["-o", self.stdout_file]
        for path in self.allow_path:
            res += ["-p", path]
        for path, action in self.set_path.items():
            res += ["-p", "%s=%s" % (path, action)]
        if self.stderr_file is not None:
            res += ["-r", self.stderr_file]
        for syscall in self.allow_syscall:
            res += ["-s", syscall]
        for syscall, action in self.set_syscall.items():
            res += ["-s", "%s=%s" % (syscall, action)]
        if self.deny_timing:
            res += ["-S"]
        if self.timeout is not None:
            res += ["-t", str(self.timeout)]
        res += ["-v"] * self.verbosity
        if self.wallclock_timeout is not None:
            res += ["-w", str(self.wallclock_timeout)]
        if self.extra_timeout is not None:
            res += ["-x", str(self.extra_timeout)]
        res += ["-M", self.relative_path(self.info_file)]
        return res

    def get_log(self):
        """Return the content of the log file of the sandbox (usually
        run.log), and set self.log as a dict containing the info in
        the log file (time, memory, status, ...).

        return (string): the content of the sandbox log file.

        """
        if "log" not in self.__dict__:
            self.log = list()
            try:
                with self.get_file(self.info_file) as log_file:
                    for line in log_file:
                        self.log.append(line.strip().split(":", 1))
            except IOError:
                raise IOError("Error while reading execution log")
        return self.log

    def get_execution_time(self):
        """After reading the sandbox log file, return the time spent
        in the sandbox.

        return (float): time spent in the sandbox.

        """
        for k, v in self.log:
            if k == 'time':
                return float(v)
        return None

    def get_execution_wall_clock_time(self):
        """After reading the sandbox log file, return the total time
        from the start of the sandbox to the conclusion of the task.

        return (float): total time the sandbox was alive.

        """
        for k, v in self.log:
            if k == 'wall-time':
                return float(v)
        return None

    def get_memory_used(self):
        """After reading the sandbox log file, return the memory used
        by the sandbox.

        return (float): memory used by the sandbox.

        """
        for k, v in self.log:
            if k == 'mem':
                return float(v)
        return None

    def get_status_list(self):
        """Reads the sandbox log file, and set and return the status
        of the sandbox.

        return (list): list of statuses of the sandbox.

        """
        if "status_list" not in self.__dict__:
            self.status_list = list()
            for k, v in self.get_log():
                if k == 'status':
                    self.status_list.append(v)

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
            return "Execution successfully finished (with exit code %d)" % \
                   self.get_exit_code()
        elif status == self.EXIT_SANDBOX_ERROR:
            return "Execution failed because of sandbox error"
        elif status == self.EXIT_SYSCALL:
            return "Execution killed because of forbidden syscall"
        elif status == self.EXIT_FILE_ACCESS:
            return "Execution killed because of forbidden file access"
        elif status == self.EXIT_TIMEOUT:
            return "Execution timed out"
        elif status == self.EXIT_SIGNAL:
            return "Execution killed with signal %d" % \
                   self.get_killing_signal()

    def get_stats(self):
        return "[%.3f sec - %.2f MB]" % \
               (self.get_execution_time(),
                float(self.get_memory_used()) / (1024 * 1024))

    def relative_path(self, path):
        """Translate from a relative path inside the sandbox to a
        system path.

        path (string): relative path of the file inside the sandbox.
        return (string): the absolute path.

        """
        return os.path.join(self.path, path)

    def create_file(self, path, executable=False):
        """Create an empty file in the sandbox and open it in write
        binary mode.

        path (string): relative path of the file inside the sandbox.
        executable (bool): to set permissions.
        return (file): the file opened in write binary mode.

        """
        if executable:
            logger.debug("Creating executable file %s in sandbox" % path)
        else:
            logger.debug("Creating plain file %s in sandbox" % path)
        real_path = self.relative_path(path)
        fd = open(real_path, "wb")
        mod = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        if executable:
            mod |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(real_path, mod)
        return fd

    def create_file_from_storage(self, path, digest, executable=False):
        """Write a file taken from FS in the sandbox.

        path (string): relative path of the file inside the sandbox.
        digest (string): digest of the file in FS.
        executable (bool): to set permissions.

        """
        fd = self.create_file(path, executable)
        with async_lock:
            self.FC.get_file_to_write_file(digest, fd, sync=True)
        fd.close()

    def create_file_from_string(self, path, content, executable=False):
        """Write some data to a file in the sandbox.

        path (string): relative path of the file inside the sandbox.
        content (string): what to write in the file.
        executable (bool): to set permissions.

        """
        fd = self.create_file(path, executable)
        fd.write(content)
        fd.close()

    def get_file(self, path):
        """Open a file in the sandbox given its relative path.

        path (string): relative path of the file inside the sandbox.
        return (file): the file opened in read binary mode.

        """
        logger.debug("Retrieving file %s from sandbox" % (path))
        real_path = self.relative_path(path)
        fd = open(real_path, "rb")
        return fd

    def get_file_to_string(self, path, maxlen=1024):
        """Return the content of a file in the sandbox given its
        relative path.

        path (string): relative path of the file inside the sandbox.
        maxlen (int): maximum number of bytes to read, or None if no
                      limit.
        return (string): the content of the file up to maxlen bytes.

        """
        fd = self.get_file(path)
        try:
            if maxlen is None:
                content = fd.read()
            else:
                content = fd.read(maxlen)
        except UnicodeDecodeError as e:
            logger.error("Unable to interpret file as UTF-8. %s" % repr(e))
            return None
        fd.close()
        return content

    def get_file_to_storage(self, path, description=""):
        """Put a sandbox file in FS and return its digest.

        path (string): relative path of the file inside the sandbox.
        description (string): the description for FS.
        return (string): the digest of the file.

        """
        fd = self.get_file(path)
        with async_lock:
            digest = self.FC.put_file_from_file(fd, description, sync=True)
        fd.close()
        return digest

    def stat_file(self, path):
        """Return the stats of a file in the sandbox.

        path (string): relative path of the file inside the sandbox.
        return (stat_result): the stat results.

        """
        return os.stat(self.relative_path(path))

    def file_exists(self, path):
        """Return if a file exists in the sandbox.

        path (string): relative path of the file inside the sandbox.
        return (bool): if the file exists.

        """
        return os.path.exists(self.relative_path(path))

    def remove_file(self, path):
        """Delete a file in the sandbox.

        path (string): relative path of the file inside the sandbox.

        """
        os.remove(self.relative_path(path))

    def clean(self):
        del self.log

    def execute(self, command):
        args = [self.box_exec] + self.build_box_options() + ["--"] + command
        logger.debug("Executing program in sandbox with command: %s" %
                     " ".join(args))
        return subprocess.call(args)

    def popen(self, command,
              stdin=None, stdout=None, stderr=None,
              close_fds=False):
        args = [self.box_exec] + self.build_box_options() + ["--"] + command
        logger.debug("Executing program in sandbox with command: %s" %
                     " ".join(args))
        return subprocess.Popen(args,
                                stdin=stdin, stdout=stdout, stderr=stderr,
                                close_fds=close_fds)

    def execute_without_std(self, command):
        popen = self.popen(command, stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           close_fds=True)
        popen.stdin.close()

        # Read stdout and stderr to the end without having to block
        # because of insufficient buffering (and without allocating
        # too much memory)
        # FIXME - Probably UNIX-specific (shouldn't work on Windows)
        to_consume = [popen.stdout, popen.stderr]
        while len(to_consume) > 0:
            read, tmp1, tmp2 = select.select(to_consume, [], [])
            for f in read:
                if f.read(8192) == '':
                    to_consume.remove(f)

        return popen.wait()

    def delete(self):
        logger.debug("Deleting sandbox in %s" % self.path)
        shutil.rmtree(self.path)
