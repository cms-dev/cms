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

"""Manage submissions to get scores and statistics.

This is the main module needed to manage the results of a competition.

It needs a data provider to load the configuration of the competition
(composed by the definitions of contests, tasks, teams and users) and
to receive notifications about submissions. Submissions can be created
and updated (for example when the user releases it or when the score is
adjusted during the contest). In the history, the updated information
about a submission will be shown only after the timestamp of the update
itself, to appropriately match what was visible in the live scoreboard.

Notifications doesn't need to be received in real time nor in the order
they happened, since this module will adjust the current scores and
update the history accordingly.

In case some retroactive changes need to be perfomed (for example after
a reevaluation of a task) the data provider can change that data and
have the competition module reload it all again, effectively changing
both the current scores and the history.

The module is composed by four classes that store the data, along with
a dictionary for each of them to easily retrive data by ID:
 * Contest: represents a contest, that is a set of tasks and a time
            period in which users have to solve them
 * Task: a task
 * Team: a team, that is a set of users
 * User: a user, that is a contestant, that scores points on the tasks

The Submission class is used to store the data about the submissions
the user do on the tasks. There's no global storage for them since
they're memorized on a per-user/per-task basis.

The Score class is where the actual computation happens. There's one
instance of it for each user for each task. It receives notifications
about submissions and it provides the current score, the current set
of submissions and the history of score changes.

The load_data and unload_data functions are used by the data provider
to control the data that this module has access to. They're only used
to provide configuration data - the submissions are provided using
scores[user][task].create_submission and update_submission.

The get_global_history and compute_rank_history functions are helpers
called to compute specific information requested by the clients.

"""

import heapq


class Contest:
    """A class representing a contest.

    It defines only a few attributes, and no methods:
     * id: a global (unique) identifier
     * name: a human-readable name (should be unique but it's not enforced)

    """
    def __init__(self, iden, data):
        """Initialize a new Contest instance.

        The id attribute will be set to the value of the iden argument,
        while all other attributes will be fetched from the data argument.

        """
        self.id = iden
        self.name = data['name']
        # begin (UTC time)
        # end idem TODO


class Task:
    """A class representing a task.

    It defines only a few attributes, and no methods:
     * id: a global (unique) identifier
     * name: a human-readable name (should be unique but it's not enforced)
     * contest: the id of the contest the task belongs to
     * score: the maximum achievable score for the task
     * data_headers: a list with the descriptions of the extra fields that
                     will be provided with each submission for the task

    """
    def __init__(self, iden, data):
        """Initialize a new Task instance.

        The id attribute will be set to the value of the iden argument,
        while all other attributes will be fetched from the data argument.

        """
        self.id = iden
        self.name = data['name']
        self.contest = contests[data['contest']]
        self.score = data['score']
        self.data_headers = data['data_headers']


class Team:
    """A class representing a team.

    It defines only a few attributes, and no methods:
     * id: a global (unique) identifier
     * name: a human-readable name (should be unique but it's not enforced)

    """
    def __init__(self, iden, data):
        """Initialize a new Team instance.

        The id attribute will be set to the value of the iden argument,
        while all other attributes will be fetched from the data argument.

        """
        self.id = iden
        self.name = data['name']


class User:
    """A class representing a user.

    It defines only a few attributes, and no methods:
     * id: a global (unique) identifier
     * f_name: the first name of the user
     * l_name: the last name of the user
     * team: the id of the team the user belongs to

    """
    def __init__(self, iden, data):
        """Initialize a new User instance.

        The id attribute will be set to the value of the iden argument,
        while all other attributes will be fetched from the data argument.

        """
        self.id = iden
        self.f_name = data['f_name']
        self.l_name = data['l_name']
        self.team = teams[data['team']]


class Submission:
    """A class representing a submission.

    It defines only a few attributes, and no methods:
     * id: a global (unique) identifier
     * user: the id of the user the submission belongs to
     * task: the id of the task the submission belongs to
     * time: the unix timestamp of the submission
     * score: the score of the submission
     * released: whether the submission has been released or not
     * data: a list of extra fields, matching the data_headers of the
             corresponding task in length as well as in meaning

    """
    def __init__(self, iden, data):
        """Initialize a new Submission instance.

        The id attribute will be set to the value of the iden argument,
        while all other attributes will be fetched from the data argument.

        """
        self.id = iden
        self.user = users[data['user']]
        self.task = tasks[data['task']]
        self.time = data['time']
        self.score = data['score']
        self.released = data['released']
        self.data = data['data']


