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

from sqlalchemy import Column, Integer, String, Boolean, Unicode, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import Base
from cms.db.Contest import Contest

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    real_name = Column(String, nullable=False)
    ip = Column(String, nullable=True)
    time_zone = Column(Float, nullable=False)
    hidden = Column(Boolean, nullable=False)
    contest_id = Column(Integer, ForeignKey(Contest.id, onupdate="CASCADE", ondelete="CASCADE"), nullable=False)

    #messages (backref)
    #questions (backref)
    #tokens (backref)
    contest = relationship(Contest, backref=backref("users"))

    def __init__(self, username, password,
                 real_name, ip, time_zone = 0.0, contest=None, tokens = [], 
                 hidden = False, messages = [], questions = []):
        self.username = username
        self.password = password
        self.real_name = real_name
        self.time_zone = time_zone
        self.ip = ip
        self.tokens = tokens
        self.hidden = hidden
        self.messages = messages
        self.questions = questions
        self.contest = contest

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    timestamp = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)

    user = relationship(User, backref=backref('messages'))

    def __init__(self, timestamp, subject, text, user=None):
        self.timestamp = timestamp
        self.subject = subject
        self.text = text
        self.user = user

class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    question_timestamp = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)
    reply_timestamp = Column(Integer, nullable=True)
    short_reply = Column(String, nullable=True)
    long_reply = Column(String, nullable=True)

    user = relationship(User, backref=backref('questions'))

    def __init__(self, question_timestamp, subject, text,
                 reply_timestamp=None, short_reply=None, long_reply=None,
                 user=None):
        self.question_timestamp = question_timestamp
        self.subject = subject
        self.text = text
        self.reply_timestamp = reply_timestamp
        self.short_reply = short_reply
        self.long_reply = long_reply
        self.user = user

def sample_user(contest):
    import random
    return User("username-%d" % (random.randint(1, 1000)), "password",
                "Mister Real Name", "10.0.0.101", 0.0, contest=contest)
