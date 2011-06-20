
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Boolean, Unicode, Float, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import Configuration

db = create_engine(Configuration.sqlalchemy_database, echo=True)

Base = declarative_base(db)
metadata = Base.metadata

Session = sessionmaker(db)