class Score:
    """A class representing the score of a user for a task.

    It doesn't only represent the numeric value of the score but it also
    contains the information used to get that value (the submissions),
    the history of the changes, and some methods to update this value.

    """
    def __init__(self, user, task):
        """Initialize an empty Score object.

        The Score object thus created will refer to the user and the task
        given as arguments. It will contain no submissions and its history
        of score changes will be empty.

        """
        self.user = user
        self.task = task

        # List of notifications of created and updated submissions,
        # sorted by ascending timestamp
        self._events = list()
        # List of submission, one for each create-event, updated to the last
        # update-event, sorted by creation time.
        # Will be kept in sync with self._events
        # Read-only attribute (from the outside)
        self.submissions = list()
        # List of changes in the score, sorted by ascending timestamp.
        # Will be kept in sync with self._events
        # Read-only attribute (from the outside)
        self.history = list()

    def create_submission(self, subm):
        """Create a new submission for this user and this task.

        Insert the Submission object given as argument in the list of
        submissions for this user for this task.
        Use it to update the history of score changes for this user and
        notify the connected clients if the current score has changed too.
        The given Submission object has to have a different ID from all
        previous created submissions for this user and this task.

        """
        # Check if no other submission has the same ID (TODO: raise exception)
        assert len([x for x in self._events if x.id == subm.id]) == 0
        # To avoid duplicated code with update_submission,
        # the submission is handled by another method
        self._handle_submission(subm)

    def update_submission(self, subm):
        """Update a new submission for this user and this task.

        The behaviour is similar to create_submission() except that
        different restrictions apply to the given Submission object.
        It needs to have the same ID as an already created submission for
        this user and this task and its timestamp needs to be greater than
        the one of that submission.

        """
        # Check that another submission has the same ID (TODO: raise exception)
        assert len([x for x in self._events if x.id == subm.id]) != 0
        # Check that this update happens later than the creation
        assert len([x for x in self._events
                    if x.id == subm.id and x.time <= subm.time]) != 0
        # To avoid duplicated code with create_submission,
        # the submission is handled by another method
        self._handle_submission(subm)

    def _handle_submission(self, subm):
        """Do the actual handling of submissions.

        Temporarily revert all subsequent created and updated submissions
        and their related score changes in the history, append this event
        and see if it modifies the history of score changes.
        Then apply again all subsequent submissions, doing the same check
        for each of them.

        """
        # Keep the current score, to see if it changes
        current_score = self._retrieve_score()

        # Keep a list of the reverted submissions
        stack = list()
        while len(self._events) > 0 and self._events[-1].time > subm.time:
            stack.append(self._events.pop())
        # Push the new submission on the top of the stack
        stack.append(subm)
        # Remove all history entries that happened later than this submission
        while len(self.history) > 0 and self.history[-1][0] > subm.time:
            self.history.pop()

        # If the reverted some events compute again the list of submissions
        if len(stack) > 1:
            self.submissions = self._compute_submissions()
        # Keep track of the current score
        old_score = self._retrieve_score()

        # For each reverted submission (including the one we're adding)
        while len(stack) != 0:
            # Update the list of submissions and put it again in the event list
            self._update_submissions(stack[-1])
            self._events.append(stack[-1])
            # Compute the new current score
            new_score = self._compute_score()
            # If we have a score change, add it to the history
            if new_score != old_score:
                self.history.append((stack[-1].time, new_score))
                old_score = new_score
            stack.pop()

        # If the new score differs from the previous one notify the clients
        if current_score != self._retrieve_score():
            _issue_score_update(self.user, self.task, self._retrieve_score())

    def _compute_submissions(self):
        """Computes the list of submissions.

        Reset the list and process all the events one by one.

        """
        self.submissions = []
        for event in self._events:
            self._update_submissions(event)

    def _update_submissions(self, event):
        """Updates the list of submissions according to the given event.

        If no submission with the same ID exist, it's a create-event,
        otherwise it's an update-event. Act accordingly.

        """
        same_id = [i for i, x in enumerate(self.submissions)
                   if x.id == event.id]
        if len(same_id) == 0:
            # Create submission
            self.submissions.append(event)
        else:
            # Update submissions
            # TODO should keep the timestamp of the creation
            self.submissions[same_id[0]] = event

    def _compute_score(self):
        """Compute the score.

        The score is computed in IOI-style: it's the maximum of
         * the score of the released submissions (if any)
         * the score of the last submission (if any)
         * zero

        """
        return max([x.score for x in self.submissions if x.released] +
                   [x.score for x in self.submissions[-1:]] + [0])

    def _retrieve_score(self):
        """Retrieve an already computed score.

        Check the history of score changes to get the current score.

        """
        return max([x[1] for x in self.history[-1:]] + [0])


