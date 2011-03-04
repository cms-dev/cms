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

import xmlrpclib
from StringIO import StringIO
from threading import Lock
import couchdb

import Configuration
import CouchObject
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib

FSL = FileStorageLib()
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

# Some exceptions that can be raised by these functions.

class FeedbackAlreadyRequested(Exception):
    pass

class TokenUnavailableException(Exception):
    pass

class ConnectionFailure(Exception):
    pass

class InvalidSubmission(Exception):
    pass

class StorageFailure(Exception):
    pass


def contest_phase(contest, timestamp):
    """
    Returns: -1 if the contest isn't started yet,
              0 if the contest is active
              1 if the contest has ended.
    """
    if contest.start != None and contest.start > timestamp :
        return -1
    if contest.stop == None or contest.stop > timestamp :
        return 0
    return 1

def available_tokens(contest, user, task, timestamp):
    """
    Returns the number of available tokens the given user can use
    for the given task.
    """
    tokens_timestamp = [s.token_timestamp
                        for s in user.tokens]
    task_tokens_timestamp = [s.token_timestamp
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
            return 0
        return available + 1
    return min(count_tokens(contest, tokens_timestamp), \
               count_tokens(task, task_tokens_timestamp))

def token_available(contest, user, task, timestamp):
    """
    Returns True if the given user can use a token for the given task.
    """
    tokens_timestamp = [s.token_timestamp
                        for s in user.tokens]
    task_tokens_timestamp = [s.token_timestamp
                             for s in user.tokens
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

    return ensure(contest, tokens_timestamp) and ensure(task, task_tokens_timestamp)


def update_submissions(contest):
    """
    Updates all the submissions in the given contest.

    Calls the refresh method for all the Submission objects in the
    given contest.
    """
    for s in contest.submissions:
        s.refresh()

def update_users(contest):
    """
    Updates all the users in the given contest.

    Calls the refresh method for all the User objects in the given
    contest.
    """
    for u in contest.users:
        u.refresh()

def refresh_array(array):
    for x in array:
        x.refresh()

def get_user_by_username(contest, username):
    for user in contest.users:
        if user.username == username:
            return user
    else:
        return None

def get_submission(contest, sub_id, owner = None):
    for s in contest.submissions:
        if s.couch_id == sub_id and (owner == None or s.user.username == owner) :
            return s
    else:
        return None

def get_submissions_by_username(contest, owner, taskname = None):
    return [s for s in contest.submissions \
            if s.user.username == owner and \
            ( taskname == None or s.task.name == taskname)]

def get_file_from_submission(submission, filename):
    if( submission == None or filename == None ):
        return None
    for key, value in submission.files.items():
        if key == filename:
            submission_file = StringIO()
            try:
                FSL.get_file(value, submission_file)
            except Exception as e:
                Utils.log("FileStorageLib raised an exception: "+repr(e),\
                            Utils.Logger.SEVERITY_DEBUG)
                return None
            file_content = submission_file.getvalue()
            submission_file.close()
            return file_content
    return None

def get_task_statement(task):
    statement_file = StringIO()
    try:
        if( not FSL.get_file(task.statement, statement_file) ):
            Utils.log("FileStorageLib get_file returned False",Utils.Logger.SEVERITY_DEBUG)
            return None
    except Exception as e:
        Utils.log("FileStorageLib raised an exception: "+repr(e),Utils.Logger.SEVERITY_DEBUG)
        return None
    statement = statement_file.getvalue()
    statement_file.close()
    return statement


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

    def _refresh_objects(contest):
        """
        Refreshes the objects that are necessary to the function.
        """
        try:
            contest.refresh()
            update_submissions(contest)
            update_users(contest)
        except AttributeError:
            raise ConnectionFailure()

    # If the user already used a token on this
    # FIXME - Concurrency problems: the user could use
    # more tokens than those available when there is
    # more than one interface server.

    with writelock:

        # The objects should be up-to-date when
        # the lock is acquired to avoid conflicts
        # with other internal requests.
        _refresh_objects(contest)

        if submission.tokened():
            raise FeedbackAlreadyRequested()

        else:

            # Inconsistency flag
            inconsistent = False

            for tentatives in xrange(Configuration.maximum_conflict_attempts):
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
                        submission.token_timestamp = timestamp
                        submission.to_couch()
                        inconsistent = False
                    break

                except couchdb.ResourceConflict:
                    # A conflict has happened: refresh the objects,
                    # check their status and try again.
                    Utils.log("enable_detailed_feedback: ResourceConflict for "\
                              +submission.couch_id, Utils.Logger.SEVERITY_DEBUG)
                    try:
                        _refresh_objects(contest)
                    except (couchdb.ResourceNotFound, ConnectionFailure) as e:
                        if inconsistent:
                            # TODO - Attempt a last triage by reverting
                            # user.tokens
                            log_message = "enable_detailed_feedback: inconsistency "\
                               +"due to unrecoverable resources for "+submission.couch_id
                            Utils.log(log_message,Utils.Logger.SEVERITY_CRITICAL)
                            raise e

            else:
                log_message = "enable_detailed_feedback: Maximum number of attempts "\
                              +"reached for "+submission.couch_id
                if inconsistent:
                    # TODO - Attempt a last triage by reverting
                    # user.tokens
                    log_message += " and it was left in an inconsistent state!"
                Utils.log(log_message,Utils.Logger.SEVERITY_CRITICAL)
                raise couchdb.ResourceConflict()

            # Warn the Evaluation Server
            try:
                ES.use_token(submission.couch_id)
            except:
                # FIXME - quali informazioni devono essere fornite?
                Utils.log("Failed to warn the Evaluation Server about a detailed"\
                          "feedback request for "+submission.couch_id+".",
                          Utils.Logger.SEVERITY_IMPORTANT)
                return False
            return True




def submit(contest, task, user, files, timestamp):
    """
    Attempts to submit a solution.

    This function attempts to store the given files in the FS and to
    store the submission in the database.
    Returns True if the submission is stored in the DB
    AND the EvaluationServer has been warned about its state change;
    Returns False if the sumbission is stored in the DB
    but the EvaluationServer has not been warned.
    Any exception indicates that the submission hasn't been stored,
    possibly with inconsistencies.
    """

    def _refresh_objects(contest):
        """
        Refreshes the objects that are necessary to the function.
        """
        try:
            contest.refresh()
            update_submissions(contest)
            update_users(contest)
        except AttributeError:
            raise ConnectionFailure()


    if not task.valid_submission(files.keys()):
        raise InvalidSubmission()

    # Attempt to store the submission locally to be able to recover
    # a failure.
    # TODO: Determine when the submission is to be considered accepted
    # and pre-emptively stored.
    if Configuration.submit_local_copy:
        import pickle
        try:
            path = os.path.join(Configuration.submit_local_copy_path, user.username)
            if not os.path.exists(path):
                os.mkdir(path)
            with open(os.path.join(path,str(int(timestamp)) ), "w") as fd:
                pickle.dump((contest.couch_id, user.couch_id, task, files), fd)
        except Exception as e:
            Utils.log("submit: local copy failed - "+repr(e),\
                         Utils.Logger.SEVERITY_IMPORTANT)

    # Check if we can connect to the DB before sending files to the FS.
    _refresh_objects(contest)


    # TODO: Check the timestamp here?

    for filename, content in files.items():
        temp_file, temp_filename = tempfile.mkstemp()
        with os.fdopen(temp_file, "w") as temp_file:
            temp_file.write(content)
        try:
            files[filename] = FSL.put(temp_filename)
        except Exception as e:
            raise StorageFailure(e)

    with writelock:

        # The objects should be up-to-date when
        # the lock is acquired to avoid conflicts
        # with other requests.
        _refresh_objects(contest)

        # Save the submission.
        # A new document shouldn't have resource conflicts...
        for tentatives in xrange(Configuration.maximum_conflict_attempts):
            try:
                s = Submission(user, task, timestamp, files)
                break
            except couchdb.ResourceConflict as e:
                Utils.log("submit: ResourceConflict for "\
                          +" a submission by "+user.username, Utils.Logger.SEVERITY_DEBUG)
                try:
                    _refresh_objects(contest)
                except ConnectionFailure as e:
                    Utils.log("submit: Refresh failed while attempting to recover"\
                              +"a conflict.", Utils.Logger.SEVERITY_CRITICAL)
                    raise e
        else:
            Utils.log("submit: Maximum number of attempts reached to add submission"\
                      +submission.couch_id+" by "+user.username,\
                            Utils.Logger.SEVERITY_CRITICAL)
            raise couchdb.ResourceConflict()

        # Append the submission to the contest.
        for tentatives in xrange(Configuration.maximum_conflict_attempts):
            contest.submissions.append(s)
            try:
                contest.to_couch()
                break
            except couchdb.ResourceConflict as e:
                Utils.log("submit: ResourceConflict for "\
                              +s.couch_id, Utils.Logger.SEVERITY_DEBUG)
                try:
                    _refresh_objects(contest)
                except ConnectionFailure as e:
                    Utils.log("submit: Refresh failed while attempting to recover"\
                              +"a conflict.", Utils.Logger.SEVERITY_CRITICAL)
                    raise e
        else:
            Utils.log("submit: Maximum number of attempts reached to append to contest. "\
                       +submission.couch_id+" by "+user.username,\
                            Utils.Logger.SEVERITY_CRITICAL)
            raise couchdb.ResourceConflict()

    # The submission should be successful:
    # Warn the Evaluation Server.
    warned = False
    try:
        ES.add_job(s.couch_id)
        warned = True
    except Exception as e:
        Utils.log("Failed to queue the submission to the Evaluation Server: " \
                  + s.couch_id + ", exception: " + repr(e), \
                  Utils.Logger.SEVERITY_IMPORTANT)
    return (s, warned)

def reevaluate_submission(submission):
    submission.invalid()
    ES.add_job(submission.couch_id)

def get_workers_status():
    return ES.get_workers_status()

def add_announcement(contest, subject, text):
    announcement = {
        "date": time.time(),
        "subject": subject,
        "text": text
        }
    contest.announcements.append(announcement)
    contest.to_couch()

def remove_announcement(contest, index):
    del contest.announcements[index]
    contest.to_couch()
