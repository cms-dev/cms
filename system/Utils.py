#!/usr/bin/python
# -*- coding: utf-8 -*-

import couchdb
import Configuration

def get_couchdb_database():
    couch = couchdb.client.Server(Configuration.couchdb_server)
    db = couch[Configuration.couchdb_database]
    return db
