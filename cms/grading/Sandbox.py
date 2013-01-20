#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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
import subprocess
import tempfile
import stat
import select
import re
from functools import wraps

from cms import config, logger


class SandboxInterfaceException(Exception):
    pass


def with_log(func):
    """Decorator for presuming that the logs are present.

    """
    @wraps(func)
    def newfunc(self, *args, **kwargs):
        """If they are not present, get the logs.

        """
        if self.log is None:
            self.get_log()
        return func(self, *args, **kwargs)

    return newfunc


def translate_box_exitcode(exitcode):
    """Translate the sandbox exit code according to the following
    table:
     * 0 -> everything ok -> returns True
     * 1 -> error in the program inside the sandbox -> returns True
     * 2 -> error in the sandbox itself -> returns False

    Basically, it recognizes whether the sandbox executed correctly or
    not.

    """
    if exitcode == 0 or exitcode == 1:
        return True
    elif exitcode == 2:
        return False
    else:
        raise SandboxInterfaceException("Sandbox exit status unknown")


def wait_without_std(procs):
    """Wait for the conclusion of the processes in the list, avoiding
    starving for input and output.

    procs (list): a list of processes as returned by Popen.

    return (list): a list of return codes.

    """
    def get_to_consume():
        """Amongst stdout and stderr of list of processes, find the
        ones that are alive and not closed (i.e., that may still want
        to write to).

        return (list): a list of open streams.

        """
        to_consume = []
        for process in procs:
            if process.poll() == None:  # If the process is alive.
                if not process.stdout.closed:
                    to_consume.append(process.stdout)
                if not process.stderr.closed:
                    to_consume.append(process.stderr)
        return to_consume

    # Close stdin; just saying stdin=None isn't ok, because the
    # standard input would be obtained from the application stdin,
    # that could interfere with the child process behaviour
    for process in procs:
        process.stdin.close()

    # Read stdout and stderr to the end without having to block
    # because of insufficient buffering (and without allocating too
    # much memory). Unix specific.
    to_consume = get_to_consume()
    while len(to_consume) > 0:
        to_read = select.select(to_consume, [], [], 1.0)[0]
        for file_ in to_read:
            file_.read(8192)
        to_consume = get_to_consume()

    return [process.wait() for process in procs]


def my_truncate(ff, size):
    """Truncate file-like object ff at specified size. If file is
    shorter than size, it is not modified (this is different from
    using ff.truncate(), which doesn't mandate any specific behavior
    in this case).

    After truncations, the file position is reset to 0.

    """
    ff.seek(0, os.SEEK_END)
    cur_size = ff.tell()
    if cur_size > size:
        ff.truncate(size)
    ff.seek(0, os.SEEK_SET)


