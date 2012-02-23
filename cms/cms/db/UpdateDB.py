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
            ("20120119", "add_per_user_time"),
            ("20120121", "add_submissions_score"),
            ("20120213", "change_tasktype_names"),
            ("20120218", "constraints_on_tokens"),
            ("20120220", "add_ignore_on_questions"),
            ("20120221", "split_first_and_last_names"),
            ("20120223", "changed_batch_parameters"),
            ]
        self.list.sort()

    def __contains__(self, script):
        """Implement the "script in sc" syntax.

        script (string): name of a script.
        return (bool): True if script is in the collection.

        """
        for (_date, contained_script) in self.list:
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
        for i, (date, _name) in enumerate(self.list):
            if date >= starting_from:
                return self.list[i:]
        return []

    def print_list(self):
        """Print the list of scripts.

        """
        print "Date         Name"
        for date, name in self.list:
            year, month, day = date[:4], date[4:6], date[6:]
            print "%s %s %s   %s" % (year, month, day, name)
            print "             %s" % \
                  self.__getattribute__(name).__doc__.split("\n")[0]

    # Following is the list of scripts implementions.

    @staticmethod
    def add_per_user_time():
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

    @staticmethod
    def add_submissions_score():
        """Support for storing the score in the submission.

        We add two fields to the submission: score and score details,
        that holds the total score (a float) and a (usually)
        JSON-encoded string storing the details of the scoring (e.g.,
        subtasks' scores). Details' meaning is decided by the
        ScoreType.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE submissions "
                            "ADD COLUMN score FLOAT;")
            session.execute("ALTER TABLE submissions "
                            "ADD COLUMN score_details VARCHAR;")
            session.execute("ALTER TABLE submissions "
                            "ADD COLUMN public_score FLOAT;")
            session.execute("ALTER TABLE submissions "
                            "ADD COLUMN public_score_details VARCHAR;")

    @staticmethod
    def change_tasktype_names():
        """Remove the TaskType prefix from every task type name.

        """
        with SessionGen(commit=True) as session:
            session.execute("UPDATE tasks SET task_type = 'Batch' "
                            "WHERE task_type = 'TaskTypeBatch';")
            session.execute("UPDATE tasks SET task_type = 'OutputOnly' "
                            "WHERE task_type = 'TaskTypeOutputOnly';")

    @staticmethod
    def constraints_on_tokens():
        """Better constraints for token information.

        We allow token_initial to be NULL, which means that the tokens
        are disabled for that contest/task. Moreover, all information
        are required to be non-negative (or positive when
        appropriate).

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE contests "
                            "ALTER COLUMN token_initial "
                            "DROP NOT NULL;")
            session.execute("ALTER TABLE contests "
                            "ADD CONSTRAINT contests_token_initial_check "
                            "CHECK (token_initial >= 0);")
            session.execute("ALTER TABLE contests "
                            "ADD CONSTRAINT contests_token_max_check "
                            "CHECK (token_max >= 0);")
            session.execute("ALTER TABLE contests "
                            "ADD CONSTRAINT contests_token_total_check "
                            "CHECK (token_total >= 0);")
            session.execute("ALTER TABLE contests "
                            "ADD CONSTRAINT contests_token_min_interval_check "
                            "CHECK (token_min_interval >= 0);")
            session.execute("ALTER TABLE contests "
                            "ADD CONSTRAINT contests_token_gen_time_check "
                            "CHECK (token_gen_time > 0);")
            session.execute("ALTER TABLE contests "
                            "ADD CONSTRAINT contests_token_gen_number_check "
                            "CHECK (token_gen_number >= 0);")

            session.execute("ALTER TABLE tasks "
                            "ALTER COLUMN token_initial "
                            "DROP NOT NULL;")
            session.execute("ALTER TABLE tasks "
                            "ADD CONSTRAINT tasks_token_initial_check "
                            "CHECK (token_initial >= 0);")
            session.execute("ALTER TABLE tasks "
                            "ADD CONSTRAINT tasks_token_max_check "
                            "CHECK (token_max >= 0);")
            session.execute("ALTER TABLE tasks "
                            "ADD CONSTRAINT tasks_token_total_check "
                            "CHECK (token_total >= 0);")
            session.execute("ALTER TABLE tasks "
                            "ADD CONSTRAINT tasks_token_min_interval_check "
                            "CHECK (token_min_interval >= 0);")
            session.execute("ALTER TABLE tasks "
                            "ADD CONSTRAINT tasks_token_gen_time_check "
                            "CHECK (token_gen_time > 0);")
            session.execute("ALTER TABLE tasks "
                            "ADD CONSTRAINT tasks_token_gen_number_check "
                            "CHECK (token_gen_number >= 0);")

    @staticmethod
    def add_ignore_on_questions():
        """Possibility to ignore users' questions.

        We simply add a field "ignored" in the questions table.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE questions "
                            "ADD COLUMN ignored BOOLEAN;")
            session.execute("UPDATE questions SET ignored = False;")
            session.execute("ALTER TABLE questions "
                            "ALTER COLUMN ignored SET NOT NULL;")

    @staticmethod
    def split_first_and_last_names():
        """Use two fields for the name instead of one.

        'Last' name is intended to be used as a family name (or anyhow
        the name you want to use to sort first); 'first' name is the
        given name (if any).

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE users ADD COLUMN first_name VARCHAR;")
            session.execute("ALTER TABLE users ADD COLUMN last_name VARCHAR;")
            session.execute("ALTER TABLE users ADD COLUMN email VARCHAR;")

            for user_id, user_real_name in session.execute("SELECT "
                                                           "id, real_name "
                                                           "FROM users;"):
                split_names = user_real_name.split()
                if len(split_names) == 0:
                    first_name = ""
                    last_name = ""
                elif len(split_names) == 1:
                    first_name = ""
                    last_name = split_names[0]
                else:
                    first_name = split_names[0]
                    last_name = " ".join(split_names[1:])
                session.execute("UPDATE users SET "
                                "first_name = :first_name, "
                                "last_name = :last_name, "
                                "email = '' "
                                "WHERE id = :user_id",
                                {
                                  "first_name": first_name,
                                  "last_name": last_name,
                                  "user_id": user_id,
                                })
            session.execute("ALTER TABLE users "
                            "ALTER COLUMN first_name SET NOT NULL;")
            session.execute("ALTER TABLE users "
                            "ALTER COLUMN last_name SET NOT NULL;")
            session.execute("ALTER TABLE users "
                            "ALTER COLUMN email SET NOT NULL;")
            session.execute("ALTER TABLE users DROP COLUMN real_name;")

    @staticmethod
    def changed_batch_parameters():
        """Params for Batch tasktype changed. Warning: read full doc!

        The parameters for Batch task type have been
        rationalized. Note that the duty and semantic of the grader
        have changed in a complete way - you cannot use old grader
        with the new semantic.

        """
        import simplejson as json
        with SessionGen(commit=True) as session:
            for task_id, task_type_parameters in session.execute(
                "SELECT id, task_type_parameters "
                "FROM tasks WHERE task_type = 'Batch';"):
                try:
                    parameters = json.loads(task_type_parameters)
                except json.decoder.JSONDecodeError:
                    raise ValueError("Unable to decode parameter string "
                                     "`%s'." % task_type_parameters)
                if parameters == ["diff", "nofile"]:
                    parameters = ["alone", "nofile", "diff"]
                elif parameters == ["diff", "file"]:
                    parameters = ["alone", "file", "diff"]
                elif parameters == ["comp", "nofile"]:
                    parameters = ["alone", "nofile", "comparator"]
                elif parameters == ["comp", "file"]:
                    parameters = ["alone", "nofile", "comparator"]
                elif parameters == ["grad"]:
                    parameters = ["grader", "file", "diff"]
                    print "WARNING: grader semantic changed, please " \
                          "read the documentation."
                else:
                    raise ValueError("Parameter string `%s' not recognized." %
                                     parameters)

                session.execute("UPDATE tasks SET "
                                "task_type_parameters = :parameters "
                                "WHERE id = :task_id",
                                {
                                   "parameters": json.dumps(parameters),
                                   "task_id": task_id
                                })


def execute_single_script(scripts_container, script):
    """Execute one script. Exit on errors.

    scripts_container (ScriptContainer): the list of scripts.
    script (string): the script name.

    """
    if script in scripts_container:
        print "Executing script %s..." % script
        try:
            scripts_container[script]()
        except Exception as error:
            print "Error received, aborting: %r" % error
            sys.exit(1)
        else:
            print "Script executed successfully"
    else:
        print "Script %s not found, aborting" % script
        sys.exit(1)


def main():
    """Parse arguments and call scripts.

    """
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

    something_done = False
    scripts_container = ScriptsContainer()
    if args.list:
        scripts_container.print_list()
        something_done = True

    for script in args.execute_script:
        execute_single_script(scripts_container, script)
        something_done = True

    if args.execute_scripts_since is not None:
        something_done = True
        if len(args.execute_scripts_since) == 8:
            scripts = scripts_container.get_scripts(
                starting_from=args.execute_scripts_since)
            for _date, script in scripts:
                execute_single_script(scripts_container, script)
        else:
            print "Invalid date format (should be YYYYMMDD)."
            sys.exit(1)

    if not something_done:
        parser.print_help()


if __name__ == "__main__":
    main()
