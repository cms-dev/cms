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

import time
import datetime
import os
import sys
import codecs

import Configuration

## ANSI utilities ##
# see for reference: http://pueblo.sourceforge.net/doc/manual/ansi_color_codes.html

ANSI_FG_COLORS = {'black': 30,
                  'red': 31,
                  'green': 32,
                  'yellow': 33,
                  'blue': 34,
                  'magenta': 35,
                  'cyan': 36,
                  'white': 37}

def filter_ansi_escape(s):
    """Filter out ANSI commands from the given string.

    """
    ansi_mode = False
    res = ''
    for c in s:
        if c == u'\033':
            ansi_mode = True
        if not ansi_mode:
            res += c
        if c == u'm':
            ansi_mode = False
    return res

## Other utilities ##

def maybe_mkdir(d):
    """Make a directory without throwing an exception if it already
    exists. Warning: this method fails silently also if the directory
    could not be created because there is a non-directory file with
    the same name. In oter words, there is no guarantee that after the
    execution, the file d exists and is a directory.

    """
    try:
        os.mkdir(d)
    except OSError:
        pass

def get_compilation_command(language, source_filename, executable_filename):
    """Returns the compilation command for the specified language,
    source filename and executable filename. The command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    """
    # For compiling in 32-bit mode under 64-bit OS: add "-march=i686",
    # "-m32" for gcc/g++. Don't know about Pascal. Anyway, this will
    # require some better support from the evaluation environment
    # (particularly the sandbox, which has to be compiled in a
    # different way depending on whether it will execute 32- or 64-bit
    # programs).
    if language == "c":
        command = ["/usr/bin/gcc", "-DEVAL", "-static", "-O2", "-lm", "-o", executable_filename, source_filename]
    elif language == "cpp":
        command = ["/usr/bin/g++", "-DEVAL", "-static", "-O2", "-o", executable_filename, source_filename]
    elif language == "pas":
        command = ["/usr/bin/fpc", "-dEVAL", "-XS", "-O2", "-o%s" % (executable_filename), source_filename]
    return command


class FileExplorer:
    def __init__(self, directory = "./fs"):
        self.directory = directory

    def list_files(self):
        import glob
        self.files = {}
        for f in glob.glob(os.path.join(self.directory, "descriptions", "*")):
            self.files[os.path.basename(f)] = open(f).read().strip()
        self.sorted_files = self.files.keys()
        self.sorted_files.sort(lambda x, y: cmp(self.files[x], self.files[y]))
        for i, f in enumerate(self.sorted_files):
            print "%3d - %s" % (i+1, self.files[f])

    def get_file(self, i):
        f = os.path.join(self.directory, "objects", self.sorted_files[i])
        os.system("less %s" % f)

    def run(self):
        while True:
            self.list_files()
            print "Display file number: ",
            self.get_file(int(raw_input())-1)

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "fs_explorer":
        FileExplorer().run()
