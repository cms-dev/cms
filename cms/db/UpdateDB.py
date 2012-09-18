#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
            ("20120313", "changed_batch_iofile_parameters"),
            ("20120319", "change_scoretype_names"),
            ("20120412", "add_unique_constraints"),
            ("20120414", "add_evaluation_memory_time"),
            ("20120701", "add_statements"),
            ("20120712", "change_token_constraints"),
            ("20120714", "drop_ranking_view"),
            ("20120717", "use_timestamps"),
            ("20120721", "use_UTC_timestamps"),
            ("20120723", "add_timezones"),
            ("20120724", "add_languages"),
            ("20120805", "support_output_only"),
            ("20120823", "add_user_tests"),
            ("20120824", "add_evaluation_text_to_user_test"),
            ("20120911", "add_submission_and_usertest_limits"),
            ("20120912", "make_contest_description_not_null"),
            ("20120915", "add_extra_time"),
            ("20120918", "use_statement_ids"),
            ("20120919", "add_ranking_score_details"),
            ("20120923", "add_time_and_memory_on_tests"),
            ]
        self.list.sort()

    def __contains__(self, script):
        """Implement the 'script in sc' syntax.

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

    @staticmethod
    def changed_batch_iofile_parameters():
        """Params for Batch tasktype changed to support custom I/O filenames.
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
                if parameters[1] == "file":
                    parameters[1] = ["input.txt", "output.txt"]
                elif parameters[1] == "nofile":
                    parameters[1] = ["", ""]
                elif isinstance(parameters[1], list):
                    print "WARNING: already updated or unrecognized "\
                        "parameters in task %d" % task_id
                else:
                    raise ValueError("I/O type `%s' not recognized." %
                                     parameters[1])

                session.execute("UPDATE tasks SET "
                                "task_type_parameters = :parameters "
                                "WHERE id = :task_id",
                                {
                                   "parameters": json.dumps(parameters),
                                   "task_id": task_id
                                })

    @staticmethod
    def change_scoretype_names():
        """Remove the ScoreType prefix from every score type name.

        """
        with SessionGen(commit=True) as session:
            for score_type in ["Sum", "Relative",
                               "GroupMin", "GroupMul"]:
                session.execute("UPDATE tasks SET score_type = '%s' "
                                "WHERE score_type = 'ScoreType%s';" %
                                (score_type, score_type))

    @staticmethod
    def add_unique_constraints():
        """Add a bunch of constraints to the DB...

        ...that we were too lazy to do right away. See code for the
        constraints.

        """
        # First value of the pair is the table name, the second is the
        # list of columns.
        constraints = [["attachments", ["task_id", "filename"]],
                       ["evaluations", ["submission_id", "num"]],
                       ["executables", ["submission_id", "filename"]],
                       ["files", ["submission_id", "filename"]],
                       ["managers", ["task_id", "filename"]],
                       ["scores", ["rankingview_id", "task_id", "user_id"]],
                       ["task_testcases", ["task_id", "num"]],
                       ["tasks", ["contest_id", "num"]],
                       ["tokens", ["submission_id"]],
                       ["users", ["contest_id", "username"]],
                       ["tasks", ["contest_id", "name"]],
                       ]

        with SessionGen(commit=True) as session:
            for table, columns in constraints:
                name = "cst_" + table + "_" + "_".join(columns)
                columns_list = "(" + ", ".join(columns) + ")"
                session.execute("ALTER TABLE %s "
                                "ADD CONSTRAINT %s "
                                "UNIQUE %s;" % (table, name, columns_list))

    @staticmethod
    def add_evaluation_memory_time():
        """Support for storing resource usage of submissions.

        We allow an evaluation to store a memory usage, an evaluation
        time and a wall clock time.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE evaluations "
                            "ADD COLUMN memory_used INTEGER;")
            session.execute("ALTER TABLE evaluations "
                            "ADD COLUMN execution_time FLOAT;")
            session.execute("ALTER TABLE evaluations "
                            "ADD COLUMN execution_wall_clock_time FLOAT;")

    @staticmethod
    def add_statements():
        """Support for statement translations.

        Add external Statement objects to support statement translations.
        The "official" statement is identified by its language code.

        """
        with SessionGen(commit=True) as session:
            session.execute("""\
