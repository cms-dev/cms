#!/usr/bin/python

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Boolean, Unicode, Float, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

#db = create_engine("sqlite:///test.sqlite", echo=True)
db = create_engine("postgresql://oiisys:ciaociao@localhost/oiisys2", echo=True)

Base = declarative_base()

metadata = Base.metadata
metadata.create_all(db)
