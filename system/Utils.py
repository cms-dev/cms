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
import CouchObject

get_contests='''function(doc) {
    if (doc.document_type=='contest')
        emit(doc,null)
}'''

def get_contest_list():
    db = get_couchdb_database()
    contests = list(db.query(get_contests, include_docs = True))
    contest_list = [CouchObject.from_couch(x.id) for x in contests]
    return contest_list

def get_couchdb_database():
    couch = couchdb.client.Server(Configuration.couchdb_server)
    try:
        db = couch[Configuration.couchdb_database]
    except couchdb.ResourceNotFound:
        couch.create(Configuration.couchdb_database)
        db = couch[Configuration.couchdb_database]
    return db

def drop_couchdb_database():
    couch = couchdb.client.Server(Configuration.couchdb_server)
    del couch[Configuration.couchdb_database]

def ask_for_contest(skip = 0):
    if len(sys.argv) > skip + 1:
        contest_id = sys.argv[skip + 1]
    else:
        db = get_couchdb_database()
        contests = list(db.query(get_contests, include_docs = True))
        print "Contests available:"
        for i, row in enumerate(contests):
            print "%3d  -  ID: %s  -  Name: %s" % (i + 1, row.id, row.doc["name"]),
            if i == 0:
                print " (default)"
            else:
                print
        try:
            contest_number = raw_input("Insert the number next to the contest you want to load: ")
            if contest_number == "":
                contest_number = 1
            contest_number = int(contest_number) - 1
            contest_id = contests[contest_number].id
        except:
            print "Insert a correct number."
            sys.exit(1)

    try:
        c = CouchObject.from_couch(contest_id)
    except couchdb.client.ResourceNotFound:
        print "Cannot load contest %s." % (contest_id)
        sys.exit(1)
    # from_couch returns None when the contest is not found,
    # and a different item if the provided ID is not a
    # contest.
    from Contest import Contest
    if c == None or not isinstance( c, Contest ):
        print "Cannot load contest %s." % (contest_id)
        sys.exit(1)
    print "Contest %s loaded." % (c.name)
    return c

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

# FIXME - Bad hack
def maybe_mkdir(d):
    try:
        os.mkdir(d)
    except:
        pass

def format_log(msg, service, operation, severity, timestamp):
    d = datetime.datetime.fromtimestamp(timestamp)
    service_full = service
    if operation != "":
        service_full += "/%s" % (operation)
    return "%s - %s [%s] %s" % ('{0:%Y/%m/%d %H:%M:%S}'.format(d), severity, service_full, msg)

class Logger:
    SEVERITY_CRITICAL, SEVERITY_IMPORTANT, SEVERITY_NORMAL, SEVERITY_DEBUG = ["CRITICAL", "IMPORTANT", "NORMAL", "DEBUG"]

    def __init__(self, service = "unknown", log_address = None, log_port = None, local_log = True):
        if log_address == None:
            log_address = Configuration.log_server[0]
        if log_port == None:
            log_port = Configuration.log_server[1]
        self.service = service
        self.operation = ""
        self.log_proxy = xmlrpclib.ServerProxy('http://%s:%d' % (log_address, log_port))
        self.local_log = local_log

        maybe_mkdir("logs")
        import random
        self.local_log_file = codecs.open(\
            os.path.join("logs","%d-%d.local-log" %
                         (time.time(), random.randint(1, 65535))),
            "w", "utf-8")

    def log(self, msg, severity = SEVERITY_NORMAL, timestamp = None):
        if timestamp == None:
            timestamp = time.time()
        try:
            self.log_proxy.log(msg, self.service, self.operation, severity, timestamp)
        except IOError:
            print "Couldn't send log to remote server"
        if self.local_log:
            line = format_log(msg, self.service, self.operation, severity, timestamp)
            print line
            print >> self.local_log_file, line

logger = Logger()

def log(s, severity = Logger.SEVERITY_NORMAL):
    logger.log(s, severity)

def set_service(service):
    logger.service = service

def set_operation(operation):
    logger.operation = operation


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
