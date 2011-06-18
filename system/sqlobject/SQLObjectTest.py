#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
from sqlobject import *

class Person(SQLObject):
    fname = StringCol()
    mi = StringCol(length=1, default=None)
    lname = StringCol()

cwd = os.getcwd()
#sqlhub.processConnection = connectionForURI('sqlite:///%s?debug=1' % (os.path.join(cwd, 'prova.sqlite'))).transaction()
pgConn = postgres.builder()("dbname=oiisys user=oiisys password=ciaociao host=127.0.0.1")
pgConn.debug = True
transConn = pgConn.transaction()
transConn2 = pgConn.transaction()
sqlhub.threadingLocal.connection = transConn

Person.createTable(ifNotExists = True)
transConn.commit()

prova = Person.get(5, connection = transConn2)
print prova

prova2 = Person.get(5, connection = transConn)
print prova2
prova2.fname = "Cambiato"
print prova2
transConn.commit()
transConn2.commit()

prova.sync()
print prova

#a = Person(fname = "Giovanni", lname = "Mascellani")
#b = Person(fname = "Stefano", lname = "Maggiolo")
transConn.commit()
transConn2.commit()
