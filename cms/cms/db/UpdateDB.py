#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""This files takes care of storing scripts that update the database
definition when it changes.

"""

import sys
import argparse

from cms.db.SQLAlchemyAll import SessionGen


class ScriptsContainer(object):
    """Class that stores a list of updating script identified by a
    name and a date.

    """

    def __init__(self):
        # List of scripts dates and names (assumed to be sorted).
        self.list = [
            ("20120119", "add_user_starting_time"),
            ]
        self.list.sort()

    def __contains__(self, script):
        """Implement the "script in sc" syntax.

        script (string): name of a script.
        return (bool): True if script is in the collection.

        """
        for (unused_date, contained_script) in self.list:
            if contained_script == script:
                return True
        return False

    def __getitem__(self, script):
        """Implement sc[script] syntax.

        script (string): name of a script.
        return (method): the script.

        """
        return self.__getattribute__(script)

    def get_scripts(self, starting_from="00000000"):
        """Return a sorted list of (date, name) for scripts whose date
        is at least starting_from.

        starting_from (string): initial date in format YYYYMMDD.
        return (list): list of (date, name) of scripts.

        """
        for i, (date, name) in enumerate(self.list):
            if date >= starting_from:
                return self.list[i:]
        return []

    def print_list(self):
        """Print the list of scripts.

        """
        print "Date         Name"
        for date, name in self.list:
            y, m, d = date[:4], date[4:6], date[6:]
            print "%s %s %s   %s" % (y, m, d, name)
            print "             %s" % \
                  self.__getattribute__(name).__doc__.split("\n")[0]

    # Following is the list of scripts implementions.

    def add_per_user__time(self):
        """Support for contest where users may use up to x seconds.

        When we want a contest that, for example, is open for 3 days
        but allows each contestant to participate for 4 hours, we need
        to store somewhere the first time a contestant logged in, and
        the maximum time a user can use.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE users "
                            "ADD COLUMN starting_time INTEGER;")
            session.execute("ALTER TABLE contests "
                            "ADD COLUMN per_user_time INTEGER;")


def execute_single_script(sc, script):
    """Execute one script. Exit on errors.

    sc (ScriptContainer): the list of scripts.
    script (string): the script name.

    """
    if script in sc:
        print "Executing script %s..." % script
        try:
            sc[script]()
        except Exception as e:
            print "Error received, aborting: %r" % e
            sys.exit(1)
        else:
            print "Script executed successfully"
    else:
        print "Script %s not found, aborting" % script
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="List and execute updating scripts for the DB "
        "when CMS changes it")
    parser.add_argument("-l", "--list",
                        help="list all available scripts",
                        action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-x", "--execute-script",
                       help="execute a given script identified by its name",
                       action="append", default=[])
    group.add_argument("-s", "--execute-scripts-since",
                       help="execute all script starting from a given date "
                       "(format: YYYYMMDD)",
                       action="store")
    args = parser.parse_args()

    sc = ScriptsContainer()
    if args.list:
        sc.print_list()

    for script in args.execute_script:
        execute_single_script(sc, script)

    if args.execute_scripts_since is not None:
        if len(args.execute_scripts_since) == 8:
            scripts = sc.get_scripts(starting_from=args.execute_scripts_since)
            for date, script in scripts:
                execute_single_script(sc, script)
        else:
            print "Invalid date format (should be YYYYMMDD)."
            sys.exit(1)





if __name__ == "__main__":
    main()