contests = dict()
tasks = dict()
teams = dict()
users = dict()

scores = dict()


def _issue_score_update(user, task, score):
    """Send a notification about a score change to the clients.

    Yet to be implemented.

    """
    pass


def load_data(contests_data, tasks_data, teams_data, users_data):
    """Load the data given as argument.

    Delete all data previously stored and initialize the module with the
    data given as argument. All of them are dicts where the key specifies
    the id of the corresponding value.

    No notification is sent to the clients, so their status will be
    inconsistent: they'll keep the data they have until they refresh.
    Use this function with caution.

    """
    global contests, tasks, teams, users, scores

    contests = dict()
    for iden in contests_data:
        contests[iden] = Contest(iden, contests_data[iden])

    tasks = dict()
    for iden in tasks_data:
        tasks[iden] = Task(iden, tasks_data[iden])

    teams = dict()
    for iden in teams_data:
        teams[iden] = Team(iden, teams_data[iden])

    users = dict()
    for iden in users_data:
        users[iden] = User(iden, users_data[iden])

    scores = dict()
    for user in users:
        scores[user] = dict()
        for task in tasks:
            scores[user][task] = Score(user, task)


def unload_data():
    """Unload all the stored data.

    No notification is sent to the clients, so their status will be
    inconsistent: they'll keep the data they have until they refresh.
    Use this function with caution.

    """
    global contests, tasks, teams, users, scores
    contests = dict()
    tasks = dict()
    teams = dict()
    users = dict()
    scores = dict()


def get_global_history():
    """Merge all individual histories into a global one.

    Take all per-user/per-task histories and merge them, providing a global
    history of all schore changes and return it using a generator.
    Returned data is in the form (user_id, task_id, score, time).

    """
    # Use a priority queue, containing only one entry per-user/per-task
    queue = list()
    for user in users:
        for task in tasks:
            score = scores[user][task]
            if score.history:
                heapq.heappush(queue, (score.history[0], score, 0))

    # When an entry is popped, push the next entry for that user/task (if any)
    while len(queue) != 0:
        change, score, index = heapq.heappop(queue)
        index += 1
        yield (score.user, score.task, change[1], change[0])
        if len(score.history) > index:
            heapq.heappush(queue, (score.history[index], score, index))


def compute_rank_history(user_id):
    """Compute the history of rank changes for the given user.

    Using the global history of score changes, return a generator yielding
    the rank changes of the given user during the competition. Returned
    data is in the form (rank, time, context), where context can be:
     * a task id, meaning the rank is relative only to scores for that task
     * a contest id, meaning the rank is relative to scores from the tasks
                     of that contest only
     * 'all', meaning the rank is relative to scores from all tasks

    """
    score = dict()
    above = dict()
    for ctx in contests.keys() + tasks.keys() + ['all']:
        score[ctx] = dict()
        above[ctx] = 0
        for user in users.keys():
            score[ctx][user] = 0

    for user, task, scr, time in get_global_history():
        if user == user_id:
            for ctx in ['all', tasks[task].contest.id, task]:
                score[ctx][user] += scr - score[task][user]

                new_above = 0
                for u in users.keys():
                    if score[ctx][u] > score[ctx][user]:
                        new_above += 1

                if new_above != above[ctx]:
                    yield (new_above + 1, time, ctx)
                    above[ctx] = new_above

        else:
            for ctx in ['all', tasks[task].contest.id, task]:
                new_score = score[ctx][user] + scr - score[task][user]

                if (score[ctx][user] > score[ctx][user_id]
                    and new_score <= score[ctx][user_id]):
                    above[ctx] -= 1
                    yield (above[ctx] + 1, time, ctx)
                elif (score[ctx][user] <= score[ctx][user_id]
                      and new_score > score[ctx][user_id]):
                    above[ctx] += 1
                    yield (above[ctx] + 1, time, ctx)

                score[ctx][user] = new_score