class Sandbox:
    """This class creates, deletes and manages the interaction with a
    sandbox. The sandbox doesn't support concurrent operation, not
    even for reading.

    The Sandbox offers API for retrieving and storing file, as well as
    executing programs in a controlled environment. There are anyway a
    few files reserved for use by the Sandbox itself:

     * commands.log: a text file with the commands ran into this
       Sandbox, one for each line;

     * run.log.N: for each N, the log produced by the sandbox when running
       command number N.

    """
    def __init__(self, file_cacher=None, temp_dir=None):
        """Initialization.

        file_cacher (FileCacher): an instance of the FileCacher class
                                  (to interact with FS).
        temp_dir (string): the directory where to put the sandbox
                           (which is itself a directory).

        """
        self.file_cacher = file_cacher

        # Get our shard number, to use as a unique identifier for the sandbox
        # on this machine.
        if file_cacher is not None and file_cacher.service is not None:
            box_id = file_cacher.service._my_coord.shard
        else:
            box_id = 0

        # We create a directory "tmp" inside the outer temporary directory,
        # because the sandbox will bind-mount the inner one. The sandbox also
        # runs code as a different user, and so we need to ensure that they can
        # read and write to the directory. But we don't want everybody on the
        # system to, which is why the outer directory exists with no read
        # permissions.
        if temp_dir is None:
            temp_dir = config.temp_dir
        self.outer_temp_dir = tempfile.mkdtemp(dir=temp_dir)
        self.path = os.path.join(self.outer_temp_dir, "tmp")
        os.mkdir(self.path)
        os.chmod(self.path, 0777)

        self.exec_name = 'isolate'
        self.box_exec = self.detect_box_executable()
        self.info_basename = "run.log"   # Used for -M
        self.cmd_file = "commands.log"
        self.log = None
        self.exec_num = -1
        logger.debug("Sandbox in `%s' created, using box `%s'." %
                     (self.path, self.box_exec))

        # Default parameters for isolate
        self.box_id = box_id           # -b
        self.cgroup = True             # --cg
        self.chdir = None              # -c
        self.dirs = []                 # -d
        self.preserve_env = False      # -e
        self.inherit_env = []          # -E
        self.set_env = {}              # -E
        self.stdin_file = None         # -i
        self.stack_space = None        # -k
        self.address_space = None      # -m
        self.stdout_file = None        # -o
        self.max_processes = 1         # -p
        self.stderr_file = None        # -r
        self.timeout = None            # -t
        self.verbosity = 0             # -v
        self.wallclock_timeout = None  # -w
        self.extra_timeout = None      # -x

        # Tell isolate to get the sandbox ready.
        box_cmd = [self.box_exec, "--cg", "-b", str(self.box_id)]
        if subprocess.call(box_cmd + ["--init"]) != 0:
            raise SandboxInterfaceException("Failed to initialize sandbox.")

    def detect_box_executable(self):
        """Try to find an isolate executable. It first looks in ./isolate/,
        then the local directory, then in the system paths.

        return (string): the path to a valid (hopefully) isolate.

        """
        paths = [os.path.join('.', 'isolate', self.exec_name),
                 os.path.join('.', self.exec_name),
                 self.exec_name]
        for path in paths:
            if os.path.exists(path):
                return path

        # As default, return self.exec_name alone, that means that
        # system path is used.
        return paths[-1]

    def build_box_options(self):
        """Translate the options defined in the instance to a string
        that can be postponed to mo-box as an arguments list.

        return (string): the arguments list as a string.

        """
        res = list()
        if self.box_id is not None:
            res += ["-b", str(self.box_id)]
        if self.cgroup:
            res += ["--cg"]
        if self.chdir is not None:
            res += ["-c", self.chdir]
        for in_name, out_name, options in self.dirs:
            s = in_name
            if out_name is not None:
                s += "=" + out_name
            if options is not None:
                s += ":" + options
            res += ["-d", s]
        if self.preserve_env:
            res += ["-e"]
        for var in self.inherit_env:
            res += ["-E", var]
        for var, value in self.set_env.items():
            res += ["-E", "%s=%s" % (var, value)]
        if self.stdin_file is not None:
            res += ["-i", self.stdin_file]
        if self.stack_space is not None:
            res += ["-k", str(self.stack_space)]
        if self.address_space is not None:
            res += ["-m", str(self.address_space)]
        if self.stdout_file is not None:
            res += ["-o", self.stdout_file]
        if self.max_processes is not None:
            res += ["-p=%d" % self.max_processes]
        else:
            res += ["-p="]
        if self.stderr_file is not None:
            res += ["-r", self.stderr_file]
        if self.timeout is not None:
            res += ["-t", str(self.timeout)]
        res += ["-v"] * self.verbosity
        if self.wallclock_timeout is not None:
            res += ["-w", str(self.wallclock_timeout)]
        if self.extra_timeout is not None:
            res += ["-x", str(self.extra_timeout)]
        res += ["-M", self.relative_path("%s.%d" %
                                         (self.info_basename, self.exec_num))]
        res += ["--run"]
        return res

    def get_log(self):
        """Read the content of the log file of the sandbox (usually
        run.log.N for some integer N), and set self.log as a dict
        containing the info in the log file (time, memory, status,
        ...).

        """
        # self.log is a dictionary of lists (usually lists of length
        # one).
        self.log = {}
        info_file = "%s.%d" % (self.info_basename, self.exec_num)
        try:
            with self.get_file(info_file) as log_file:
                for line in log_file:
                    key, value = line.strip().split(":", 1)
                    if key in self.log:
                        self.log[key].append(value)
                    else:
                        self.log[key] = [value]
        except IOError as error:
            raise IOError("Error while reading execution log file %s. %r" %
                          (info_file, error))

    @with_log
    def get_execution_time(self):
        """Return the time spent in the sandbox, reading the logs if
        necessary.

        return (float): time spent in the sandbox.

        """
        if 'time' in self.log:
            return float(self.log['time'][0])
        return None

    @with_log
    def get_execution_wall_clock_time(self):
        """Return the total time from the start of the sandbox to the
        conclusion of the task, reading the logs if necessary.

        return (float): total time the sandbox was alive.

        """
        if 'time-wall' in self.log:
            return float(self.log['time-wall'][0])
        return None

    @with_log
    def get_memory_used(self):
        """Return the memory used by the sandbox, reading the logs if
        necessary.

        return (float): memory used by the sandbox (in bytes).

        """
        if 'cg-mem' in self.log:
            return int(self.log['cg-mem'][0]) * 1024
        return None

    @with_log
    def get_killing_signal(self):
        """Return the signal that killed the sandboxed process,
        reading the logs if necessary.

        return (int): offending signal, or 0.

        """
        if 'exitsig' in self.log:
            return int(self.log['exitsig'][0])
        return 0

    @with_log
    def get_exit_code(self):
        """Return the exit code of the sandboxed process, reading the
        logs if necessary.

        return (float): exitcode, or 0.

        """
        if 'exitcode' in self.log:
            return int(self.log['exitcode'][0])
        return 0

    # TODO - Rather fragile interface...
    KILLING_SYSCALL_RE = re.compile("^Forbidden syscall (.*)$")

    @with_log
    def get_killing_syscall(self):
        """Return the syscall that triggered the killing of the
        sandboxed process, reading the log if necessary.

        return (string): offending syscall, or None.

        """
        if 'message' in self.log:
            match = self.KILLING_SYSCALL_RE.match(
                self.log['message'][0])
            if match is not None:
                return match.group(1)
        return None

    # TODO - Rather fragile interface...
    KILLING_FILE_ACCESS_RE = re.compile("^Forbidden access to file (.*)$")

    @with_log
    def get_forbidden_file_error(self):
        """Return the error that got us killed for forbidden file
        access.

        return (string): offending error, or None.

        """
        if 'message' in self.log:
            match = self.KILLING_FILE_ACCESS_RE.match(
                self.log['message'][0])
            if match is not None:
                return match.group(1)
        return None

    @with_log
    def get_status_list(self):
        """Reads the sandbox log file, and set and return the status
        of the sandbox.

        return (list): list of statuses of the sandbox.

        """
        if 'status' in self.log:
            return self.log['status']
        return []

    EXIT_SANDBOX_ERROR = 'sandbox error'
    EXIT_OK = 'ok'
    EXIT_SIGNAL = 'signal'
    EXIT_TIMEOUT = 'timeout'
    EXIT_FILE_ACCESS = 'file access'
    EXIT_SYSCALL = 'syscall'
    EXIT_NONZERO_RETURN = 'nonzero return'

    def get_exit_status(self):
        """Get the list of statuses of the sandbox and return the most
        important one.

        return (string): the main reason why the sandbox terminated.

        """
        status_list = self.get_status_list()
        if 'XX' in status_list:
            return self.EXIT_SANDBOX_ERROR
        # New version seems not to report OK
        #elif 'OK' in status_list:
        #    return self.EXIT_OK
        elif 'FO' in status_list:
            return self.EXIT_SYSCALL
        elif 'FA' in status_list:
            return self.EXIT_FILE_ACCESS
        elif 'TO' in status_list:
            return self.EXIT_TIMEOUT
        elif 'SG' in status_list:
            return self.EXIT_SIGNAL
        elif 'RE' in status_list:
            return self.EXIT_NONZERO_RETURN
        return self.EXIT_OK

    def get_human_exit_description(self):
        """Get the status of the sandbox and return a human-readable
        string describing it.

        return (string): human-readable explaination of why the
                         sandbox terminated.

        """
        status = self.get_exit_status()
        if status == self.EXIT_OK:
            return "Execution successfully finished (with exit code %d)" % \
                self.get_exit_code()
        elif status == self.EXIT_SANDBOX_ERROR:
            return "Execution failed because of sandbox error"
        elif status == self.EXIT_SYSCALL:
            return "Execution killed because of forbidden syscall %s" % \
                self.get_killing_syscall()
        elif status == self.EXIT_FILE_ACCESS:
            return "Execution killed because of forbidden file access: %s" \
                    % self.get_forbidden_file_error()
        elif status == self.EXIT_TIMEOUT:
            return "Execution timed out"
        elif status == self.EXIT_SIGNAL:
            return "Execution killed with signal %d" % \
                self.get_killing_signal()
        elif status == self.EXIT_NONZERO_RETURN:
            return "Execution failed because the return code was nonzero"

    def get_stats(self):
        """Return a human-readable string representing execution time
        and memory usage.

        return (string): human-readable stats.

        """
        execution_time = self.get_execution_time()
        if execution_time is not None:
            time_str = "%.3f sec" % (execution_time)
        else:
            time_str = "(time unknown)"
        memory_used = self.get_memory_used()
        if memory_used is not None:
            mem_str = "%.2f MB" % (memory_used / (1024 * 1024))
        else:
            mem_str = "(memory usage unknown)"
        return "[%s - %s]" % (time_str, mem_str)

    def relative_path(self, path):
        """Translate from a relative path inside the sandbox to a
        system path.

        path (string): relative path of the file inside the sandbox.
        return (string): the absolute path.

        """
        return os.path.join(self.path, path)

    # TODO - Rewrite it as context manager
    def create_file(self, path, executable=False):
        """Create an empty file in the sandbox and open it in write
        binary mode.

        path (string): relative path of the file inside the sandbox.
        executable (bool): to set permissions.
        return (file): the file opened in write binary mode.

        """
        if executable:
            logger.debug("Creating executable file %s in sandbox." % path)
        else:
            logger.debug("Creating plain file %s in sandbox." % path)
        real_path = self.relative_path(path)
        file_ = open(real_path, "wb")
        mod = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        if executable:
            mod |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(real_path, mod)
        return file_

    def create_file_from_storage(self, path, digest, executable=False):
        """Write a file taken from FS in the sandbox.

        path (string): relative path of the file inside the sandbox.
        digest (string): digest of the file in FS.
        executable (bool): to set permissions.

        """
        file_ = self.create_file(path, executable)
        self.file_cacher.get_file(digest, file_obj=file_)
        file_.close()

    def create_file_from_string(self, path, content, executable=False):
        """Write some data to a file in the sandbox.

        path (string): relative path of the file inside the sandbox.
        content (string): what to write in the file.
        executable (bool): to set permissions.

        """
        file_ = self.create_file(path, executable)
        file_.write(content)
        file_.close()

    def create_file_from_fileobj(self, path, file_obj, executable=False):
        """Write a file in the sandbox copying the content of an open
        file-like object.

        path (string): relative path of the file inside the sandbox.
        file_obj (file): where from read the file content.
        executable (bool): to set permissions.

        """
        dest = self.create_file(path, executable)
        shutil.copyfileobj(file_obj, dest)
        dest.close()

    # TODO - Rewrite it as context manager
    def get_file(self, path, trunc_len=None):
        """Open a file in the sandbox given its relative path.

        path (string): relative path of the file inside the sandbox.
        trunc_len (int): if None, does nothing; otherwise, before
                         returning truncate it at the specified length.

        return (file): the file opened in read binary mode.

        """
        logger.debug("Retrieving file %s from sandbox" % (path))
        real_path = self.relative_path(path)
        if trunc_len is not None:
            file_ = open(real_path, "ab")
            my_truncate(file_, trunc_len)
            file_.close()
        file_ = open(real_path, "rb")
        return file_

    def get_file_to_string(self, path, maxlen=1024):
        """Return the content of a file in the sandbox given its
        relative path.

        path (string): relative path of the file inside the sandbox.
        maxlen (int): maximum number of bytes to read, or None if no
                      limit.
        return (string): the content of the file up to maxlen bytes.

        """
        file_ = self.get_file(path)
        try:
            if maxlen is None:
                content = file_.read()
            else:
                content = file_.read(maxlen)
        except UnicodeDecodeError as error:
            logger.error("Unable to interpret file as UTF-8. %r" % error)
            return None
        file_.close()
        return content

    def get_file_to_storage(self, path, description="", trunc_len=None):
        """Put a sandbox file in FS and return its digest.

        path (string): relative path of the file inside the sandbox.
        description (string): the description for FS.
        trunc_len (int): if None, does nothing; otherwise, before
                         returning truncate it at the specified length.

        return (string): the digest of the file.

        """
        file_ = self.get_file(path, trunc_len=trunc_len)
        digest = self.file_cacher.put_file(file_obj=file_,
                                           description=description)
        file_.close()
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

    def execute(self, command):
        """Execute the given command in the sandbox.

        command (list): executable filename and arguments of the
                        command.
        return (bool): True if the sandbox didn't report errors
                       (caused by the sandbox itself), False otherwise

        """
        self.exec_num += 1
        self.log = None
        args = [self.box_exec] + self.build_box_options() + ["--"] + command
        logger.debug("Executing program in sandbox with command: %s" %
                     " ".join(args))
        with open(self.relative_path(self.cmd_file), 'a') as commands:
            commands.write("%s\n" % (" ".join(args)))
        return translate_box_exitcode(subprocess.call(args))

    def popen(self, command,
              stdin=None, stdout=None, stderr=None,
              close_fds=True):
        """Execute the given command in the sandbox using
        subprocess.Popen, assigning the corresponding standard file
        descriptors.

        command (list): executable filename and arguments of the
                        command.
        stdin (file): a file descriptor/object or None.
        stdout (file): a file descriptor/object or None.
        stderr (file): a file descriptor/object or None.
        close_fds (bool): close all file descriptor before executing.
        return (object): popen object.

        """
        self.exec_num += 1
        self.log = None
        args = [self.box_exec] + self.build_box_options() + ["--"] + command
        logger.debug("Executing program in sandbox with command: %s" %
                     " ".join(args))
        with open(self.relative_path(self.cmd_file), 'a') as commands:
            commands.write("%s\n" % (" ".join(args)))
        try:
            p = subprocess.Popen(args,
                                    stdin=stdin, stdout=stdout, stderr=stderr,
                                    close_fds=close_fds)
        except OSError, e:
            logger.critical("Failed to execute program in sandbox with command: %s" %
                        " ".join(args))
            logger.critical("Exception: %r" % e)
            raise

        return p


    def execute_without_std(self, command, wait=False):
        """Execute the given command in the sandbox using
        subprocess.Popen and discarding standard input, output and
        error. More specifically, the standard input gets closed just
        after the execution has started; standard output and error are
        read until the end, in a way that prevents the execution from
        being blocked because of insufficient buffering.

        command (list): executable filename and arguments of the
                        command.
        return (bool): True if the sandbox didn't report errors
                       (caused by the sandbox itself), False otherwise

        """
        popen = self.popen(command, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        close_fds=True)

        # If the caller wants us to wait for completion, we also avoid
        # std*** to interfere with command. Otherwise we let the
        # caller handle these issues.
        if wait:
            return translate_box_exitcode(wait_without_std([popen])[0])
        else:
            return popen

    def delete(self):
        """Delete the directory where the sandbox operated.

        """
        logger.debug("Deleting sandbox in %s" % self.path)

        # Tell isolate to cleanup the sandbox.
        box_cmd = [self.box_exec, "--cg", "-b", str(self.box_id)]
        subprocess.call(box_cmd + ["--cleanup"])

        # Delete the working directory.
        shutil.rmtree(self.outer_temp_dir)
