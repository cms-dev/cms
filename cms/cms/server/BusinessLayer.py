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

import os
import tempfile
import time
import codecs

import xmlrpclib
from StringIO import StringIO
from threading import Lock

from cms import Config
import cms.util.Utils as Utils
from cms.db.SQLAlchemyAll import Contest, Submission

from cms.async.AsyncLibrary import Service, rpc_method, rpc_binary_response, logger
#from Utils import ServiceCoord

# Some exceptions that can be raised by these functions.

class FeedbackAlreadyRequested(Exception):
    pass

class TokenUnavailableException(Exception):
    pass

class ConnectionFailure(Exception):
    pass

class InvalidSubmission(Exception):
    pass

class RepeatedSubmission(Exception):
    pass

class StorageFailure(Exception):
    pass


def contest_phase(contest, timestamp):
    """
    Returns: -1 if the contest isn't started yet,
              0 if the contest is active
              1 if the contest has ended.
    """
    if contest.start is not None and contest.start > timestamp:
        return -1
    if contest.stop is None or contest.stop > timestamp:
        return 0
    return 1

def available_tokens(contest, user, task, timestamp):
    """
    Returns the number of available tokens the given user can use
    for the given task.
    """
    tokens_timestamp = [s.token.timestamp
                        for s in user.tokens]
    task_tokens_timestamp = [s.token.timestamp
                             for s in user.tokens
                             if s.task == task]
    # These should not be needed, but let's be safe
    tokens_timestamp.sort()
    task_tokens_timestamp.sort()

    def count_tokens(object_with_tokens_specs, timestamps):
        o = object_with_tokens_specs

        # Ensure availability
        available = o.token_initial
        # Time left from the last iteration
        leftover_time = 0
        last_t = contest.start
        for t in timestamps + [timestamp]:
            interval = t - last_t
            interval += leftover_time
            int_interval = int(interval)
            gen_tokens = int_interval / (60 * o.token_gen_time)
            if available + gen_tokens >= o.token_max:
                leftover_time = 0
                available = o.token_max - 1
            else:
                leftover_time = interval % (60 * o.token_gen_time)
                available = available + gen_tokens - 1
            last_t = t
        if available < 0:
            return 0
        return available + 1
    return min(count_tokens(contest, tokens_timestamp), \
               count_tokens(task, task_tokens_timestamp))

def token_available(contest, user, task, timestamp):
    """
    Returns True if the given user can use a token for the given task.
    """
    tokens_timestamp = [s.token.timestamp
                        for s in user.get_tokens()]
    task_tokens_timestamp = [s.token.timestamp
                             for s in user.get_tokens()
                             if s.task == task]

    # A token without timestamp means that there is another process that is
    # attempting to enable the token for the respective submission: if
    # this happens, forbid the usage of tokens.
    if None in tokens_timestamp:
        return False

    # These should not be needed, but let's be safe
    tokens_timestamp.sort()
    task_tokens_timestamp.sort()

    def ensure(object_with_tokens_specs, timestamps):
        o = object_with_tokens_specs
        # Ensure min_interval
        if timestamps != [] and \
                timestamp - timestamps[-1] < 60 * o.token_min_interval:
            return False
        # Ensure total
        if len(timestamps) >= o.token_total:
            return False

        # Ensure availability
        available = o.token_initial
        # Time left from the last iteration
        leftover_time = 0
        # FIXME: Generation starts from the Epoch?
        last_t = 0
        for t in timestamps + [timestamp]:
            interval = t - last_t
            interval += leftover_time
            int_interval = int(interval)
            gen_tokens = int_interval / (60 * o.token_gen_time)
            if available + gen_tokens >= o.token_max:
                leftover_time = 0
                available = o.token_max - 1
            else:
                leftover_time = interval % (60 * o.token_gen_time)
                available = available + gen_tokens - 1
            last_t = t
        if available < 0:
            return False
        return True

    return ensure(contest, tokens_timestamp)\
        and ensure(task, task_tokens_timestamp)


# This lock attempts to avoid resource conflicts inside the module.
# ALWAYS acquire this when you attempt to modify an object.
# Acquire this also if you think the objects shouldn't change
# while reading them.
writelock = Lock()


def enable_detailed_feedback(contest, submission, timestamp, user):
    """
    Attempts to enable the given submission for detailed feedback.

    If the given user has available tokens and the submission is not
    yet marked for detailed feedback, this function attempts to mark
    that submisssion for detailed feedback.
    Returns True if the submission has been marked for detailed feedback
    AND the EvaluationServer has been warned about its state change;
    Returns False if the sumbission has been marked for detailed feedback
    but the EvaluationServer has not been warned.
    Any exception indicates that the submission hasn't been marked
    for detailed feedback, possibly with inconsistencies.
    """

    # If the user already used a token on this
    # FIXME - Concurrency problems: the user could use
    # more tokens than those available when there is
    # more than one interface server.

    with writelock:

        if submission.tokened():
            raise FeedbackAlreadyRequested()

        else:

            # Inconsistency flag
            inconsistent = False

            for tentatives in xrange(Config.maximum_conflict_attempts):
                try:
                    # Update the user's tokenized submissions.
                    # Skip this step if the submission is already in the list.
                    if submission not in user.tokens:
                        if not token_available(contest, user, submission.task,\
                                                timestamp):
                            raise TokenUnavailableException()
                        user.tokens.append(submission)
                        user.to_couch()
                        inconsistent = True
                    # Update the token timestamp if this is not already marked
                    # by someone else when we attempt again.
                    if not submission.tokened():
                        submission.token.timestamp = timestamp
                        submission.to_couch()
                        inconsistent = False
                    break

                except couchdb.ResourceConflict:
                    # A conflict has happened: refresh the objects,
                    # check their status and try again.
                    Utils.log("enable_detailed_feedback: ResourceConflict for %s."
                              % submission.couch_id, Utils.Logger.SEVERITY_DEBUG)

            else:
                log_message = "enable_detailed_feedback: Maximum number of attempts "\
                              + "reached for " + submission.couch_id
                if inconsistent:
                    # TODO - Attempt a last triage by reverting
                    # user.tokens
                    log_message += " and it was left in an inconsistent state!"
                Utils.log(log_message, Utils.Logger.SEVERITY_CRITICAL)
                raise couchdb.ResourceConflict()

            # Warn the Evaluation Server
            try:
                ES.use_token(submission.couch_id)
            except:
                # FIXME - quali informazioni devono essere fornite?
                Utils.log("Failed to warn the Evaluation Server about a detailed"\
                          "feedback request for " + submission.couch_id + ".",
                          Utils.Logger.SEVERITY_IMPORTANT)
                return False
            return True
