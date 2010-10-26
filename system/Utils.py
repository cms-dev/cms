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

import couchdb
import xmlrpclib
import time
import datetime
import os
import sys

import Configuration
import CouchObject

get_contests='''function(doc) {
    if (doc.document_type=='contest')
        emit(doc,null)
}'''

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
        print contest_id
    try:
        c = CouchObject.from_couch(contest_id)
    except couchdb.client.ResourceNotFound:
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

    def log(self, msg, severity = SEVERITY_NORMAL, timestamp = None):
        if timestamp == None:
            timestamp = time.time()
        try:
            self.log_proxy.log(msg, self.service, self.operation, severity, timestamp)
        except IOError:
            print "Couldn't send log to remote server"
        if self.local_log:
            print format_log(msg, self.service, self.operation, severity, timestamp)

logger = Logger()

def log(s, severity = Logger.SEVERITY_NORMAL):
    logger.log(s, severity)

def set_service(service):
    logger.service = service

def set_operation(operation):
    logger.operation = operation
