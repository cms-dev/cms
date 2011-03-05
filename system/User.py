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

import Utils
from CouchObject import CouchObject


class User(CouchObject):
    _to_copy = ["username", "password", "real_name", "ip", \
                "hidden", "messages", "questions"]
    _to_copy_id_array = ["tokens"]

    def __init__(self, username, password,
                 real_name, ip, tokens = [], hidden = False, messages = [],
                 questions = [], couch_id = None, couch_rev = None):
        self.username = username
        self.password = password
        self.real_name = real_name
        self.ip = ip
        self.tokens = tokens
        self.hidden = hidden
        self.messages = messages
        self.questions = questions
        CouchObject.__init__(self, "user", couch_id, couch_rev)

    def choose_couch_id_basename(self):
        return "user-%s" % (self.username)

def sample_user(couch_id = None):
    import random
    return User("username-%d" % (random.randint(1, 1000)), "password",
                "Mister Real Name", "10.0.0.101", couch_id = couch_id)

if __name__ == "__main__":
    u = sample_user()
    print "Couch ID: %s" % (u.couch_id)
