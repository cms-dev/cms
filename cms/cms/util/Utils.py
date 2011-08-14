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

import couchdb
import xmlrpclib
import time
import datetime
import os
import sys
import codecs

import Configuration
from cms.db.SQLAlchemyAll import Session, metadata, Contest, SessionGen

def analyze_table(tablename, session=None):
    """Analyze the specified table (issuing the corresponding ANALYZE
    command to the SQL backend).

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation.

    """
    if session == None:
        with SessionGen() as session:
            return analyze_table(tablename, session)

    session.execute("ANALYZE %s;" % (tablename))

def analyze_all_tables(session=None):
    """Analyze all tables tracked by SQLAlchemy.

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation.

    """
    if session == None:
        with SessionGen() as session:
            return analyze_all_tables(session)

    for table in metadata.sorted_tables:
        analyze_table(table.name, session)

def get_contest_list(session=None):
    """Return all the contest objects available on the database.

    session (Session object): if specified, use such session for
                              connecting to the database; otherwise,
                              create a temporary one and discard it
                              after the operation (this means that no
                              further expansion of lazy properties of
                              the returned Contest objects will be
                              possible).

    """
    if session == None:
        with SessionGen() as session:
            return get_contest_list(session)

    return session.query(Contest).all()

def ask_for_contest(skip=0):
    if isinstance(skip, int) and len(sys.argv) > skip + 1:
        contest_id = sys.argv[skip + 1]
    elif isinstance(skip, str):
        contest_id = skip
    else:
        with SessionGen() as session:
            contests = get_contest_list(session)
            print "Contests available:"
            # The ids of the contests are cached, so the session can
            # be closed as soon as possible
            matches = {}
            for i, row in enumerate(contests):
                print "%3d  -  ID: %s  -  Name: %s  -  Description: %s" % (i + 1, row.id, row.name, row.description),
                matches[i+1] = row.id
                if i == 0:
                    print " (default)"
                else:
                    print
        contest_number = raw_input("Insert the number next to the contest you want to load: ")
        if contest_number == "":
            contest_number = 1
        try:
            contest_id = matches[int(contest_number)]
        except ValueError:
            print "Insert a correct number."
            sys.exit(1)
    return contest_id

def filter_ansi_escape(s):
    ansi_mode = False
    res = ''
    for c in s:
        if c == u'\x1b':
            ansi_mode = True
        if not ansi_mode:
            res += c
        if c == u'm':
            ansi_mode = False
    return res

def maybe_mkdir(d):
    try:
        os.mkdir(d)
    except:
        pass

def get_compilation_command(language, source_filename, executable_filename):
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