CREATE TABLE IF NOT EXISTS statements (
    id SERIAL NOT NULL,
    language VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    task_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT cst_statements_task_id_language UNIQUE (task_id, language),
    FOREIGN KEY(task_id) REFERENCES tasks (id)
    ON DELETE CASCADE ON UPDATE CASCADE
)""")
            session.execute("DROP INDEX IF EXISTS ix_statements_task_id;")
            session.execute("CREATE INDEX ix_statements_task_id "
                            "ON statements (task_id)")
            for task_id, digest in session.execute(
                "SELECT id, statement FROM tasks;"):
                session.execute("INSERT INTO statements "
                                "(language, digest, task_id) "
                                "VALUES ('', '%s', %s);" % (digest, task_id))
            session.execute("ALTER TABLE tasks "
                            "DROP COLUMN statement;")
            session.execute("ALTER TABLE tasks "
                            "ADD COLUMN official_language VARCHAR;")
            session.execute("UPDATE tasks "
                            "SET official_language = '';")
            session.execute("ALTER TABLE tasks "
                            "ALTER COLUMN official_language SET NOT NULL;")

    @staticmethod
    def change_token_constraints():
        """Fix token constraints to avoid ambiguos corner cases.

        Set some token_* fields to != None or to != zero since these
        values would cause a "behavior" (from the user-perspective)
        that is identical to other, more "reasonable" and natural
        value combinations.

        """
        with SessionGen(commit=True) as session:
            for table in ["contests", "tasks"]:
                session.execute("""
UPDATE %s
SET token_initial = token_max
WHERE token_initial > token_max;
""" % table)
                session.execute("""
UPDATE %s
SET (token_initial, token_max, token_total) = (NULL, NULL, NULL)
WHERE token_max = 0 OR token_total = 0;
""" % table)
                session.execute("""
UPDATE %s
SET token_min_interval = 0
WHERE token_min_interval IS NULL;
""" % table)
                session.execute("""
UPDATE %s
SET (token_gen_time, token_gen_number) = (1, 0)
WHERE token_gen_time IS NULL OR token_gen_number IS NULL;
""" % table)
            session.execute("""
ALTER TABLE contests
ADD CONSTRAINT contests_check CHECK (token_initial <= token_max),
DROP CONSTRAINT contests_token_max_check,
DROP CONSTRAINT contests_token_total_check,
DROP CONSTRAINT contests_token_gen_time_check,
ADD CONSTRAINT contests_token_max_check CHECK (token_max > 0),
ADD CONSTRAINT contests_token_total_check CHECK (token_total > 0),
ADD CONSTRAINT contests_token_gen_time_check CHECK (token_gen_time >= 0),
ALTER COLUMN token_min_interval SET NOT NULL,
ALTER COLUMN token_gen_time SET NOT NULL,
ALTER COLUMN token_gen_number SET NOT NULL;
""")
            session.execute("""
ALTER TABLE tasks
ADD CONSTRAINT tasks_check CHECK (token_initial <= token_max),
DROP CONSTRAINT tasks_token_max_check,
DROP CONSTRAINT tasks_token_total_check,
DROP CONSTRAINT tasks_token_gen_time_check,
ADD CONSTRAINT tasks_token_max_check CHECK (token_max > 0),
ADD CONSTRAINT tasks_token_total_check CHECK (token_total > 0),
ADD CONSTRAINT tasks_token_gen_time_check CHECK (token_gen_time >= 0),
ALTER COLUMN token_min_interval SET NOT NULL,
ALTER COLUMN token_gen_time SET NOT NULL,
ALTER COLUMN token_gen_number SET NOT NULL;
""")

    @staticmethod
    def drop_ranking_view():
        """Remove the useless tables.

        Ranking views and the accessory scores tables were intended to
        be used, but this is not true anymore.

        """
        with SessionGen(commit=True) as session:
            session.execute("DROP TABLE scores;")
            session.execute("DROP TABLE rankingviews;")

    @staticmethod
    def use_timestamps():
        """Use TIMESTAMP column type for columns that represent datetimes

        And INTERVAL for columns that represent timedeltas.

        """
        with SessionGen(commit=True) as session:
            for table, column in [("contests", "start"),
                                  ("contests", "stop"),
                                  ("announcements", "timestamp"),
                                  ("submissions", "timestamp"),
                                  ("tokens", "timestamp"),
                                  ("users", "starting_time"),
                                  ("messages", "timestamp"),
                                  ("questions", "question_timestamp"),
                                  ("questions", "reply_timestamp")]:
                session.execute("""
ALTER TABLE %(table)s
ALTER %(column)s TYPE timestamp USING to_timestamp(%(column)s);
""" % {"table": table, "column": column})

            session.execute("""
