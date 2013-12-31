#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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

"""Contest-related database interface for SQLAlchemy.

"""

from __future__ import absolute_import

from datetime import timedelta

from sqlalchemy.schema import Column, ForeignKey, CheckConstraint
from sqlalchemy.types import Integer, Unicode, DateTime, Interval
from sqlalchemy.orm import relationship, backref

from . import Base, RepeatedUnicode

from cms import DEFAULT_LANGUAGES
from cmscommon.datetime import make_datetime


class Contest(Base):
    """Class to store a contest (which is a single day of a
    programming competition).

    """
    __tablename__ = 'contests'
    __table_args__ = (
        CheckConstraint("start <= stop"),
        CheckConstraint("token_initial <= token_max"),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Short name of the contest, and longer description. Both human
    # readable.
    name = Column(
        Unicode,
        nullable=False)
    description = Column(
        Unicode,
        nullable=False)

    # The list of languages shorthand allowed in the contest,
    # e.g. cpp. The codes must be the same as those in cms.LANGUAGES.
    languages = Column(
        RepeatedUnicode(),
        nullable=False,
        default=DEFAULT_LANGUAGES)

    # Follows the enforcement of token for any person, for all the
    # task. This enforcements add up to the ones defined task-wise.

    # token_initial is the initial number of tokens available, or None
    # to disable completely the tokens.
    token_initial = Column(
        Integer,
        CheckConstraint("token_initial >= 0"),
        nullable=True)
    # token_max is the maximum number in any given time, or None not
    # to enforce this limitation.
    token_max = Column(
        Integer,
        CheckConstraint("token_max > 0"),
        nullable=True)
    # token_total is the maximum number that can be used in the whole
    # contest, or None not to enforce this limitation.
    token_total = Column(
        Integer,
        CheckConstraint("token_total > 0"),
        nullable=True)
    # token_min_interval is the minimum interval in seconds between
    # two uses of a token (set it to 0 to not enforce any limitation).
    token_min_interval = Column(
        Interval,
        CheckConstraint("token_min_interval >= '0 seconds'"),
        nullable=False,
        default=timedelta())
    # Every token_gen_time from the beginning of the contest we generate
    # token_gen_number tokens. If _gen_number is 0 no tokens will be
    # generated, if _gen_number is > 0 and _gen_time is 0 tokens will be
    # infinite. In case of infinite tokens, the values of _initial, _max
    # and _total will be ignored (except when token_initial is None).
    token_gen_time = Column(
        Interval,
        CheckConstraint("token_gen_time >= '0 seconds'"),
        nullable=False,
        default=timedelta())
    token_gen_number = Column(
        Integer,
        CheckConstraint("token_gen_number >= 0"),
        nullable=False,
        default=0)

    # Beginning and ending of the contest.
    start = Column(
        DateTime,
        nullable=True)
    stop = Column(
        DateTime,
        nullable=True)

    # Timezone for the contest. All timestamps in CWS will be shown
    # using the timezone associated to the logged-in user or (if it's
    # None or an invalid string) the timezone associated to the
    # contest or (if it's None or an invalid string) the local
    # timezone of the server. This value has to be a string like
    # "Europe/Rome", "Australia/Sydney", "America/New_York", etc.
    timezone = Column(
        Unicode,
        nullable=True)

    # Max contest time for each user in seconds.
    per_user_time = Column(
        Interval,
        nullable=True)

    # Maximum number of submissions or user_tests allowed for each user
    # during the whole contest or None to not enforce this limitation.
    max_submission_number = Column(
        Integer,
        CheckConstraint("max_submission_number > 0"),
        nullable=True)
    max_user_test_number = Column(
        Integer,
        CheckConstraint("max_user_test_number > 0"),
        nullable=True)

    # Minimum interval between two submissions or user_tests, or None to
    # not enforce this limitation.
    min_submission_interval = Column(
        Interval,
        CheckConstraint("min_submission_interval > '0 seconds'"),
        nullable=True)
    min_user_test_interval = Column(
        Interval,
        CheckConstraint("min_user_test_interval > '0 seconds'"),
        nullable=True)

    # The scores for this contest will be rounded to this number of
    # decimal places.
    score_precision = Column(
        Integer,
        CheckConstraint("score_precision >= 0"),
        nullable=False,
        default=0)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # tasks (list of Task objects)
    # announcements (list of Announcement objects)
    # users (list of User objects)

    # Moreover, we have the following methods.
    # get_submissions (defined in __init__.py)
    # get_submission_results (defined in __init__.py)
    # get_user_tests (defined in __init__.py)
    # get_user_test_results (defined in __init__.py)

    # FIXME - Use SQL syntax
    def get_task(self, task_name):
        """Return the first task in the contest with the given name.

        task_name (string): the name of the task we are interested in.
        return (Task): the corresponding task object, or KeyError.

        """
        for task in self.tasks:
            if task.name == task_name:
                return task
        raise KeyError("Task not found")

    # FIXME - Use SQL syntax
    def get_task_index(self, task_name):
        """Return the index of the first task in the contest with the
        given name.

        task_name (string): the name of the task we are interested in.
        return (int): the index of the corresponding task, or
                      KeyError.

        """
        for idx, task in enumerate(self.tasks):
            if task.name == task_name:
                return idx
        raise KeyError("Task not found")

    # FIXME - Use SQL syntax
    def get_user(self, username):
        """Return the first user in the contest with the given name.

        username (string): the name of the user we are interested in.
        return (User): the corresponding user object, or KeyError.

        """
        for user in self.users:
            if user.username == username:
                return user
        raise KeyError("User not found")

    def enumerate_files(self, skip_submissions=False, skip_user_tests=False,
                        skip_generated=False):
        """Enumerate all the files (by digest) referenced by the
        contest.

        return (set): a set of strings, the digests of the file
                      referenced in the contest.

        """
        # Here we cannot use yield, because we want to detect
        # duplicates
        files = set()
        for task in self.tasks:

            # Enumerate statements
            for file_ in task.statements.itervalues():
                files.add(file_.digest)

            # Enumerate attachments
            for file_ in task.attachments.itervalues():
                files.add(file_.digest)

            # Enumerate managers
            for dataset in task.datasets:
                for file_ in dataset.managers.itervalues():
                    files.add(file_.digest)

            # Enumerate testcases
            for dataset in task.datasets:
                for testcase in dataset.testcases.itervalues():
                    files.add(testcase.input)
                    files.add(testcase.output)

        if not skip_submissions:
            for submission in self.get_submissions():

                # Enumerate files
                for file_ in submission.files.itervalues():
                    files.add(file_.digest)

                # Enumerate executables
                if not skip_generated:
                    for sr in submission.results:
                        for file_ in sr.executables.itervalues():
                            files.add(file_.digest)

        if not skip_user_tests:
            for user_test in self.get_user_tests():

                files.add(user_test.input)

                if not skip_generated:
                    for ur in user_test.results:
                        if ur.output is not None:
                            files.add(ur.output)

                # Enumerate files
                for file_ in user_test.files.itervalues():
                    files.add(file_.digest)

                # Enumerate managers
                for file_ in user_test.managers.itervalues():
                    files.add(file_.digest)

                # Enumerate executables
                if not skip_generated:
                    for ur in user_test.results:
                        for file_ in ur.executables.itervalues():
                            files.add(file_.digest)

        return files

    def phase(self, timestamp):
        """Return: -1 if contest isn't started yet at time timestamp,
                    0 if the contest is active at time timestamp,
                    1 if the contest has ended.

        timestamp (datetime): the time we are iterested in.
        return (int): contest phase as above.

        """
        if self.start is not None and self.start > timestamp:
            return -1
        if self.stop is None or self.stop > timestamp:
            return 0
        return 1

    @staticmethod
    def _tokens_available(token_timestamps, token_initial,
                          token_max, token_total, token_min_interval,
                          token_gen_time, token_gen_number,
                          start, timestamp):
        """Do exactly the same computation stated in tokens_available,
        but ensuring only a single set of token_* directive.
        Basically, tokens_available call this twice for contest-wise
        and task-wise parameters and then assemble the result.

        token_timestamps ([datetime]): list of timestamps of used
            tokens.
        token_* (int): the parameters we want to enforce.
        start (datetime): the time from which we start accumulating
            tokens.
        timestamp (datetime): the time relative to which make the
            calculation (has to be greater than or equal to all
            elements of token_timestamps).

        return ((int, datetime|None, datetime|None)): same as
            tokens_available.

        """
        # If token_initial is None, it means that the admin disabled
        # tokens usage, hence no tokens.
        if token_initial is None:
            return (0, None, None)

        # expiration is the timestamp at which all min_intervals for
        # the tokens played up to now have expired (i.e. the first
        # time at which we can play another token). If no tokens have
        # been played so far, this time is the start of the contest.
        expiration = \
            token_timestamps[-1] + token_min_interval \
            if len(token_timestamps) > 0 else start

        # If we have infinite tokens we don't need to simulate
        # anything, since nothing gets consumed or generated. We can
        # return immediately.
        if token_gen_number > 0 and token_gen_time == timedelta():
            return (-1, None, expiration if expiration > timestamp else None)

        # If we already played the total number allowed, we don't have
        # anything left.
        played_tokens = len(token_timestamps)
        if token_total is not None and played_tokens >= token_total:
            return (0, None, None)

        # If we're in the case "generate 0 tokens every 0 seconds" we
        # set the _gen_time to a non-zero value, to ease calculations.
        if token_gen_time == timedelta():
            token_gen_time = timedelta(seconds=1)

        # avail is the current number of available tokens. We are
        # going to rebuild all the history to know how many of them we
        # have now.
        # We start with the initial number (it's already capped to max
        # by the DB). token_initial can be ignored after this.
        avail = token_initial

        def generate_tokens(prev_time, next_time):
            """Compute how many tokens have been generated between the
            two timestamps.

            prev_time (datetime): timestamp of begin of interval.
            next_time (datetime): timestamp of end of interval.
            return (int): number of tokens generated.

            """
            # How many generation times we passed from start to
            # the previous considered time?
            before_prev = int((prev_time - start).total_seconds()
                              / token_gen_time.total_seconds())
            # And from start to the current considered time?
            before_next = int((next_time - start).total_seconds()
                              / token_gen_time.total_seconds())
            # So...
            return token_gen_number * (before_next - before_prev)

        # Previous time we considered
        prev_token = start

        # Simulating!
        for token in token_timestamps:
            # Increment the number of tokens because of generation.
            avail += generate_tokens(prev_token, token)
            if token_max is not None:
                avail = min(avail, token_max)

            # Play the token.
            avail -= 1

            prev_token = token

        avail += generate_tokens(prev_token, timestamp)
        if token_max is not None:
            avail = min(avail, token_max)

        # Compute the time in which the next token will be generated.
        next_gen_time = None
        if token_gen_number > 0 and (token_max is None or avail < token_max):
            next_gen_time = \
                start + token_gen_time * \
                int((timestamp - start).total_seconds() /
                    token_gen_time.total_seconds() + 1)

        # If we have more tokens than how many we are allowed to play,
        # cap it, and note that no more will be generated.
        if token_total is not None:
            if avail >= token_total - played_tokens:
                avail = token_total - played_tokens
                next_gen_time = None

        return (avail,
                next_gen_time,
                expiration if expiration > timestamp else None)

    def tokens_available(self, username, task_name, timestamp=None):
        """Return three pieces of data:

        [0] the number of available tokens for the user to play on the
            task (independently from the fact that (s)he can play it
            right now or not due to a min_interval wating for
            expiration); -1 means infinite tokens;

        [1] the next time in which a token will be generated (or
            None); from the user perspective, i.e.: if the user will
            do nothing, [1] is the first time in which his number of
            available tokens will be greater than [0];

        [2] the time when the min_interval will expire, or None

        In particular, let r the return value of this method. We can
        sketch the code in the following way.:

        if r[0] > 0 or r[0] == -1:
            we have tokens
            if r[2] is None:
                we can play a token
            else:
                we must wait till r[2] to play a token
            if r[1] is not None:
                next one will be generated at r[1]
            else:
                no other tokens will be generated (max/total reached ?)
        else:
            we don't have tokens right now
            if r[1] is not None:
                next one will be generated at r[1]
                if r[2] is not None and r[2] > r[1]:
                    but we must wait also till r[2] to play it
            else:
                no other tokens will be generated (max/total reached ?)

        Note also that this method assumes that all played tokens were
        regularly played, and that there are no tokens played in the
        future. Also, if r[0] == 0 and r[1] is None, then r[2] should
        be ignored.

        username (string): the username of the user.
        task_name (string): the name of the task.
        timestamp (datetime): the time relative to which making the
            calculation.

        return ((int, datetime|None, datetime|None)): see description
            above.

        """
        if timestamp is None:
            timestamp = make_datetime()

        user = self.get_user(username)
        task = self.get_task(task_name)

        # Take the list of the tokens already played (sorted by time).
        tokens = user.get_tokens()
        token_timestamps_contest = sorted([token.timestamp
                                           for token in tokens])
        token_timestamps_task = sorted([
            token.timestamp for token in tokens
            if token.submission.task.name == task_name])

        # If the contest is USACO-style (i.e., the time for each user
        # start when he/she logs in for the first time), then we start
        # accumulating tokens from the user starting time; otherwise,
        # from the start of the contest.
        start = self.start
        if self.per_user_time is not None:
            start = user.starting_time

        # Compute separately for contest-wise and task-wise.
        res_contest = Contest._tokens_available(
            token_timestamps_contest, self.token_initial,
            self.token_max, self.token_total, self.token_min_interval,
            self.token_gen_time, self.token_gen_number,
            start, timestamp)
        res_task = Contest._tokens_available(
            token_timestamps_task, task.token_initial,
            task.token_max, task.token_total, task.token_min_interval,
            task.token_gen_time, task.token_gen_number,
            start, timestamp)

        # Merge the results.

        # First, the "expiration".
        if res_contest[2] is None:
            expiration = res_task[2]
        elif res_task[2] is None:
            expiration = res_contest[2]
        else:
            expiration = max(res_task[2], res_contest[2])

        # Then, check if both are infinite
        if res_contest[0] == -1 and res_task[0] == -1:
            res = (-1, None, expiration)
        # Else, "combine" them appropriately.
        else:
            # Having infinite contest tokens, in this situation, is the
            # same as having a finite number that is strictly greater
            # than the task tokens. The same holds the other way, too.
            if res_contest[0] == -1:
                res_contest = (res_task[0] + 1, None, None)
            if res_task[0] == -1:
                res_task = (res_contest[0] + 1, None, None)

            # About next token generation time: we need to see when the
            # *minimum* between res_contest[0] and res_task[0] is
            # increased by one, so if there is an actual minimum we
            # need to consider only the next generation time for it.
            # Otherwise, if they are equal, we need both to generate an
            # additional token and we store the maximum between the two
            # next times of generation.
            if res_contest[0] < res_task[0]:
                # We have more task-tokens than contest-tokens.
                # We just need a contest-token to be generated.
                res = (res_contest[0], res_contest[1], expiration)
            elif res_task[0] < res_contest[0]:
                # We have more contest-tokens than task-tokens.
                # We just need a task-token to be generated.
                res = (res_task[0], res_task[1], expiration)
            else:
                # Darn, we need both!
                if res_contest[1] is None or res_task[1] is None:
                    res = (res_task[0], None, expiration)
                else:
                    res = (res_task[0], max(res_contest[1], res_task[1]),
                           expiration)

        return res


class Announcement(Base):
    """Class to store a messages sent by the contest managers to all
    the users.

    """
    __tablename__ = 'announcements'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time, subject and text of the announcement.
    timestamp = Column(
        DateTime,
        nullable=False)
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # Contest (id and object) owning the announcement.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    contest = relationship(
        Contest,
        backref=backref(
            'announcements',
            order_by=[timestamp],
            cascade="all, delete-orphan",
            passive_deletes=True))
