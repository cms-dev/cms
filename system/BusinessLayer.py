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

from StringIO import StringIO
from FileStorageLib import FileStorageLib

from threading import Lock
import couchdb
import os
import tempfile
import xmlrpclib

import Configuration
import CouchObject
import Utils
from Submission import Submission

FSL = FileStorageLib()
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

class FeedbackAlreadyRequestedException(Exception):
    pass


class TokenUnavailableException(Exception):
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
                Utils.log("FileStorageLib raised an exception: "+repr(e),Utils.Logger.SEVERITY_DEBUG)
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


#This lock attempts to avoid resource conflicts inside the module.
writelock = Lock()

def enable_detailed_feedback(contest, submission, timestamp):

    # If the user already used a token on this
    # FIXME - Concurrency problems: the user could use
    # more tokens than those available, exploting the fact
    # that the update on the database is performed some
    # time after the availablility check.
    # This requires to make the whole operation isolated.
    # Who should be responsible about the correct use of tokens?
    # If more interfaces alter the token of the same user, they
    # should coordinate in order to avoid issues.

    with writelock:

        user = submission.user
        if submission.tokened():
            raise FeedbackAlreadyRequestedException()
        # Are there any tokens available?
        elif not token_available(contest, user, submission.task, timestamp):
            raise TokenUnavailableException()
        else: 

            # Save to CouchDB
            # FIXME - Should catch ResourceConflict exception:
            # update the documents, do some sanity checks,
            # modify them again and try again to store them on
            # CouchDB
            for tentatives in xrange(3):
                try:
                    # Finding the submission tokened again might happen when
                    # there are conflicts; In this case we only have to ensure
                    # that the user is updated.
                    
                    if not submission.tokened():
                        submission.token_timestamp = timestamp
                        submission.to_couch()
                    
                    if submission not in user.tokens:
                        user.tokens.append(submission)
                        user.to_couch()
                    break
                except couchdb.ResourceConflictException:
                    # A conflict has happened: refresh the objects,
                    # check their status and try again. 
                    Utils.log("enable_detailed_feedback: ResourceConflict for "+submission.couch_id,\
                                Utils.Logger.SEVERITY_DEBUG)
                    contest.refresh()
                    update_submissions(contest)
                    update_users(contest)
                    # Instead of simply refreshing, get it again to 
                    # check if the submission is still in the DB
                    
                    # If this fails, either the submission doesn't exist anymore, or the owner has changed.
                    submission = get_submission(contest,submission.submission_id,user.username)
                    if submission == None:
                        raise couchdb.ResourceNotFound()

            else:
                Utils.log("enable_detailed_feedback: Maximum number of retries reached for "+submission.couch_id,\
                            Utils.Logger.SEVERITY_CRITICAL)
                raise couchdb.ResourceConflict()
            # We have to warn Evaluation Server
            try:
                ES.use_token(submission.couch_id)
            except:
                # FIXME - quali informazioni devono essere fornite?
                Utils.log("Failed to warn the Evaluation Server about a detailed feedback request.",
                          Utils.Logger.SEVERITY_IMPORTANT)
            return


class StorageFailure(Exception):
    pass
    


def submit(contest, task, user, files, timestamp):
    
    for filename, content in files.items():
        temp_file, temp_filename = tempfile.mkstemp()
        with os.fdopen(temp_file, "w") as temp_file:
            temp_file.write(content)
        try:
            files[filename] = FSL.put(temp_filename)
        except Exception as e:
            raise StorageFailure(e)

    with writelock:

        # A new document shouldn't have resource conflicts...
        for tentatives in xrange(3):
            try:
                s = Submission(user, task, timestamp, files)
                break
            except couchdb.ResourceConflict as e:
                contest.refresh()
                update_users(contest)
                update_submissions(contest)
                # What else should this do?
        else:
            Utils.log("submit: Failed to add the submission to couchdb. "+submission.couch_id+" by "+user.username,\
                            Utils.Logger.SEVERITY_CRITICAL)
            raise couchdb.ResourceConflict()

        # FIXME - Should catch ResourceConflict exception: update the
        # document, do some sanity checks, modify it again and try
        # again to store it on CouchDB
        for tentatives in xrange(3):
            contest.submissions.append(s)
            try:
                contest.to_couch()
                break
            except couchdb.ResourceConflict as e:
                contest.refresh()
                update_users(contest)
                update_submissions(contest)
                # What else should this do?      
        else:
            Utils.log("submit: Failed to append to contest. "+submission.couch_id+" by "+user.username,\
                            Utils.Logger.SEVERITY_CRITICAL)
            raise couchdb.ResourceConflict()

    try:
        ES.add_job(s.couch_id)
    except Exception as e:
        Utils.log("Failed to queue the submission to the Evaluation Server: "+s.couch_id+", exception: "+repr(e),\
                  Utils.Logger.SEVERITY_IMPORTANT)
    return s

