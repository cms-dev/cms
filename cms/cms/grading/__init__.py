#!/usr/bin/python
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


class JobException(Exception):
    """Exception raised by a worker doing a job.

    """
    def __init__(self, msg=""):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

    def __repr__(self):
        return "JobException(\"%s\")" % (repr(self.msg))


def get_compilation_command(language, source_filenames, executable_filename,
                            for_evaluation=True):
    """Returns the compilation command for the specified language,
    source filenames and executable filename. The command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    language (string): one of the recognized languages.
    source_filenames (list): a list of the string that are the
                             filenames of the source files to compile.
    executable_filename (string): the output file.
    for_evaluation (bool): if True, define EVAL during the compilation;
                           defaults to True.
    return (list): a list of string to be passed to subprocess.

    """
    # For compiling in 32-bit mode under 64-bit OS: add "-march=i686",
    # "-m32" for gcc/g++. Don't know about Pascal. Anyway, this will
    # require some better support from the evaluation environment
    # (particularly the sandbox, which has to be compiled in a
    # different way depending on whether it will execute 32- or 64-bit
    # programs).
    if language == "c":
        command = ["/usr/bin/gcc"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-lm", "-o", executable_filename]
        command += source_filenames
    elif language == "cpp":
        command = ["/usr/bin/g++"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-o", executable_filename]
        command += source_filenames
    elif language == "pas":
        command = ["/usr/bin/fpc"]
        if for_evaluation:
            command += ["-dEVAL"]
        command += ["-XS", "-O2", "-o%s" % executable_filename]
        command += source_filenames
    return command
