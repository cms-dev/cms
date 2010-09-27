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

def log(s):
    print "LOG:", s
