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

"""Contest-related database interface for SQLAlchemy. Not to be used
directly (import it from SQLAlchemyAll).

"""

import time

from sqlalchemy import Column, ForeignKey, Integer, String, CheckConstraint
from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import Base


class Contest(Base):
    """Class to store a contest (which is a single day of a
    programming competition). Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'contests'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Short name of the contest, and longer description. Both human
    # readable.
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Follows the enforcement of token for any person, for all the
    # task. This enforcements add up to the ones defined task-wise.

    # token_initial is the initial number of tokens available, or None
    # to disable completely the tokens.
    token_initial = Column(
        Integer, CheckConstraint("token_initial >= 0"), nullable=True)
    # token_max is the maximum number in any given time, or None not
    # to enforce this limitation.
    token_max = Column(
        Integer, CheckConstraint("token_max >= 0"), nullable=True)
    # token_total is the maximum number that can be used in the whole
    # contest, or None not to enforce this limitation.
    token_total = Column(
        Integer, CheckConstraint("token_total >= 0"), nullable=True)
    # token_min_interval is the minimum interval in seconds between
    # two uses of a token, or None not to enforce this limitation.
    token_min_interval = Column(
        Integer, CheckConstraint("token_min_interval >= 0"), nullable=True)
    # Every token_gen_time minutes from the beginning of the contest
    # we generate token_gen_number tokens, or we don't if either is
    # None.
    token_gen_time = Column(
        Integer, CheckConstraint("token_gen_time > 0"), nullable=True)
    token_gen_number = Column(
        Integer, CheckConstraint("token_gen_number >= 0"), nullable=True)

    # Beginning and ending of the contest, unix times.
    start = Column(Integer, nullable=True)
    stop = Column(Integer, nullable=True)

    # Max contest time for each user in seconds.
    per_user_time = Column(Integer, nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # tasks (list of Task objects)
    # announcements (list of Announcement objects)
    # ranking_view (RankingView object)
    # users (list of User objects)

    # Moreover, we have the following methods.
    # get_submissions (defined in SQLAlchemyAll)
    # create_empty_ranking_view (defined in SQLAlchemyAll)
    # update_ranking_view (defined in SQLAlchemyAll)

    def __init__(self, name, description, tasks, users,
                 token_initial=0, token_max=0, token_total=0,
                 token_min_interval=0,
                 token_gen_time=60, token_gen_number=1,
                 start=None, stop=None, per_user_time=None,
                 announcements=None, ranking_view=None):
        self.name = name
        self.description = description
        self.tasks = tasks
        self.users = users
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.token_gen_number = token_gen_number
        self.start = start
        self.stop = stop
        self.per_user_time = per_user_time
        self.announcements = announcements if announcements is not None else []
        self.ranking_view = ranking_view

    def export_to_dict(self, skip_submissions=False):
        """Return object data as a dictionary.

        """
        return {'name':               self.name,
                'description':        self.description,
                'tasks':              [task.export_to_dict()
                                       for task in self.tasks],
                'users':              [user.export_to_dict(skip_submissions)
                                       for user in self.users],
                'token_initial':      self.token_initial,
                'token_max':          self.token_max,
                'token_total':        self.token_total,
                'token_min_interval': self.token_min_interval,
                'token_gen_time':     self.token_gen_time,
                'token_gen_number':   self.token_gen_number,
                'start':              self.start,
                'stop':               self.stop,
                'per_user_time':      self.per_user_time,
                'announcements':      [announcement.export_to_dict()
                                       for announcement in self.announcements],
                'ranking_view':       self.ranking_view.export_to_dict()}

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

    def enumerate_files(self, skip_submissions=False, light=False):
        """Enumerate all the files (by digest) referenced by the
        contest.

        return (set): a set of strings, the digests of the file
                      referenced in the contest.

        """
        # Here we cannot use yield, because we want to detect
        # duplicates
        files = set()
        for task in self.tasks:

            # Enumerate attachments
            for _file in task.attachments.values():
                files.add(_file.digest)

            # Enumerate managers
            for _file in task.managers.values():
                files.add(_file.digest)

            # Enumerate testcases
            if not light:
                for testcase in task.testcases:
                    files.add(testcase.input)
                    files.add(testcase.output)

            # Enumerate statements
            for a,_file in task.statements.iteritems():
	            files.add(_file.digest)
            # FIXME It works, but I'm not sure if it does what it should do

        if not skip_submissions:
            for submission in self.get_submissions():

                # Enumerate files
                for _file in submission.files.values():
                    files.add(_file.digest)

                # Enumerate executables
                if not light:
                    for _file in submission.executables.values():
                        files.add(_file.digest)

        return files

    def phase(self, timestamp):
        """Return: -1 if contest isn't started yet at time timestamp,
                    0 if the contest is active at time timestamp,
                    1 if the contest has ended.

        timestamp (int): the time we are iterested in.
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

        token_timestamps (list): list of timestamps of used tokens.
        token_* (int): the parameters we want to enforce.
        start (int): the time from which we start accumulating tokens.
        timestamp (int): the time relative to which make the
                         calculation.
        return (tuple): same as tokens_available.

        """
        # If we already played the total number allowed, we don't have
        # anything left.
        played_tokens = len(token_timestamps)
        if token_total is not None and played_tokens >= token_total:
            return (0, None, None)

        # If token_initial is None, it means that the admin disabled
        # tokens usage, hence no tokens.
        if token_initial is None:
            return (0, None, None)

        # Now that we already considered the number of tokens already
        # played, we can put a semaphore at the end of the list.
        END_OF_THE_WORLD = 2000000000
        token_timestamps.append(END_OF_THE_WORLD)

        # avail is the current number of available tokens. We are
        # going to rebuild all the history to know how many of them we
        # have now.

        # We start with the initial number, capped to max. *_initial
        # can be ignored after this.
        avail = token_initial
        if token_max is not None:
            avail = min(avail, token_max)

        # If token_gen_number is None, we may as well consider it 0.
        if token_gen_number is None:
            token_gen_number = 0

        # This is the index of the first non-yet-considered played
        # token.
        tokens_index = 0

        # This is the next expiring time for *_min_intervals. Note
        # that since we assume token were played by the rule, we need
        # not to think of these as critical times. At the end of the
        # simulation, we know that all min_intervals will be expired
        # at this time (and not a second before).
        expiration = 0

        # Previous time we considered
        prev_critical_time = start

        def generate_tokens(prev_time, next_time):
            """Compute how many tokens have been generated between the
            two timestamps.

            prev_time (int): timestamp of begin of interval.
            next_time (int): timestamp of end of interval.
            return (int): number of tokens generated.

            """
            if token_gen_time is not None:
                # How many generation times we passed from start to
                # the previous considered time?
                before_prev = int((prev_time - start) / (token_gen_time * 60))
                # And from start to the current considered time?
                before_next = int((next_time - start) / (token_gen_time * 60))
                # So...
                return token_gen_number * (before_next - before_prev)
            else:
                return 0

        # Simulating!
        while True:
            next_critical_time = min(token_timestamps[tokens_index],
                                     timestamp)

            # Increment the number of tokens 'cause of generation.
            avail += generate_tokens(prev_critical_time, next_critical_time)
            if token_max is not None:
                avail = min(avail, token_max)

            # If the user played a token, we decrease the available
            # tokens, and set that all min_intervals will expire at
            # expiration. Also we pass to the next token.
            if next_critical_time == token_timestamps[tokens_index]:
                avail -= 1
                if token_min_interval is not None:
                    expiration = next_critical_time + token_min_interval
                tokens_index += 1

            # Yay, simulation concluded.
            if next_critical_time == timestamp:
                break

            prev_critical_time = next_critical_time

        # Compute the time in which the next token will be generated.
        next_gen_time = None
        if token_gen_time is not None and token_gen_number > 0 and \
                (token_max is None or avail < token_max):
            next_gen_time = start + token_gen_time * 60 * \
                            int((timestamp - start) /
                                (token_gen_time * 60) + 1)

        # If we have more tokens than how many we are allowed to play,
        # cap it, and note that no more will be generated.
        if token_total is not None:
            if avail >= token_total - played_tokens:
                avail = token_total - played_tokens
                next_gen_time = None

        return (avail,
                next_gen_time,
                expiration if expiration > timestamp
                else None)

    def tokens_available(self, username, task_name, timestamp=None):
        """Return three pieces of data:

        [0] the number of available tokens for the user to play on the
            task (independently from the fact that (s)he can play it
            right now or not due to a min_interval wating for
            expiration);

        [1] the next time in which a token will be generated (or
            None); from the user perspective, i.e.: if the user will
            do nothing, [1] is the first time in which his number of
            available tokens will be greater than [0];

        [2] the time when the min_interval will expire, or None

        In particular, let r the return value of this method. We can
        sketch the code in the following way.:

        if r[0] > 0 and r[2] is None:
            we can play a token
            if r[1] is not None:
                next one will be generated at r[1]
            else:
                no other tokens will be generated (max/total reached ?)
        elif r[0] > 0:
            we must wait till r[2] to play the token
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
        timestamp (int): the time relative to which making the
                         calculation
        return ((int, int, int)): see description above the latter two
                                  are timestamps, or None.

        """
        if timestamp is None:
            timestamp = int(time.time())

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
        res = []

        # The available tokens are the minimum.
        res.append(min(res_contest[0], res_task[0]))

        # Next token generation time
        if res_contest[0] < res_task[0]:
            # In this case, we just need a contest-wise token to be
            # generated.
            res.append(res_contest[1])
        if res_task[0] < res_contest[0]:
            # Specular case.
            res.append(res_task[1])
        else:
            # Darn, we need both!
            if res_contest[1] is None or res_task[1] is None:
                res.append(None)
            else:
                res.append(max(res_contest[1], res_task[1]))

        # Finally, both min_intervals must expire.
        if res_contest[2] is None or res_task[2] is None:
            res.append(None)
        else:
            res.append(max(res_contest[2], res_task[2]))

        return tuple(res)


class Announcement(Base):
    """Class to store a messages sent by the contest managers to all
    the users. Not to be used directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'announcements'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Time, subject and text of the announcements.
    timestamp = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)

    # Contest for which the announcements are.
    contest_id = Column(Integer,
                        ForeignKey(Contest.id,
                                   onupdate="CASCADE",
                                   ondelete="CASCADE"),
                        nullable=False,
                        index=True)
    contest = relationship(Contest,
                           backref=backref(
                               'announcements',
                               single_parent=True,
                               order_by=[timestamp],
                               cascade="all, delete, delete-orphan"))

    def __init__(self, timestamp, subject, text, contest=None):
        self.timestamp = timestamp
        self.subject = subject
        self.text = text
        self.contest = contest

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'timestamp': self.timestamp,
                'subject':   self.subject,
                'text':      self.text}
