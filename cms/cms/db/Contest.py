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

"""Contest-related database interface for SQLAlchemy. Not to be used
directly (import it from SQLAlchemyAll).

"""

import time

from sqlalchemy import Column, ForeignKey, Integer, String
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
    # T_initial is the initial number, T_max is the maximum number in
    # any given time (or None to ignore), T_total is the maximum
    # number that can be used in the whole contest (or None),
    # T_min_interval the minimum interval in seconds between to uses
    # of a token (or None), Every T_gen_time minutes from the
    # beginning of the contest we generate T_gen_number tokens, or we
    # don't if either is None.
    token_initial = Column(Integer, nullable=False)
    token_max = Column(Integer, nullable=True)
    token_total = Column(Integer, nullable=True)
    token_min_interval = Column(Integer, nullable=True)
    token_gen_time = Column(Integer, nullable=True)
    token_gen_number = Column(Integer, nullable=True)

    # Beginning and ending of the contest, unix times.
    start = Column(Integer, nullable=True)
    stop = Column(Integer, nullable=True)

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
                 start=None, stop=None, announcements=None,
                 ranking_view=None):
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
        if announcements is None:
            announcements = []
        self.announcements = announcements
        self.ranking_view = ranking_view

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'name':               self.name,
                'description':        self.description,
                'tasks':              [task.export_to_dict()
                                       for task in self.tasks],
                'users':              [user.export_to_dict()
                                       for user in self.users],
                'token_initial':      self.token_initial,
                'token_max':          self.token_max,
                'token_min_interval': self.token_min_interval,
                'token_gen_time':     self.token_gen_time,
                'token_gen_number':   self.token_gen_number,
                'start':              self.start,
                'stop':               self.stop,
                'announcements':      [announcement.export_to_dict()
                                       for announcement in self.announcements],
                'ranking_view':       self.ranking_view.export_to_dict()}

    def get_task(self, task_name):
        """Return the first task in the contest with the given name.

        task_name (string): the name of the task we are interested in.
        return (Task): the corresponding task object, or KeyError.

        """
        for t in self.tasks:
            if t.name == task_name:
                return t
        raise KeyError("Task not found")

    def get_task_index(self, task_name):
        """Return the index of the first task in the contest with the
        given name.

        task_name (string): the name of the task we are interested in.
        return (int): the index of the corresponding task, or
                      KeyError.

        """
        for i, t in enumerate(self.tasks):
            if t.name == task_name:
                return i
        raise KeyError("Task not found")

    def get_user(self, username):
        """Return the first user in the contest with the given name.

        username (string): the name of the user we are interested in.
        return (User): the corresponding user object, or KeyError.

        """
        for u in self.users:
            if u.username == username:
                return u
        raise KeyError("User not found")

    def enumerate_files(self):
        """Enumerate all the files (by digest) referenced by the
        contest.

        return (set): a set of strings, the digests of the file
                      referenced in the contest.

        """
        files = set()
        for task in self.tasks:

            # Enumerate attachments
            for f in task.attachments.values():
                files.add(f.digest)

            # Enumerate managers
            for f in task.managers.values():
                files.add(f.digest)

            # Enumerate testcases
            for testcase in task.testcases:
                files.add(testcase.input)
                files.add(testcase.output)

        for submission in self.get_submissions():

            # Enumerate files
            for f in submission.files.values():
                files.add(f.digest)

            # Enumerate executables
            for f in submission.executables.values():
                files.add(f.digest)

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

    def tokens_available(self, username, task_name):
        """Return three pieces of data:

        [0] the number of available tokens for the user to play on the
            task (independently from the fact that (s)he can play it
            right now or not due to a min_interval wating for
            expiration);

        [1] the next time in which a token will be generated (or
            None);

        [2] the time when the min_interval will expire, or None

        In particular, let r the return value of this method. We can
        sketch the code in the following way.:

        if r[0] > 0 and r[2] is None:
            we can play a token
            if r[1] is not None:
                next one will be generated at r[1]
            else:
                no other tokens will be generated
        elif r[0] > 0:
            we must wait till r[2] to play the token
            if r[1] is not None:
                next one will be generated at r[1]
            else:
                no other tokens will be generated
        else:
            we don't have tokens right now
            if r[1] is not None:
                next one will be generated at r[1]
                if r[2] is not None:
                    but we must wait also till r[2] to play it
            else:
                no other tokens will be generated

        Note also that this method assumes that all played tokens were
        regularly played, and that there are no tokens played in the
        future. Also, if r[0] == 0 and r[1] == None, then r[2] should
        be ignored.

        username (string): the username of the user.
        task_name (string): the name of the task.
        return ((int, int, int)): see description above the latter two
                                  are timestamps, or None.

        """
        timestamp = int(time.time())

        user = self.get_user(username)
        task = self.get_user(task_name)
        res = []

        # In this function, no suffix means relative to the contest,
        # *_task means relative to the task. We are going to compute
        # with them in parallel.

        # We take the list of the tokens already played.
        tokens = user.get_tokens()
        tokens_task = [token for token in tokens
                       if tokens.submission.task.task_name == task_name]

        # If we already played the total number allowed, we don't have
        # anything left. token_total can be ignored after this.
        if self.token_total is not None and \
               len(tokens) >= self.token_total:
            return (0, None, None)
        if task.token_total is not None and \
               len(tokens_task) >= task.token_total:
            return (0, None, None)

        # Now that we already considered the number of tokens already
        # played, we can put a semaphore at the end of both lists.
        class FakeToken:
            timestamp = 2000000000
        tokens.append(FakeToken())
        tokens_task.append(FakeToken())

        # avail* is the current number of available tokens. We are
        # going to rebuild all the history to know how many of them we
        # have now.

        # We start with the initial number, capped to max. *_initial
        # can be ignored after this.
        avail = self.token_initial
        if self.token_max is not None:
            avail = min(avail, self.token_max)
        avail_task = task.token_initial
        if task.token_max is not None:
            avail_task = min(avail_task, task.token_max)

        # These are the first not-yet-considered generation times.
        next_gen_time = 2000000000
        if self.token_gen_time is not None and \
               self.token_gen_number is not None:
            next_gen_time = self.start + self.token_gen_time * 60
        next_gen_time_task = 2000000000
        if task.token_gen_time is not None and \
               task.token_gen_number is not None:
            next_gen_time = self.start + task.token_gen_time * 60

        # These are the index of the first non-yet-considered token.
        tokens_index = 0
        tokens_task_index = 0

        # These are the next expiring time for *_min_intervals. Note
        # that since we assume token were played by the rule, we need
        # not to think of these as critical times. At the end of the
        # simulation, we know that all min_intervals will be expired
        # at these times (and not a second before).
        expiration = 0
        expiration_task = 0

        # Simulating!
        while True:
            next_critical_time = min(
                next_gen_time,
                next_gen_time_task,
                tokens[tokens_index].timestamp,
                tokens_task[tokens_task_index].timestamp,
                timestamp)

            # Generations happen *exactly* at round second, hence
            # before any other event happening in that second.
            if next_critical_time == next_gen_time:
                # If it is contest generation time, we add the tokens,
                # capped at *_max; also we increment next_gen_time.
                avail += self.token_gen_number
                if self.token_max is not None:
                    avail = min(avail, self.token_max)
                if self.token_gen_time is not None:
                    next_gen_time += self.token_gen_time * 60

            if next_critical_time == next_gen_time_task:
                # Same for task.
                avail_task += task.token_gen_number
                if task.token_max is not None:
                    avail_task = min(avail_task, task.token_max)
                if task.token_gen_time is not None:
                    next_gen_time_task += task.token_gen_time * 60

            if next_critical_time == tokens[tokens_index].timestamp:
                # If the user played a token, we decrease the
                # available tokens, and set that all min_intervals
                # will expire at expiration. Also we pass to the next
                # token.
                avail -= 1
                if self.token_min_interval is not None:
                    expiration = next_critical_time + \
                                 self.token_min_interval
                tokens_index += 1

            if next_critical_time == tokens_task[tokens_task_index].timestamp:
                # Same for task.
                avail_task -= 1
                if task.token_min_interval is not None:
                    expiration_task = next_critical_time + \
                                      task.token_min_interval
                tokens_task_index += 1

            if next_critical_time == timestamp:
                # Yay, simulation concluded.
                break

        # Now, min(avail, avail_task) is exactly the tokens available.
        res.append(min(avail, avail_task))

        # For the next generation time things are a bit more
        # complex. No one is ever going to use together contest-wise
        # and task-wise tokens, notwithstanding we implement it
        # correctly.
        if avail < avail_task:
            # In this case, we just need a contest-wise token to be
            # generated.
            res.append(next_gen_time if next_gen_time != 2000000000
                       else None)
        elif avail_task < avail:
            # Specular case.
            res.append(next_gen_time_task if next_gen_time_task != 2000000000
                       else None)
        else:
            # We need both!
            next_gen_time_both = max(next_gen_time, next_gen_time_task)
            res.append(next_gen_time_both if next_gen_time_both != 2000000000
                       else None)

        # Finally, both min_intervals must expire.
        expiration_time_both = max(expiration, expiration_task)
        res.append(expiration_time_both
                   if expiration_time_both >= timestamp
                   else None)

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
                        nullable=False)
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
