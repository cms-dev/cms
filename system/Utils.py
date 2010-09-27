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
import Configuration
import xmlrpclib
import time
import datetime
import os

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

# FIXME - Bad hack
def maybe_mkdir(d):
    try:
        os.mkdir(d)
    except:
        pass

def format_log(msg, service, severity, timestamp):
    d = datetime.datetime.fromtimestamp(timestamp)
    return "%s - %s [%s] %s" % ('{0:%Y/%m/%d %H:%M:%S}'.format(d), severity, service, msg)

class Logger:
    SEVERITY_CRITICAL, SEVERITY_IMPORTANT, SEVERITY_NORMAL, SEVERITY_DEBUG = ["CRITICAL", "IMPORTANT", "NORMAL", "DEBUG"]

    def __init__(self, service = "unknown", log_address = None, log_port = None, local_log = True):
        if log_address == None:
            log_address = Configuration.log_server[0]
        if log_port == None:
            log_port = Configuration.log_server[1]
        self.service = service
        self.log_proxy = xmlrpclib.ServerProxy('http://%s:%d' % (log_address, log_port))
        self.local_log = local_log

    def log(self, msg, severity = SEVERITY_NORMAL, timestamp = None):
        if timestamp == None:
            timestamp = time.time()
        try:
            self.log_proxy.log(msg, self.service, severity, timestamp)
        except IOError:
            print "Couldn't send log to remote server"
        if self.local_log:
            print format_log(msg, self.service, severity, timestamp)

logger = Logger()

def log(s):
    logger.log(s)

def set_service(service):
    logger.service = service
