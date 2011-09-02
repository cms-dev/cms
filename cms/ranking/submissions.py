#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
import json
import functools

class InvalidKey(Exception):
    """Exception raised in case of invalid key."""
    pass


class InvalidTime(Exception):
    """Exception raised in case of invalid time."""
    pass


class InvalidData(Exception):
    """Exception raised in case of invalid data."""
    pass


class Submission(object):
    """A submission.

    Represents the useful data of a submission, that is the creation time,
    the score, the token flag, the extra data but not the user nor the task.
    It also provides the data's history and methods to query and update it.

    """
    def __init__(self, time, data):
        """Initialize the submission.

        Create a submission with the given creation time and initial data.

        time (int): the unix timestamp of the creation time
        data (dict): the initial data, containing:
         - 'score' (float): the initial score
         - 'token' (bool): the initial token flag
         - 'extra' (list of str): the initial extra data

        """
        self.time = time
        self._score = [(time, data['score'])]
        self._token = [(time, data['token'])]
        self._extra = [(time, data['extra'])]

    def get_current_score(self):
        """Return the current score."""
        return self._score[-1][1]

    def get_score(self, time):
        """Return the score at the given time.

        time (int): the unix timestamp of the query
        return (float): the queried score

        Raise InvalidTime if time is less than the creation time.

        """
        if time < self.time:
            raise InvalidTime
        # suggestion: could use binary search
        for t, score in reversed(self._score):
            if t <= time:
                return score

    def set_score(self, time, score):
        """Set the score at the given time.

        time (int): the unix timestamp of the update
        score (float): the updated score

        Raise InvalidTime if time is less than the creation time.

        """
        if time < self.time:
            raise InvalidTime
        # suggestion: could use binary search
        idx = 0
        while idx < len(self._score) and self._score[idx][0] < time:
            idx += 1
        if idx is len(self._score) or self._score[idx][0] > time:
            self._score.insert(idx, (time, score))
        else:
            self._score[idx] = (time, score)

    def get_current_token(self):
        """Return the current token flag."""
        return self._token[-1][1]

    def get_token(self, time):
        """Return the token flag at the given time.

        time (int): the unix timestamp of the query
        return (bool): the queried token flag

        Raise InvalidTime if time is less than the creation time.

        """
        if time < self.time:
            raise InvalidTime
        # suggestion: could use binary search
        for t, token in reversed(self._token):
            if t <= time:
                return token

    def set_token(self, time, token):
        """Set the token flag at the given time.

        time (int): the unix timestamp of the update
        token (bool): the updated token flag

        Raise InvalidTime if time is less than the creation time.

        """
        if time < self.time:
            raise InvalidTime
        # suggestion: could use binary search
        idx = 0
        while idx < len(self._token) and self._token[idx][0] < time:
            idx += 1
        if idx is len(self._token) or self._token[idx][0] > time:
            self._token.insert(idx, (time, token))
        else:
            self._token[idx] = (time, token)

    def get_current_extra(self):
        """Return the current extra data."""
        return self._extra[-1][1]

    def get_extra(self, time):
        """Return the extra data at the given time.

        time (int): the unix timestamp of the query
        return (list of str): the queried extra data

        Raise InvalidTime if time is less than the creation time.

        """
        if time < self.time:
            raise InvalidTime
        # suggestion: could use binary search
        for t, extra in reversed(self._extra):
            if t <= time:
                return extra

    def set_extra(self, time, extra):
        """Set the extra data at the given time.

        time (int): the unix timestamp of the update
        extra (list of str): the updated extra data

        Raise InvalidTime if time is less than the creation time.

        """
        if time < self.time:
            raise InvalidTime
        # suggestion: could use binary search
        idx = 0
        while idx < len(self._extra) and self._extra[idx][0] < time:
            idx += 1
        if idx is len(self._extra) or self._extra[idx][0] > time:
            self._extra.insert(idx, (time, extra))
        else:
            self._extra[idx] = (time, extra)

    def dump(self):
        """Dump the submission."""
        return self.__dict__

    def load(self, data):
        """Load the submission."""
        # validate data
        try:
            assert type(data) is dict
            assert type(data['time']) is int
            assert data['time'] >= 0
            assert type(data['_score']) is list
            for idx, x in enumerate(data['_score']):
                assert type(x) is list
                assert len(x) == 2
                assert type(x[0]) is int
                assert type(x[1]) is float
                assert x[1] >= 0.0
                if idx == 0:
                    assert x[0] == data['time']
                else:
                    assert x[0] > data['_score'][idx-1][0]
            assert type(data['_token']) is list
            for idx, x in enumerate(data['_token']):
                assert type(x) is list
                assert len(x) == 2
                assert type(x[0]) is int
                assert type(x[1]) is bool
                if idx == 0:
                    assert x[0] == data['time']
                else:
                    assert x[0] > data['_token'][idx-1][0]
            assert type(data['_extra']) is list
            for idx, x in enumerate(data['_extra']):
                assert type(x) is list
                assert len(x) == 2
                assert type(x[0]) is int
                assert type(x[1]) is list
                if idx == 0:
                    assert x[0] == data['time']
                else:
                    assert x[0] > data['_score'][idx-1][0]
                for j in x[1]:
                    assert type(j) is unicode
        except (KeyError, AssertionError):
            raise InvalidData
        self.time = data['time']
        self._score = [(x[0], x[1]) for x in data['_score']]
        self._token = [(x[0], x[1]) for x in data['_token']]
        self._extra = [(x[0], x[1]) for x in data['_extra']]


