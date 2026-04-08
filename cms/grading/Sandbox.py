#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2026 Luca Versari <veluca93@gmail.com>
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

import functools
import logging
import io
import os
import select
import stat
import subprocess
import tempfile
import tarfile
import typing

from cms import config, rmtree
from cms.db.filecacher import FileCacher
from cmscommon.commands import pretty_print_cmdline

logger = logging.getLogger(__name__)


class SandboxInterfaceException(Exception):
    pass


def with_meta(func):
    """Decorator for presuming that meta information is present."""

    @functools.wraps(func)
    def newfunc(self, *args, **kwargs):
        """If not present, get the meta information."""
        if self.meta is None:
            self.get_meta()
        return func(self, *args, **kwargs)

    return newfunc


def wait_without_std(procs: list[subprocess.Popen]) -> list[int]:
    """Wait for the conclusion of the processes in the list, avoiding
    starving for input and output.

    procs: a list of processes as returned by Popen.

    return: a list of return codes.

    """

    def get_to_consume() -> list:
        """Amongst stdout and stderr of list of processes, find the
        ones that are alive and not closed (i.e., that may still want
        to write to).

        return: a list of open streams.

        """
        to_consume = []
        for process in procs:
            if process.poll() is None:  # If the process is alive.
                if process.stdout and not process.stdout.closed:
                    to_consume.append(process.stdout)
                if process.stderr and not process.stderr.closed:
                    to_consume.append(process.stderr)
        return to_consume

    # Close stdin; just saying stdin=None isn't ok, because the
    # standard input would be obtained from the application stdin,
    # that could interfere with the child process behaviour
    for process in procs:
        if process.stdin:
            process.stdin.close()

    # Read stdout and stderr to the end without having to block
    # because of insufficient buffering (and without allocating too
    # much memory). Unix specific.
    to_consume = get_to_consume()
    while len(to_consume) > 0:
        to_read = select.select(to_consume, [], [], 1.0)[0]
        for file_ in to_read:
            file_.read(8 * 1024)
        to_consume = get_to_consume()

    return [process.wait() for process in procs]


class Truncator(io.RawIOBase):
    """Wrap a file-like object to simulate truncation.

    This file-like object provides read-only access to a limited prefix
    of a wrapped file-like object. It provides a truncated version of
    the file without ever touching the object on the filesystem.

    This class is only able to wrap binary streams as it relies on the
    readinto method which isn't provided by text (unicode) streams.

    """

    def __init__(self, fobj: io.RawIOBase, size: int):
        """Wrap fobj and give access to its first size bytes.

        fobj: a file-like object to wrap.
        size: the number of bytes that will be accessible.

        """
        self.fobj = fobj
        self.size = size

    def close(self):
        """See io.IOBase.close."""
        self.fobj.close()

    @property
    def closed(self):
        """See io.IOBase.closed."""
        return self.fobj.closed

    def readable(self):
        """See io.IOBase.readable."""
        return True

    def seekable(self):
        """See io.IOBase.seekable."""
        return True

    def readinto(self, b):
        """See io.RawIOBase.readinto."""
        # This is the main "trick": we clip (i.e. mask, reduce, slice)
        # the given buffer so that it doesn't overflow into the area we
        # want to hide (that is, out of the prefix) and then we forward
        # it to the wrapped file-like object.
        b = memoryview(b)[: max(0, self.size - self.fobj.tell())]
        return self.fobj.readinto(b)

    def seek(self, offset, whence=io.SEEK_SET):
        """See io.IOBase.seek."""
        # We have to catch seeks relative to the end of the file and
        # adjust them to the new "imposed" size.
        if whence == io.SEEK_END:
            if self.fobj.seek(0, io.SEEK_END) > self.size:
                self.fobj.seek(self.size, io.SEEK_SET)
            return self.fobj.seek(offset, io.SEEK_CUR)
        else:
            return self.fobj.seek(offset, whence)

    def tell(self):
        """See io.IOBase.tell."""
        return self.fobj.tell()

    def write(self, _):
        """See io.RawIOBase.write."""
        raise io.UnsupportedOperation("write")


