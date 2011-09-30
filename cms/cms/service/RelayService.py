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

"""Relay service. Its jobs is to communicate events to the Ranking
module, via http requests.

"""

import httplib
import simplejson
import base64

from cms.db.SQLAlchemyAll import Session, Submission, Contest
from cms.db.Utils import ask_for_contest

from cms.async.AsyncLibrary import Service, rpc_method, logger
from cms.async import ServiceCoord
from cms import Config


def get_authorization(username, password):
    """Compute the basic authentication string needed to send data to
    the ranking.

    username (string): username to login with.
    password (string): password of the username.
    return (string): the basic auth header, or ValueError if username
                     contains ":"

    """
    if ":" in username:
        raise ValueError
    return "Basic %s" % base64.b64encode(username + ':' + password)


def post_data(connection, url, data, auth, method="POST"):
    """Send some data to url through the connection using username and
    password specified in auth.

    connection (httplib.HTTPConnection): the connection.
    url (string): the relative url.
    auth (string): the authorization as returned by get_authorization.
    data (dict): the data to json-encode and send.

    """
    connection.request(method,
                       url,
                       simplejson.dumps(data),
                       {'Authorization': auth})
    r = connection.getresponse()
    r.read()


def put_data(connection, url, data, auth):
    post_data(connection, url, data, auth, "PUT")


class RelayService(Service):
    """Relay service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("RelayService", shard))
        Service.__init__(self, shard)

        self.session = Session()

    @rpc_method
    def initialize(self, contest_id):
        """Send to the ranking all the data that are supposed to be
        sent before the contest: contest, users, tasks. No support for
        teams, flags and faces.

        contest_id (int): the contest to send.
        return (bool): True

        """
        connection = httplib.HTTPConnection(Config.ranking_address)
        auth = get_authorization(Config.ranking_username,
                                 Config.ranking_password)

        # Send contest
        contest = Contest.get_from_id(contest_id, self.session)
        if contest is None:
            logger.error("Received request for unexistent contest id %s." %
                         contest_id)
            raise KeyError
        post_data(connection,
                  '/contests/%s' % contest.name,
                  {"name": contest.description,
                   "begin": contest.start,
                   "end": contest.stop},
                  auth)

        for user in contest.users:
            post_data(connection,
                      "/users/%s" % user.username,
                      {"f_name": user.real_name.split()[0],
                       "l_name": " ".join(user.real_name.split()[1:]),
                       "team": "None"},
                      auth)

    @rpc_method
    def submission_new_score(self, submission_id, timestamp=None,
                             score=0.0, extra=[]):
        """This RPC inform RelayService that ES has a new score for
        the submission. We have roughly three possible ways that ES
        calls this:

        1. the user submits and ES evaluate the submission; timestamp
           is the time of the submission;

        2. another user submits a better solution in a task where the
           score depends on the other solutions; timestamp is the time
           of the submission of the other user;

        3. for some reason, ES re-evaluate the submission, or another
           one as in (2); in this case the timestamp is the original
           one, as in (1) or (2), not the time of the re-evaluation.

        submission_id (int): the id of the submission that changed.
        timestamp (int): the time where the changes has been done.
        score (float): the new score of the submission.
        extra (list): the extra data (i.e., partial scores).
        returns (bool): True

        """
        logger.info("Posting new score %s for submission %s." %
                    (score, submission_id))
        connection = httplib.HTTPConnection(Config.ranking_address)
        auth = get_authorization(Config.ranking_username,
                                 Config.ranking_password)
        submission = Submission.get_from_id(submission_id, self.session)
        if submission is None:
            logger.error("Received request for unexistent submission id %s." %
                         submission_id)
            raise KeyError
        if submission.user.hidden:
            return
        if timestamp is None:
            timestamp = submission.timestamp

        # We are not sure that the submission has already been sent,
        # so we post it anyway.
        post_data(connection,
                  "/subs/%s" % submission_id,
                  {"user": submission.user.username,
                   "task": submission.task.name,
                   "time": timestamp,
                   "score": score,
                   "token": submission.token is not None,
                   "extra": extra
                   },
                  auth)

        # And then we do a put to update the result.
        put_data(connection,
                 "/subs/%s" % submission_id,
                 {"time": timestamp,
                  "score": score,
                  "extra": extra},
                 auth)


    @rpc_method
    def submission_tokened(self, submission_id, timestamp):
        """This RPC inform RelayService that the user has played the
        token on a submission.

        submission_id (int): the id of the submission that changed.
        timestamp (int): the time of the token.
        returns (bool): True

        """
        logger.info("Posting token usage for submission %s." % submission_id)
        connection = httplib.HTTPConnection(Config.ranking_address)
        auth = get_authorization(Config.ranking_username,
                                 Config.ranking_password)
        submission = Submission.get_from_id(submission_id, self.session)
        if submission is None:
            logger.error("Received request for unexistent submission id %s." %
                         submission_id)
            raise KeyError

        # We are not sure that the submission has already been sent,
        # so we post it anyway.
        post_data(connection,
                  "/subs/%s" % submission_id,
                  {"user": submission.user.username,
                   "task": submission.task.name,
                   "time": timestamp,
                   "score": 0.0,
                   "token": submission.token is not None,
                   "extra": []},
                  auth)

        # And then we do a put to update the result.
        put_data(connection,
                 "/subs/%s" % submission_id,
                 {"time": timestamp,
                  "token": True},
                 auth)


def main():
    import sys
    if len(sys.argv) < 2:
        print sys.argv[0], "shard [contest]"
    else:
        RelayService(int(sys.argv[1])).run()


if __name__ == "__main__":
    main()
