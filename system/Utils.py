#!/usr/bin/python
# -*- coding: utf-8 -*-

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
