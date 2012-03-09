#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system - importer for Australian judge spec
# files.
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

import os
import sys
import codecs
import optparse

from cms.async import ServiceCoord
from cms.db.SQLAlchemyAll import metadata, SessionGen, Task, Manager, \
    Testcase, User, Contest, SubmissionFormatElement
from cms.grading.ScoreType import ScoreTypes
from cms.async.AsyncLibrary import rpc_callback, Service
from cms.service.LogService import logger
from cms.db import ask_for_contest

class AddUser(Service):

    def __init__(self, shard, first_name, last_name, username, password, contest_id):
        #logger.initialize(ServiceCoord("AddUser", shard))
        #logger.debug("AddUser.__init__")
        Service.__init__(self, shard)

        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.password = password
        self.contest_id = contest_id

        self.add_timeout(self.add_user, None, 10, immediately=True)

    def add_user(self):
        #logger.info("Creating question on the database.")
        with SessionGen() as session:
            # Create the dict corresponding to the old contest, from
            # the database
            contest = Contest.get_from_id(self.contest_id, session)

            user = User(
                    first_name=self.first_name,
                    last_name=self.last_name,
                    username=self.username,
                    password=self.password,
                    ip = "0.0.0.0",
                    hidden = False,
                    contest = contest)
            session.add(user)
            session.commit()

        self.exit()
        return False

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] <first name> <last name> <username> <password>")
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    parser.add_option("-c", "--contest",
                      help="contest ID to add username/password to",
                      dest="contest_id", action="store", type="int", default=None)
    options, args = parser.parse_args()
    if len(args) != 4:
        parser.error("I need exactly four parameters, the first name, last name, username and password")
    if options.shard is None:
        options.shard = 0
    contest_id = options.contest_id
    if contest_id is None:
        contest_id = ask_for_contest()

    first_name = args[0]
    last_name = args[1]
    username = args[2]
    password = args[3]
    user_adder = AddUser(shard=options.shard,
                        first_name=first_name,
                        last_name=last_name,
                        username=username,
                        password=password,
                        contest_id=contest_id).run()

if __name__ == "__main__":
    main()
