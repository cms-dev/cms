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

from SQLAlchemyUtils import Base
from Contest import Contest

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    real_name = Column(String, nullable=False)
    ip = Column(String, nullable=True)
    hidden = Column(Boolean, nullable=False)
    #messages (skipped for now)
    #questions (skipped for now)
    contest_id = Column(Integer, ForeignKey(Contest.id), nullable=False)

    #tokens (backref)
    contest = relationship(Contest, backref=backref("users"))

    def __init__(self, username, password,
                 real_name, ip, contest=None, tokens = [], hidden = False,
                 messages = [], questions = []):
        self.username = username
        self.password = password
        self.real_name = real_name
        self.ip = ip
        self.tokens = tokens
        self.hidden = hidden
        self.messages = messages
        self.questions = questions
        self.contest = contest

    #def choose_couch_id_basename(self):
    #    return "user-%s" % (self.username)

def sample_user(contest):
    import random
    return User("username-%d" % (random.randint(1, 1000)), "password",
                "Mister Real Name", "10.0.0.101", contest=contest)