class SubmissionList(object):
    """A list of submissions.

    Apart from storing submissions and providing methods to create, update,
    delete and retrieve them, this class computes the score and the history
    of score changes. All this information is automatically updated when
    submissions are modified.

    """
    def __init__(self, user, task):
        """Initialize the submission list.

        Create an empty submission list for the given user and task.

        user (str): the if of the user
        task (str): the id of the task

        """
        assert isinstance(user, unicode)
        assert isinstance(task, unicode)
        self.user = user
        self.task = task
        self._subs = dict()
        self._times = list()
        self._history = list()
        self._callbacks = list()

    def create(self, key, time, data):
        """Create a new submission.

        Create a new submission in this list, with the given key, creation
        time and initial data.

        key (str): the id of the submission
        time (int): the unix timestamp of the creation time
        data (dict): the initial data, containing:
         - 'score' (float): the initial score
         - 'token' (bool): the initial token flag
         - 'extra' (list of str): the initial extra data

        """
        self._subs[key] = Submission(time, data)
        self._update_history(time)

    def update(self, key, time, data):
        """Update a submission.

        Update a submission in this list, with the given key, update time
        and initial data.

        key (str): the id of the submission
        time (int): the unix timestamp of the update time
        data (dict): the initial data, containing (optionally):
         - 'score' (float): the updated score
         - 'token' (bool): the updated token flag
         - 'extra' (list of str): the updated extra data

        """
        if 'score' in data:
            self._subs[key].set_score(time, data['score'])
        if 'token' in data:
            self._subs[key].set_token(time, data['token'])
        if 'extra' in data:
            self._subs[key].set_extra(time, data['extra'])
        self._update_history(time)

    def delete(self, key):
        """Delete a submission.

        Delete the submission with the given key from the list.

        key (str): the id of the submission.

        """
        del self._subs[key]
        # reconstruct the other data
        times = list()
        for sub in self._subs.values():
            times.extend([x[0] for x in sub._score])
            times.extend([x[0] for x in sub._token])
            times.extend([x[0] for x in sub._extra])
        self._times = sorted(set(times))  # get a sorted unique list
        self._history = list()
        if len(self._times) > 0:
            self._update_history(self._times[0])

    def retrieve(self, key):
        """Retrieve a submission.

        Retireve the submission with the given key from the list.

        key (str): the id of the submission.

        """
        return self._subs[key]

    def get_score(self):
        """Return the current score of these submissions."""
        if len(self._history) > 0:
            return self._history[-1][1]
        else:
            return 0

    def _update_history(self, time):
        """Update the history of score changes from the given time onwards.

        time (int): the unix timestamp of the beginning of the update.

        """
        prev_score = self.get_score()

        if len(self._times) is not 0 and time < self._times[-1]:
            # the new time is inserted in the middle
            # remove the old score changes
            self._history = [x for x in self._history if x[0] < time]
            # find the first time >= the given time
            idx = 0
            while idx < len(self._times) and self._times[idx] < time:
                idx += 1
            # if the given time isn't present insert it
            if idx is len(self._times) or self._times[idx] is not time:
                self._times.insert(idx, time)
            # update all score changes from the given time onwards
            while idx < len(self._times):
                score = self._compute_score(self._times[idx])
                if score != self.get_score():
                    self._history.append((self._times[idx], score))
                idx += 1
        else:
            # the new time is inserted at the end
            # if the given time isn't present append it
            if len(self._times) is 0 or time > self._times[-1]:
                self._times.append(time)
            # update the score changes
            score = self._compute_current_score()
            if score != self.get_score():
                self._history.append((time, score))

        if prev_score != self.get_score():
            for f in self._callbacks:
                f(self.get_score())


    def _compute_current_score(self):
        """Compute the current score for these submissions."""
        max_released = 0
        last = (0, 0)

        for i in self._subs.values():
            score, released = i.get_current_score(), i.get_current_token()
            if (i.time, score) > last:
                last = (i.time, score)
            if released:
                max_released = max(max_released, score)

        return max(max_released, last[1])

    def _compute_score(self, time):
        """Compute the score at the given time for these submissions."""
        max_released = 0
        last = (0, 0)

        for i in self._subs.values():
            if i.time <= time:
                score, released = i.get_score(time), i.get_token(time)
                if (i.time, score) > last:
                    last = (i.time, score)
                if released:
                    max_released = max(max_released, score)

        return max(max_released, last[1])

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def dump(self, key):
        """Dump the submission matching the given key."""
        data = self._subs[key].dump()
        data['user'] = self.user
        data['task'] = self.task
        return data

    def load(self, key, data):
        """Load the submission with the given key."""
        s = Submission(0, {'score': 0.0, 'token': False, 'extra': []})
        s.load(data)
        self._subs[key] = s
        self._update_history(s.time)

