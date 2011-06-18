
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Boolean, Unicode, Float, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.collections import attribute_mapped_collection

#db = create_engine("sqlite:///test.sqlite", echo=True)
db = create_engine("postgresql://oiisys:ciaociao@localhost/oiisys2", echo=True)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String)
    password = Column(String)
    real_name = Column(Unicode)
    ip = Column(String)
    #tokens =
    hidden = Column(Boolean)
    #messages =
    #questions =

    def __init__(self, username, password,
                 real_name, ip, tokens = [], hidden = False, messages = [],
                 questions = []):
        self.username = username
        self.password = password
        self.real_name = real_name
        self.ip = ip
        self.tokens = tokens
        self.hidden = hidden
        self.messages = messages
        self.questions = questions

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    #attachments =
    statement = Column(String)
    time_limit = Column(Float)
    task_type = Column(String)
    #submission_format =
    #managers =
    #testcases (backref)
    #public_testcases =
    token_initial = Column(Integer)
    token_max = Column(Integer)
    token_total = Column(Integer)
    token_min_interval = Column(Float)
    token_gen_time = Column(Float)

    TASK_TYPE_BATCH = "TaskTypeBatch"
    TASK_TYPE_PROGRAMMING = "TaskTypeProgramming"
    TASK_TYPE_OUTPUT_ONLY = "TaskTypeOutputOnly"

    def __init__(self, name, title, attachments, statement,
                 time_limit, memory_limit,
                 task_type, submission_format, managers,
                 score_type, score_parameters,
                 testcases, public_testcases,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time):
        self.name = name
        self.title = title
        self.attachments = attachments
        self.statement = statement
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.task_type = task_type
        self.submission_format = submission_format
        self.managers = managers
        self.score_type = score_type
        self.score_parameters = score_parameters
        self.scorer = ScoreTypes.get_score_type_class(score_type,
                                                      score_parameters)
        self.testcases = testcases
        self.public_testcases = public_testcases
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time

    def valid_submission(self, files):
        return True

class Testcase(Base):
    __tablename__ = 'task_testcases'

    id = Column(Integer, primary_key=True)
    num = Column(Integer)
    input = Column(String)
    output = Column(String)
    task_id = Column(Integer, ForeignKey('tasks.id'))

    task = relationship(Task, backref=backref('testcases', collection_class=attribute_mapped_collection('num')))

metadata = Base.metadata
metadata.create_all(db)