ALTER TABLE contests
ALTER per_user_time TYPE interval USING per_user_time * '1 second'::interval,
ALTER token_min_interval TYPE interval USING token_min_interval * '1 second'::interval,
ALTER token_gen_time TYPE interval USING token_gen_time * '1 minute'::interval,
DROP CONSTRAINT contests_token_min_interval_check,
DROP CONSTRAINT contests_token_gen_time_check,
ADD CONSTRAINT contests_token_min_interval_check CHECK (token_min_interval >= '0 seconds'),
ADD CONSTRAINT contests_token_gen_time_check CHECK (token_gen_time >= '0 seconds');
""")
            session.execute("""
ALTER TABLE tasks
ALTER token_min_interval TYPE interval USING token_min_interval * '1 second'::interval,
ALTER token_gen_time TYPE interval USING token_gen_time * '1 minute'::interval,
DROP CONSTRAINT tasks_token_min_interval_check,
DROP CONSTRAINT tasks_token_gen_time_check,
ADD CONSTRAINT tasks_token_min_interval_check CHECK (token_min_interval >= '0 seconds'),
ADD CONSTRAINT tasks_token_gen_time_check CHECK (token_gen_time >= '0 seconds');
""")

    @staticmethod
    def use_UTC_timestamps():
        """Convert TIMESTAMP columns to represent UTC times

        Instead of using local time.

        """
        with SessionGen(commit=True) as session:
            for table, column in [("contests", "start"),
                                  ("contests", "stop"),
                                  ("announcements", "timestamp"),
                                  ("submissions", "timestamp"),
                                  ("tokens", "timestamp"),
                                  ("users", "starting_time"),
                                  ("messages", "timestamp"),
                                  ("questions", "question_timestamp"),
                                  ("questions", "reply_timestamp")]:
                session.execute("""
UPDATE %(table)s
SET %(column)s = CAST(%(column)s AS TIMESTAMP WITH TIME ZONE) AT TIME ZONE 'UTC';
""" % {"table": table, "column": column})

    @staticmethod
    def add_timezones():
        """Add support for per-contest and per-user timezones

        By adding the Contest.timezone and User.timezone fields.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE contests "
                            "ADD COLUMN timezone VARCHAR;")
            session.execute("ALTER TABLE users "
                            "ALTER timezone DROP NOT NULL,"
                            "ALTER timezone TYPE VARCHAR USING NULL;")

    @staticmethod
    def add_languages():
        """Add a list of languages to each user

        Defaults to empty list.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE users "
                            "ADD COLUMN languages VARCHAR[];")
            session.execute("UPDATE users "
                            "SET languages = '{}';")
            session.execute("ALTER TABLE users "
                            "ALTER COLUMN languages SET NOT NULL;")

    @staticmethod
    def support_output_only():
        """Increase support for output only tasks

        By allowing NULL time and memory limits

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE tasks "
                            "ALTER COLUMN time_limit DROP NOT NULL,"
                            "ALTER COLUMN memory_limit DROP NOT NULL;")

    @staticmethod
    def add_user_tests():
        """Add the table user_tests and related.

        """
        with SessionGen(commit=False) as session:
            session.execute("""\
CREATE TABLE IF NOT EXISTS user_tests (
    id SERIAL NOT NULL,
    user_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    language VARCHAR,
    input VARCHAR NOT NULL,
    output VARCHAR,
    compilation_outcome VARCHAR,
    compilation_text VARCHAR,
    compilation_tries INTEGER NOT NULL,
    compilation_shard INTEGER,
    compilation_sandbox VARCHAR,
    evaluation_outcome VARCHAR,
    evaluation_tries INTEGER NOT NULL,
    evaluation_shard INTEGER,
    evaluation_sandbox VARCHAR,
    PRIMARY KEY (id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);""")
            session.execute("""\
DROP INDEX IF EXISTS ix_user_tests_task_id;""")
            session.execute("""\
CREATE INDEX ix_user_tests_task_id ON user_tests (task_id);""")
            session.execute("""\
DROP INDEX IF EXISTS ix_user_tests_user_id;""")
            session.execute("""\
CREATE INDEX ix_user_tests_user_id ON user_tests (user_id);""")

            session.execute("""\
CREATE TABLE IF NOT EXISTS user_test_executables (
    id SERIAL NOT NULL,
    filename VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    user_test_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_test_id) REFERENCES user_tests(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);""")
            session.execute("""\
DROP INDEX IF EXISTS cst_executables_user_test_id_filename;""")
            session.execute("""\
CREATE UNIQUE INDEX cst_executables_user_test_id_filename ON user_test_executables (user_test_id, filename);""")
            session.execute("""\
DROP INDEX IF EXISTS ix_user_test_executables_user_test_id;""")
            session.execute("""\
CREATE INDEX ix_user_test_executables_user_test_id ON user_test_executables (user_test_id);""")

            session.execute("""\
CREATE TABLE user_test_files (
    id SERIAL NOT NULL,
    filename VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    user_test_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_test_id) REFERENCES user_tests(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);""")
            session.execute("""\
DROP INDEX IF EXISTS cst_files_user_test_id_filename;""")
            session.execute("""\
CREATE UNIQUE INDEX cst_files_user_test_id_filename ON user_test_files (user_test_id, filename);""")
            session.execute("""\
DROP INDEX IF EXISTS ix_user_test_files_user_test_id;""")
            session.execute("""\
CREATE INDEX ix_user_test_files_user_test_id ON user_test_files (user_test_id);""")

            session.execute("""\
CREATE TABLE user_test_managers (
    id SERIAL NOT NULL,
    filename VARCHAR NOT NULL,
    digest VARCHAR NOT NULL,
    user_test_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_test_id) REFERENCES user_tests(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);""")
            session.execute("""\
DROP INDEX IF EXISTS cst_managers_user_test_id_filename;""")
            session.execute("""\
CREATE UNIQUE INDEX cst_managers_user_test_id_filename ON user_test_managers (user_test_id, filename);""")
            session.execute("""\
DROP INDEX IF EXISTS ix_user_test_managers_user_test_id;""")
            session.execute("""\
CREATE INDEX ix_user_test_managers_user_test_id ON user_test_managers (user_test_id);""")

            session.commit()

    @staticmethod
    def add_evaluation_text_to_user_test():
        """Add the evaluation_text column to table user tests.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE user_tests "
                            "ADD COLUMN evaluation_text VARCHAR;")

    @staticmethod
    def add_submission_and_usertest_limits():
        """Add limits to the total number and the frequency of
        submissions and usertests.

        """
        with SessionGen(commit=True) as session:
            session.execute("""\