class SubmissionStore(object):
    """A store for submissions.

    Store all submissions for all users for all tasks.
    Provide methods to create, update, delete and retrieve submissions,
    to receive notifications of score changes and to query about score
    change history.
    Provide validation of data and persistent storage on disk.

    """
    def __init__(self, path):
        """Init an empty submission store.

        path (str): the on-disk location of stored submissions.

        """
        self._path = path
        self._store = dict()
        self._scores = dict()
        self._callbacks = list()

        try:
            os.mkdir(path)
        except OSError:
            # it's ok: it means the directory already exists
            pass

        try:
            for name in os.listdir(path):
                if name[-5:] == '.json' and name[:-5] != '':
                    with open(path + name, 'r') as f:
                        key = name[:-5]
                        data = json.loads(f.read())
                        try:
                            assert type(data) is dict
                            assert type(data['user']) is unicode
                            assert type(data['task']) is unicode
                        except (KeyError, ValueError):
                            raise InvalidData
                        user, task = data['user'], data['task']
                        if not user in self._scores:
                            self._scores[user] = dict()
                        if not task in self._scores[user]:
                            self._scores[user][task] = SubmissionList(user, task)
                            self._scores[user][task].add_callback(
                                functools.partial(self.callback, user, task))
                        self._store[key] = (user, task)
                        self._scores[user][task].load(key, data)
        except OSError:
            # the directory doesn't exist or is inaccessible
            # TODO tell it to some human operator
            pass
        except IOError:
            # TODO tell it to some human operator
            pass
        except InvalidData:
            # someone edited the data incorrectly
            pass

    def callback(self, user, task, score):
        for f in self._callbacks:
            f(user, task, score)

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def create(self, key, data):
        """Create a new submission.

        Create a new submission with the given key and initial data.

        key (str): the id of the submission
        data (dict): the initial data, containing:
         - user (str): the id of the user
         - task (str): the id of the tash
         - time (int): the unix timestamp of creation time
         - score (float): the score
         - token (bool): the token flag
         - extra (list of str): the extra data

        """
        # validate key
        if not isinstance(key, unicode) or key in self._store:
            raise InvalidKey
        # validate data
        try:
            assert type(data) is dict
            assert type(data['user']) is unicode
            assert type(data['task']) is unicode
            assert type(data['time']) is int  # unix timestamp
            assert type(data['score']) is float
            assert type(data['token']) is bool
            assert type(data['extra']) is list
            for i in data['extra']:
                assert type(i) is unicode
            # additional validation
            assert data['time'] >= 0
            assert data['score'] >= 0.0
        except (KeyError, AssertionError):
            raise InvalidData
        # create entity
        user, task, time = data['user'], data['task'], data['time']
        if not user in self._scores:
            self._scores[user] = dict()
        if not task in self._scores[user]:
            self._scores[user][task] = SubmissionList(user, task)
            self._scores[user][task].add_callback(
                functools.partial(self.callback, user, task))
        self._store[key] = (user, task)
        self._scores[user][task].create(key, time, data)
        # save to disk
        try:
            with open(self._path + key + '.json', 'w') as f:
                f.write(json.dumps(self._scores[user][task].dump(key)))
        except IOError:
            # TODO tell it to some human operator
            pass


    def update(self, key, data):
        """Update a submission.

        Update a submission with the given data.

        key (str): the id of the submission
        data (dict): the data to update, containing:
         - time (int): the unix timestamp of update time
         - score (float): the score (optional)
         - token (bool): the token flag (optional)
         - extra (list of str): the extra data (optional)

        """
        # validate key
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey
        # validate data
        try:
            assert type(data) is dict
            assert type(data['time']) is int
            if 'user' in data:
                assert type(data['user']) is unicode
                assert data['user'] == self._store[key][0]
            if 'task' in data:
                assert type(data['task']) is unicode
                assert data['task'] == self._store[key][1]
            if 'score' in data:
                assert type(data['score']) is float
                assert data['score'] >= 0.0
            if 'released' in data:
                assert type(data['token']) is bool
            if 'data' in data:
                assert type(data['extra']) is list
                for i in data['extra']:
                    assert type(i) is unicode
            # additional validation
            assert data['time'] >= 0
        except (KeyError, AssertionError) as e:
            raise InvalidData, e
        # update entity
        (user, task), time = self._store[key], data['time']
        assert user in self._scores
        assert task in self._scores[user]
        self._scores[user][task].update(key, time, data)
        # save to disk
        try:
            with open(self._path + key + '.json', 'w') as f:
                f.write(json.dumps(self._scores[user][task].dump(key)))
        except IOError:
            # TODO tell it to some human operator
            pass

    def delete(self, key):
        """Delete a submission."""
        # validate key
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey
        # delete entity
        user, task = self._store[key]
        assert user in self._scores
        assert task in self._scores[user]
        self._scores[user][task].delete(key)
        # TODO delete _score[user][task] (and up) if empty
        # delete from disk
        try:
            os.remove(self._path + key + '.json')
        except OSError:
            # TODO tell it to some human operator
            pass

    def retrieve(self, key):
        """Retrieve a submission."""
        # validate key
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey
        # retrieve entity
        user, task = self._store[key]
        assert user in self._scores
        assert task in self._scores[user]
        return self._scores[user][task].retrieve(key)

submission_store = SubmissionStore("subs/")