class Sandbox:
    """This class creates, deletes and manages the interaction with a
    sandbox. The sandbox doesn't support concurrent operation, not
    even for reading.

    The Sandbox offers API for retrieving and storing file, as well as
    executing programs in a controlled environment. There are anyway a
    few files reserved for use by the Sandbox itself:

     * commands.log: a text file with the commands ran into this
       Sandbox, one for each line;

     * run.meta.N: for each N, the meta file produced by the sandbox when
       running command number N.

    """

    EXIT_SANDBOX_ERROR = "sandbox error"
    EXIT_OK = "ok"
    EXIT_SIGNAL = "signal"
    EXIT_TIMEOUT = "timeout"
    EXIT_TIMEOUT_WALL = "wall timeout"
    EXIT_MEM_LIMIT = "memory limit exceeded"
    EXIT_NONZERO_RETURN = "nonzero return"

    def __init__(
        self,
        box_index: int,
        shard: int | None,
        name: str | None = None,
        temp_dir: str | None = None,
    ):
        """Initialization.

        box_index: index of this sandbox within the service that wants
            to run it. No two boxes with the same `box_index` should exist
            at the same time.
        shard: the shard index of the service this sandbox runs in, if any.
        name: name of the sandbox, which might appear in the
            path and in system logs.
        temp_dir: temporary directory to use; if None, use the
            default temporary directory specified in the configuration.

        """
        self.name: str = name if name is not None else "unnamed"
        self.temp_dir: str = (
            temp_dir if temp_dir is not None else config.global_.temp_dir
        )

        # Isolate, by default, only accepts ids up to 65000. We assign
        # the range [(shard+1)*1000, (shard+2)*1000) to each Worker and keep
        # the range [0, 1000) for other uses (command-line scripts like cmsMake
        # or direct console users of isolate). Inside each range ids are
        # assigned sequentially, with a wrap-around.
        if shard is None:
            box_id = box_index
        else:
            BOXES_PER_SHARD = 1000
            assert box_index < BOXES_PER_SHARD
            # Note that "shard % 64" might hide misconfiguration.
            # However, since shard numbers are global, there is no good way
            # to have a number in the [0, num_workers_on_this_machine) range.
            box_id = (1 + (shard % 64)) * BOXES_PER_SHARD + box_index

        # We create a directory "home" inside the outer temporary directory,
        # that will be bind-mounted to "/tmp" inside the sandbox (some
        # compilers need "/tmp" to exist, and this is a cheap shortcut to
        # create it). The sandbox also runs code as a different user, and so
        # we need to ensure that they can read and write to the directory.
        # But we don't want everybody on the system to, which is why the
        # outer directory exists with no read permissions.
        self._outer_dir = tempfile.mkdtemp(
            dir=self.temp_dir, prefix="cms-%s-" % (self.name)
        )
        self._home = os.path.join(self._outer_dir, "home")
        self._home_dest = "/tmp"
        os.mkdir(self._home)

        self.exec_name = "isolate"
        # Used for -M - the meta file ends up in the outer directory. The
        # actual filename will be <info_basename>.<execution_number>.
        self.info_basename = os.path.join(self._outer_dir, "run.meta")
        # this type hint is lying a little bit, but inside @with_meta functions,
        # meta will not be None, so this is good enough
        self.meta: dict[str, list[str]] = None
        self.exec_num: int = -1
        self.cmd_file = os.path.join(self._outer_dir, "commands.log")

        # Default parameters for isolate
        self.box_id = box_id  # -b
        self.chdir = self._home_dest  # -c
        self.dirs: list[tuple[str | None, str, str | None]] = []  # -d
        self.preserve_env = False  # -e
        self.inherit_env: list[str] = []  # -E
        self.set_env: dict[str, str] = {}  # -E
        self.fsize: int | None = None  # -f
        self.stdin_file: str | None = None  # -i
        self.stdout_file: str | None = None  # -o
        self.stderr_file: str | None = None  # -r
        self.stack_space: int | None = None  # -k
        self.address_space: int | None = None  # -m
        self.timeout: float | None = None  # -t
        self.verbosity: int = 0  # -v
        self.wallclock_timeout: float | None = None  # -w
        self.extra_timeout: float | None = None  # -x

        self.max_processes: int = 1

        self.allow_writing_all()

        self.add_mapped_directory(self._home, dest=self._home_dest, options="rw")

        # Create temporary directory on /dev/shm to prevent communication
        # between sandboxes.
        self.dirs.append((None, "/dev/shm", "tmp"))

        # Set common environment variables.
        # Specifically needed by Python, that searches the home for
        # packages.
        self.set_env["HOME"] = self._home_dest

        # Needed on Ubuntu by PHP (and more), since /usr/bin only contains a
        # symlink to one out of many alternatives.
        self.maybe_add_mapped_directory("/etc/alternatives")

        # On Arch Linux, pypy3 is installed in `/opt` and `/usr/bin/pypy3` is
        # just a symlink.
        self.maybe_add_mapped_directory("/opt/pypy3")

        # Likewise, needed by C# programs. The Mono runtime looks in
        # /etc/mono/config to obtain the default DllMap, which includes, in
        # particular, the System.Native assembly.
        self.maybe_add_mapped_directory("/etc/mono", options="noexec")

        # Tell isolate to get the sandbox ready. We do our best to cleanup
        # after ourselves, but we might have missed something if a previous
        # worker was interrupted in the middle of an execution, so we issue an
        # idempotent cleanup.
        self.cleanup()
        self.initialize_isolate()

    def set_multiprocess(self, multiprocess: bool):
        """Set the sandbox to (dis-)allow multiple threads and processes.

        multiprocess: whether to allow multiple thread/processes or not.

        """
        if multiprocess:
            # Max processes is set to 1000 to limit the effect of fork bombs.
            self.max_processes = 1000
        else:
            self.max_processes = 1

    def get_stats(self) -> str:
        """Return a human-readable string representing execution time
        and memory usage.

        return: human-readable stats.

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

    def get_root_path(self) -> str:
        """Return the toplevel path of the sandbox.

        return: the root path.

        """
        return self._outer_dir

    @with_meta
    def get_execution_time(self) -> float | None:
        """Return the time spent in the sandbox, reading the meta if
        necessary.

        return: time spent in the sandbox.

        """
        if "time" in self.meta:
            return float(self.meta["time"][0])
        return None

    @with_meta
    def get_execution_wall_clock_time(self) -> float | None:
        """Return the total time from the start of the sandbox to the
        conclusion of the task, reading the meta if necessary.

        return: total time the sandbox was alive.

        """
        if "time-wall" in self.meta:
            return float(self.meta["time-wall"][0])
        return None

    @with_meta
    def get_memory_used(self) -> int | None:
        """Return the memory used by the sandbox, reading the meta if
        necessary.

        return: memory used by the sandbox (in bytes).

        """
        if "cg-mem" in self.meta:
            # Isolate returns memory measurements in KiB.
            return int(self.meta["cg-mem"][0]) * 1024
        return None

    @with_meta
    def get_killing_signal(self) -> int:
        """Return the signal that killed the sandboxed process,
        reading the meta if necessary.

        return: offending signal, or 0.

        """
        if "exitsig" in self.meta:
            return int(self.meta["exitsig"][0])
        return 0

    def get_exit_status(self) -> str:
        """Get the list of statuses of the sandbox and return the most
        important one.

        return: the main reason why the sandbox terminated.

        """
        status_list = self.get_status_list()
        if "XX" in status_list:
            return self.EXIT_SANDBOX_ERROR
        elif "TO" in status_list:
            if "message" in self.meta and "wall" in self.meta["message"][0]:
                return self.EXIT_TIMEOUT_WALL
            else:
                return self.EXIT_TIMEOUT
        elif "SG" in status_list:
            if "cg-oom-killed" in self.meta:
                return self.EXIT_MEM_LIMIT
            else:
                return self.EXIT_SIGNAL
        elif "RE" in status_list:
            return self.EXIT_NONZERO_RETURN
        # OK status is not reported in the meta file, it's implicit.
        return self.EXIT_OK

    @with_meta
    def get_exit_code(self) -> int:
        """Return the exit code of the sandboxed process, reading the
        meta if necessary.

        return: exitcode, or 0.

        """
        if "exitcode" in self.meta:
            return int(self.meta["exitcode"][0])
        return 0

    def get_human_exit_description(self) -> str:
        """Get the status of the sandbox and return a human-readable
        string describing it.

        return: human-readable explaination of why the
                         sandbox terminated.

        """
        status = self.get_exit_status()
        if status == self.EXIT_OK:
            return (
                "Execution successfully finished (with exit code %d)"
                % self.get_exit_code()
            )
        elif status == self.EXIT_SANDBOX_ERROR:
            return "Execution failed because of sandbox error"
        elif status == self.EXIT_TIMEOUT:
            return "Execution timed out"
        elif status == self.EXIT_TIMEOUT_WALL:
            return "Execution timed out (wall clock limit exceeded)"
        elif status == self.EXIT_SIGNAL:
            return "Execution killed with signal %s" % self.get_killing_signal()
        elif status == self.EXIT_NONZERO_RETURN:
            return "Execution failed because the return code was nonzero"
        assert False, "Invalid exit status"

    def relative_path(self, path: str) -> str:
        """Translate from a relative path inside the sandbox to a system path.

        path: relative path of the file inside the sandbox.

        return: the absolute path.

        """
        return os.path.join(self._home, path)

    def create_file(self, path: str, executable: bool = False) -> typing.BinaryIO:
        """Create an empty file in the sandbox and open it in write
        binary mode.

        path: relative path of the file inside the sandbox.
        executable: to set permissions.

        return: the file opened in write binary mode.

        """
        if executable:
            logger.debug("Creating executable file %s in sandbox.", path)
        else:
            logger.debug("Creating plain file %s in sandbox.", path)
        real_path = self.relative_path(path)
        try:
            file_fd = os.open(real_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            file_ = open(file_fd, "wb")
        except OSError as e:
            logger.error(
                "Failed create file %s in sandbox. Unable to "
                "evalulate this submission. This may be due to "
                "cheating. %s",
                real_path,
                e,
                exc_info=True,
            )
            raise
        mod = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        if executable:
            mod |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(real_path, mod)
        return file_

    def create_file_from_storage(
        self, path: str, digest: str, file_cacher: FileCacher, executable: bool = False
    ):
        """Write a file taken from FS in the sandbox.

        path: relative path of the file inside the sandbox.
        digest: digest of the file in FS.
        file_cacher: a FileCacher instance.
        executable: to set permissions.

        """
        with self.create_file(path, executable) as dest_fobj:
            file_cacher.get_file_to_fobj(digest, dest_fobj)

    def create_file_from_string(
        self, path: str, content: bytes, executable: bool = False
    ):
        """Write some data to a file in the sandbox.

        path: relative path of the file inside the sandbox.
        content: what to write in the file.
        executable: to set permissions.

        """
        with self.create_file(path, executable) as dest_fobj:
            dest_fobj.write(content)

    def get_file(self, path: str, trunc_len: int | None = None) -> typing.BinaryIO:
        """Open a file in the sandbox given its relative path.

        path: relative path of the file inside the sandbox.
        trunc_len: if None, does nothing; otherwise, before
            returning truncate it at the specified length.

        return: the file opened in read binary mode.

        """
        logger.debug("Retrieving file %s from sandbox.", path)
        real_path = self.relative_path(path)
        file_ = open(real_path, "rb")
        if trunc_len is not None:
            file_ = Truncator(file_, trunc_len)
        return file_

    def get_file_text(self, path: str, trunc_len: int | None = None) -> typing.TextIO:
        """Open a file in the sandbox given its relative path, in text mode.

        Assumes encoding is UTF-8. The caller must handle decoding errors.

        path: relative path of the file inside the sandbox.
        trunc_len: if None, does nothing; otherwise, before
            returning truncate it at the specified length.

        return: the file opened in read text mode.

        """
        logger.debug("Retrieving text file %s from sandbox.", path)
        real_path = self.relative_path(path)
        file_ = open(real_path, "rt", encoding="utf-8")
        if trunc_len is not None:
            # FIXME Truncator is always binary, no? text-mode streams don't
            # even have the readinto method that Truncator uses...
            file_ = Truncator(file_, trunc_len)
        return file_

    def get_file_to_string(self, path: str, maxlen: int | None = 1024) -> bytes:
        """Return the content of a file in the sandbox given its
        relative path.

        path: relative path of the file inside the sandbox.
        maxlen: maximum number of bytes to read, or None if no
            limit.

        return: the content of the file up to maxlen bytes.

        """
        with self.get_file(path) as file_:
            if maxlen is None:
                return file_.read()
            else:
                return file_.read(maxlen)

    def get_file_to_storage(
        self,
        path: str,
        file_cacher: FileCacher,
        description: str = "",
        trunc_len: int | None = None,
    ) -> str:
        """Put a sandbox file in FS and return its digest.

        path: relative path of the file inside the sandbox.
        file_cacher: a FileCacher instance.
        description: the description for FS.
        trunc_len: if None, does nothing; otherwise, before
            returning truncate it at the specified length.

        return: the digest of the file.

        """
        with self.get_file(path, trunc_len=trunc_len) as file_:
            return file_cacher.put_file_from_fobj(file_, description)

    def stat_file(self, path: str) -> os.stat_result:
        """Return the stats of a file in the sandbox.

        path: relative path of the file inside the sandbox.

        return: the stat results.

        """
        return os.stat(self.relative_path(path))

    def file_exists(self, path: str) -> bool:
        """Return if a file exists in the sandbox.

        path: relative path of the file inside the sandbox.

        return: if the file exists.

        """
        return os.path.exists(self.relative_path(path))

    def remove_file(self, path: str):
        """Delete a file in the sandbox.

        path: relative path of the file inside the sandbox.

        """
        os.remove(self.relative_path(path))

    def execute_without_std(
        self, command: list[str], wait: bool = False
    ) -> bool | subprocess.Popen:
        """Execute the given command in the sandbox using
        subprocess.Popen and discarding standard input, output and
        error. More specifically, the standard input gets closed just
        after the execution has started; standard output and error are
        read until the end, in a way that prevents the execution from
        being blocked because of insufficient buffering.

        command: executable filename and arguments of the command.
        wait: True if this call is blocking, False otherwise

        return: if the call is blocking, then return True
            if the sandbox didn't report errors (caused by the sandbox
            itself), False otherwise; if the call is not blocking,
            return the Popen object from subprocess.

        """
        popen = self._popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )

        # If the caller wants us to wait for completion, we also avoid
        # std*** to interfere with command. Otherwise we let the
        # caller handle these issues.
        if wait:
            return self.translate_box_exitcode(wait_without_std([popen])[0])
        else:
            return popen

    def translate_box_exitcode(self, exitcode: int) -> bool:
        """Translate the sandbox exit code to a boolean sandbox success.

        Isolate emits the following exit codes:
        * 0 -> both sandbox and internal process finished successfully (meta
            file will contain "status:OK" -> return True;
        * 1 -> sandbox finished successfully, but internal process was
            terminated, e.g., due to timeout (meta file will contain
            status:x" with x in (TO, SG, RE)) -> return True;
        * 2 -> sandbox terminated with an error (meta file will contain
            "status:XX") -> return False.

        exitcode: the exit code of the sandbox.

        return: False if the sandbox had an error, True if it terminated
            correctly (regardless of what the internal process did).
        """
        if exitcode == 0 or exitcode == 1:
            return True
        elif exitcode == 2:
            return False
        else:
            raise SandboxInterfaceException(
                "Sandbox exit status (%d) unknown" % exitcode
            )

    def cleanup(self, delete: bool = False):
        """Cleanup the sandbox.

        To be called at the end of the execution, regardless of
        whether the sandbox should be deleted or not.

        delete: if True, also delete get_root_path() and everything it
            contains.
        """
        # The user isolate assigns within the sandbox might have created
        # subdirectories and files therein, making the user outside the sandbox
        # unable to delete the whole tree. If the caller asked us to delete the
        # sandbox, we first issue a chmod within isolate to make sure that we
        # will be able to delete everything. If not, we leave the files as they
        # are to avoid masking possible problems the admin wanted to debug.

        exe = ["isolate", "--box-id=%d" % self.box_id, "--cg"]

        if delete:
            # Ignore exit status as some files may be owned by our user
            subprocess.call(
                exe
                + [
                    "--dir=%s=%s:rw" % (self._home_dest, self._home),
                    "--run",
                    "--",
                    "/bin/chmod",
                    "777",
                    "-R",
                    self._home_dest,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

        # Tell isolate to cleanup the sandbox.
        subprocess.check_call(
            exe + ["--cleanup"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )

        if delete:
            logger.debug("Deleting sandbox in %s.", self._outer_dir)
            # Delete the working directory.
            rmtree(self._outer_dir)

    def archive(self) -> str | None:
        """Archive the directory where the sandbox operated.

        Stores the archived sandbox in the file cacher and returns its digest.
        Returns None if archiving failed.

        """
        logger.info("Archiving sandbox in %s.", self.get_root_path())

        assert self.file_cacher is not None

        with tempfile.TemporaryFile(dir=self.temp_dir) as sandbox_archive:
            # Archive the working directory
            content_path = self.get_root_path()
            try:
                with tarfile.open(fileobj=sandbox_archive, mode="w:gz") as tar_file:
                    tar_file.add(content_path, os.path.basename(content_path))
            except Exception:
                logger.warning("Failed to archive sandbox", exc_info=True)
                return None

            # Put archive to FS
            sandbox_archive.seek(0)
            return self.file_cacher.put_file_from_fobj(
                sandbox_archive, "Sandbox %s" % self.get_root_path()
            )

    def add_mapped_directory(
        self,
        src: str,
        dest: str | None = None,
        options: str | None = None,
        ignore_if_not_existing: bool = False,
    ):
        """Add src to the directory to be mapped inside the sandbox.

        src: directory to make visible.
        dest: if not None, the path where to bind src.
        options: if not None, isolate's directory rule options.
        ignore_if_not_existing: if True, ignore the mapping when src
            does not exist (instead of having isolate terminate with an
            error).

        """
        if dest is None:
            dest = src
        if ignore_if_not_existing and not os.path.exists(src):
            return
        self.dirs.append((src, dest, options))

    def maybe_add_mapped_directory(
        self, src: str, dest: str | None = None, options: str | None = None
    ):
        """Same as add_mapped_directory, with ignore_if_not_existing."""
        return self.add_mapped_directory(
            src, dest, options, ignore_if_not_existing=True
        )

    def allow_writing_all(self):
        """Set permissions in such a way that any operation is allowed."""
        os.chmod(self._home, 0o777)
        for filename in os.listdir(self._home):
            os.chmod(os.path.join(self._home, filename), 0o777)

    def allow_writing_none(self):
        """Set permissions in such a way that the user cannot write anything."""
        os.chmod(self._home, 0o755)
        for filename in os.listdir(self._home):
            os.chmod(os.path.join(self._home, filename), 0o755)

    def allow_writing_only(self, inner_paths: list[str]):
        """Set permissions in so that the user can write only some paths.

        By default the user can only write to the home directory. This
        method further restricts permissions so that it can only write
        to some files inside the home directory.

        inner_paths: the only paths that the user is allowed to
            write to; they should be "inner" paths (from the perspective
            of the sandboxed process, not of the host system); they can
            be absolute or relative (in which case they are interpreted
            relative to the home directory); paths that point to a file
            outside the home directory are ignored.

        """
        outer_paths = []
        for inner_path in inner_paths:
            abs_inner_path = os.path.realpath(os.path.join(self._home_dest, inner_path))
            # If an inner path is absolute (e.g., /fifo0/u0_to_m) then
            # it may be outside home and we should ignore it.
            if os.path.commonpath([abs_inner_path, self._home_dest]) != self._home_dest:
                continue
            rel_inner_path = os.path.relpath(abs_inner_path, self._home_dest)
            outer_path = os.path.join(self._home, rel_inner_path)
            outer_paths.append(outer_path)

        # If one of the specified file do not exists, we touch it to
        # assign the correct permissions.
        for path in outer_paths:
            if not os.path.exists(path):
                open(path, "wb").close()

        # Close everything, then open only the specified.
        self.allow_writing_none()
        for path in outer_paths:
            os.chmod(path, 0o722)

    def build_box_options(self) -> list[str]:
        """Translate the options defined in the instance to a string
        that can be postponed to isolate as an arguments list.

        return: the arguments list as strings.

        """
        res = ["--cg"]
        if self.box_id is not None:
            res += ["--box-id=%d" % self.box_id]
        if self.chdir is not None:
            res += ["--chdir=%s" % self.chdir]
        for src, dest, options in self.dirs:
            s = dest
            if src is not None:
                s += "=" + src
            if options is not None:
                s += ":" + options
            res += ["--dir=%s" % s]
        if self.preserve_env:
            res += ["--full-env"]
        for var in self.inherit_env:
            res += ["--env=%s" % var]
        for var, value in self.set_env.items():
            res += ["--env=%s=%s" % (var, value)]
        if self.fsize is not None:
            # Isolate wants file size as KiB.
            res += ["--fsize=%d" % (self.fsize // 1024)]
        if self.stdin_file is not None:
            res += ["--stdin=%s" % self.inner_absolute_path(self.stdin_file)]
        if self.stack_space is not None:
            # Isolate wants stack size as KiB.
            res += ["--stack=%d" % (self.stack_space // 1024)]
        if self.address_space is not None:
            # Isolate wants memory size as KiB.
            res += ["--cg-mem=%d" % (self.address_space // 1024)]
        if self.stdout_file is not None:
            res += ["--stdout=%s" % self.inner_absolute_path(self.stdout_file)]
        if self.max_processes is not None:
            res += ["--processes=%d" % self.max_processes]
        else:
            res += ["--processes"]
        if self.stderr_file is not None:
            res += ["--stderr=%s" % self.inner_absolute_path(self.stderr_file)]
        if self.timeout is not None:
            res += ["--time=%g" % self.timeout]
        res += ["--verbose"] * self.verbosity
        if self.wallclock_timeout is not None:
            res += ["--wall-time=%g" % self.wallclock_timeout]
        if self.extra_timeout is not None:
            res += ["--extra-time=%g" % self.extra_timeout]
        res += ["--meta=%s" % ("%s.%d" % (self.info_basename, self.exec_num))]
        res += ["--run"]
        return res

    def get_meta(self):
        """Read the content of the meta file of the sandbox (usually
        run.meta.N for some integer N), and set self.meta as a dict
        containing the info in the meta file (time, memory, status,
        ...).

        """
        # self.meta is a dictionary of lists (usually lists of length
        # one).
        self.meta = {}
        info_file = "%s.%d" % (self.info_basename, self.exec_num)
        try:
            with self.get_file_text(info_file) as meta_file:
                for line in meta_file:
                    key, value = line.strip().split(":", 1)
                    if key in self.meta:
                        self.meta[key].append(value)
                    else:
                        self.meta[key] = [value]
        except OSError as error:
            raise OSError(
                "Error while reading execution meta file %s. %r" % (info_file, error)
            )

    @with_meta
    def get_status_list(self) -> list[str]:
        """Reads the sandbox meta file, and set and return the status
        of the sandbox.

        return: list of statuses of the sandbox.

        """
        if "status" in self.meta:
            return self.meta["status"]
        return []

    def inner_absolute_path(self, path: str) -> str:
        """Translate from a relative path inside the sandbox to an
        absolute path inside the sandbox.

        path: relative path of the file inside the sandbox.

        return: the absolute path of the file inside the sandbox.

        """
        return os.path.join(self._home_dest, path)

    def _popen(
        self,
        command: list[str],
        stdin: int | None = None,
        stdout: int | None = None,
        stderr: int | None = None,
        close_fds: bool = True,
    ) -> subprocess.Popen:
        """Execute the given command in the sandbox using
        subprocess.Popen, assigning the corresponding standard file
        descriptors.

        command: executable filename and arguments of the command.
        stdin: a file descriptor.
        stdout: a file descriptor.
        stderr: a file descriptor.
        close_fds: close all file descriptor before executing.

        return: popen object.

        """
        self.meta = None
        self.exec_num += 1

        args = ["isolate"] + self.build_box_options() + ["--"] + command
        logger.debug(
            "Executing program in sandbox with command: `%s'.",
            pretty_print_cmdline(args),
        )
        # Temporarily allow writing new files.
        prev_permissions = stat.S_IMODE(os.stat(self._home).st_mode)
        os.chmod(self._home, 0o770)
        with open(self.cmd_file, "at", encoding="utf-8") as commands:
            commands.write("%s\n" % (pretty_print_cmdline(args)))
        os.chmod(self._home, prev_permissions)
        try:
            p = subprocess.Popen(
                args, stdin=stdin, stdout=stdout, stderr=stderr, close_fds=close_fds
            )
        except OSError:
            logger.critical(
                "Failed to execute program in sandbox " "with command: %s",
                pretty_print_cmdline(args),
                exc_info=True,
            )
            raise

        return p

    def initialize_isolate(self):
        """Initialize isolate's box."""
        init_cmd = ["isolate", "--box-id=%d" % self.box_id, "--cg", "--init"]
        try:
            subprocess.check_call(init_cmd)
        except subprocess.CalledProcessError as e:
            raise SandboxInterfaceException("Failed to initialize sandbox") from e