ALTER TABLE contests
ADD COLUMN max_submission_number INTEGER,
ADD COLUMN max_usertest_number INTEGER,
ADD COLUMN min_submission_interval INTERVAL,
ADD COLUMN min_usertest_interval INTERVAL;""")
            session.execute("""\
ALTER TABLE tasks
ADD COLUMN max_submission_number INTEGER,
ADD COLUMN max_usertest_number INTEGER,
ADD COLUMN min_submission_interval INTERVAL,
ADD COLUMN min_usertest_interval INTERVAL;""")
        print "Please remove 'min_submission_interval' from your configuration."
        print "It is now possible to set it on a per-task and per-contest basis using AWS."

    @staticmethod
    def make_contest_description_not_null():
        """Make the Contest.description field NOT NULL.

        """
        with SessionGen(commit=True) as session:
            session.execute("""\
UPDATE contests
SET description = '' WHERE description IS NULL;""")
            session.execute("""\
ALTER TABLE contests
ALTER COLUMN description SET NOT NULL;""")

    @staticmethod
    def add_extra_time():
        """Add extra time for the users

        Defaults to zero.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE users "
                            "ADD COLUMN extra_time INTERVAL;")
            session.execute("UPDATE users "
                            "SET extra_time = '0 seconds';")
            session.execute("ALTER TABLE users "
                            "ALTER COLUMN extra_time SET NOT NULL;")

    @staticmethod
    def use_statement_ids():
        """Move user.languages to user.statements

        Use Statement IDs instead of language codes.

        """
        with SessionGen(commit=True) as session:
            session.execute("""\
ALTER TABLE users
DROP COLUMN languages,
ADD COLUMN statements INTEGER[];""")
            session.execute("""\
UPDATE users
SET statements = '{}'""")
            session.execute("""\
ALTER TABLE users
ALTER COLUMN statements SET NOT NULL;""")

    @staticmethod
    def add_ranking_score_details():
        """Add a field with the score details to send to RWS

        Please rescore solutions.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE submissions "
                            "ADD COLUMN ranking_score_details VARCHAR;")

    @staticmethod
    def add_time_and_memory_on_tests():
        """Add memory_used and execution_time on UserTests.

        """
        with SessionGen(commit=True) as session:
            session.execute("ALTER TABLE user_tests "
                            "ADD COLUMN memory_used INTEGER, "
                            "ADD COLUMN execution_time DOUBLE PRECISION;")


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
