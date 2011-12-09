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

"""Scoring service. Its jobs is to handle everything is bout assigning
scores and communicating them to the world.

In particular, it takes care of handling the internal way of keeping
the score (i.e., the ranking view) and send to the external ranking
services the scores, via http requests.

"""

import httplib
import simplejson
import base64
import errno

from cms.db.SQLAlchemyAll import SessionGen, Submission, Contest
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
    return (int): status of the http request.

    """
    connection.request(method,
                       url,
                       simplejson.dumps(data),
                       {'Authorization': auth})
    r = connection.getresponse()
    r.read()
    return r.status


def put_data(connection, url, data, auth):
    """See post_data.

    """
    return post_data(connection, url, data, auth, "PUT")


def safe_post_data(connection, url, data, auth, operation):
    """Call post_data issuing a warning if we get a status different
    from 200 or 201. See post_data for parameters.

    """
    status = post_data(connection, url, data, auth)
    if status not in [200, 201]:
        logger.info("Status %s while %s to ranking." %
                    (status, operation))


def safe_put_data(connection, url, data, auth, operation):
    """Call put_data issuing a warning if we get a status different
    from 200 or 201. See post_data for parameters.

    """
    status = put_data(connection, url, data, auth)
    if status not in [200, 201]:
        logger.info("Status %s while %s to ranking." %
                    (status, operation))


class ScoringService(Service):
    """Scoring service.

    """

    # How often we try to send data to remote rankings.
    CHECK_DISPATCH_TIME = 5.0

    def __init__(self, shard, contest_id):
        logger.initialize(ServiceCoord("ScoringService", shard))
        Service.__init__(self, shard)

        self.contest_id = contest_id

        self.scorers = {}
        with SessionGen(commit=False) as session:
            contest = session.query(Contest).\
                      filter_by(id=contest_id).first()
            logger.info("Loaded contest %s" % contest.name)
            self.submission_ids_to_score = \
                [x.id for x in contest.get_submissions() if x.evaluated()]
            contest.create_empty_ranking_view(timestamp=contest.start)
            for task in contest.tasks:
                self.scorers[task.id] = task.get_scorer()
            session.commit()

        self.rankings = []
        for i in xrange(len(Config.rankings_address)):
            address = Config.rankings_address[i]
            username = Config.rankings_username[i]
            password = Config.rankings_password[i]
            auth = get_authorization(username, password)
            self.rankings.append(("%s:%d" % tuple(address), auth))
        self.operation_queue = []

        for ranking in self.rankings:
            self.operation_queue.append((self.initialize, [ranking]))

        self.add_timeout(self.dispatch_operations, None,
                         ScoringService.CHECK_DISPATCH_TIME, immediately=True)

        self.add_timeout(self.score_old_submissions, None,
                         0.01, immediately=True)

    def score_old_submissions(self):
        """The submissions in the submission_ids_to_score list are
        evaluated submissions that we can assign a score to, and this
        method scores one of these at a time. This method keeps
        getting called while the list is non-empty.

        Note: doing this way (instead of putting everything in the
        __init__ (prevent freezing the service at the beginning in
        case of many old submissions.

        """
        if len(self.submission_ids_to_score) == 0:
            logger.info("Finished loading old submissions.")
            return False
        else:
            self.new_evaluation(self.submission_ids_to_score[0])
            self.submission_ids_to_score = self.submission_ids_to_score[1:]
            return True

    def dispatch_operations(self):
        """Look at the operations still to do in the queue and tries
        to dispatch them

        """
        pending = len(self.operation_queue)
        if pending > 0:
            logger.info("%s operations still pending." % pending)

        failed_rankings = set([])
        new_queue = []
        for method, args in self.operation_queue:
            if args[0] in failed_rankings:
                new_queue.append((method, args))
                continue
            try:
                method(*args)
            except Exception as err:
                # Connection aborted / refused / reset by peer
                if err.errno not in [errno.ECONNABORTED,
                                     errno.ECONNREFUSED,
                                     errno.ECONNRESET]:
                    raise err
                logger.info("Ranking %s not connected." % args[0][0])
                new_queue.append((method, args))
                failed_rankings.add(args[0])
        self.operation_queue = new_queue

        # We want this to run forever.
        return True

    def initialize(self, ranking):
        """Send to the ranking all the data that are supposed to be
        sent before the contest: contest, users, tasks. No support for
        teams, flags and faces.

        ranking ((string, string)): address and authorization string
                                    of ranking server.
        return (bool): success of operation

        """
        logger.info("Initializing rankings.")
        connection = httplib.HTTPConnection(ranking[0])
        auth = ranking[1]

        with SessionGen(commit=False) as session:
            contest = Contest.get_from_id(self.contest_id, session)
            if contest is None:
                logger.error("Received request for unexistent contest id %s." %
                             self.contest_id)
                raise KeyError
            contest_name = contest.name
            contest_url = "/contests/%s" % contest_name
            contest_data = {"name": contest.description,
                            "begin": contest.start,
                            "end": contest.stop}

            users = [["/users/%s" % user.username,
                      {"f_name": user.real_name.split()[0],
                       "l_name": " ".join(user.real_name.split()[1:]),
                       "team": None}]
                     for user in contest.users
                     if not user.hidden]

            tasks = [["/tasks/%s" % task.name,
                      {"name": task.title,
                       "contest": contest.name,
                       "score": 100.0,
                       "extra_headers": [],
                       "order": task.num,
                       "short_name": task.name}]
                     for task in contest.tasks]

        safe_put_data(connection, contest_url, contest_data, auth,
                      "sending contest %s" % contest_name)

        for user in users:
            safe_put_data(connection, user[0], user[1], auth,
                          "sending user %s" % (user[1]["l_name"] + " " +
                                                user[1]["f_name"]))

        for task in tasks:
            safe_put_data(connection, task[0], task[1], auth,
                          "sending task %s" % task[1]["name"])

        return True

    @rpc_method
    def new_evaluation(self, submission_id):
        """This RPC inform ScoringService that ES finished the
        evaluation for a submission.

        submission_id (int): the id of the submission that changed.

        """
        with SessionGen(commit=True) as session:
            submission = Submission.get_from_id(submission_id, session)
            if submission is None:
                logger.critical("[action_finished] Couldn't find "
                                " submission %d in the database" %
                                submission_id)
                return

            # Assign score to the submission
            scorer = self.scorers[submission.task_id]
            scorer.add_submission(submission_id, submission.timestamp,
                                  submission.user.username,
                                  [float(ev.outcome)
                                   for ev in submission.evaluations],
                                  submission.tokened())

            # Update the ranking view
            contest = session.query(Contest).\
                      filter_by(id=self.contest_id).first()
            contest.update_ranking_view(self.scorers,
                                        task=submission.task)

            score = scorer.scores.get(submission.user.username, 0.0)
            # TODO: implement extras in scoretype
            extra = []

            # Data to send to remote rankings
            sub_url = "/subs/%s" % submission_id
            sub_post_data = {"user": submission.user.username,
                             "task": submission.task.name,
                             "time": submission.timestamp,
                             "score": score,
                             "token": False,
                             "extra": extra}
            sub_put_data = {"time": submission.timestamp,
                            "score": score,
                            "extra": extra}

        # TODO: ScoreRelative here does not work with remote
        # rankings (it does in the ranking view) because we
        # update only the user owning the submission.
        for ranking in self.rankings:
            self.operation_queue.append((self.send_score,
                                         [ranking, sub_url,
                                          sub_post_data, sub_put_data]))

    def send_score(self, ranking, sub_url, sub_post_data, sub_put_data):
        """Send a score to the remote ranking.

        ranking ((string, string)): address and authorization string
                                    of ranking server.
        sub_url (string): relative url in the remote ranking.
        sub_post_data (dict): dictionary to send to the ranking to
                              create the submission.
        sub_put_data (dict): dictionary to send to the ranking to
                             update the submission.
        return (bool): success of operation.

        """
        logger.info("Posting new score %s for submission %s." %
                    (sub_put_data["score"], sub_url))
        connection = httplib.HTTPConnection(ranking[0])
        auth = ranking[1]

        # We try to use put, if something goes wrong (i.e., the
        # submission does not exists in the server), we try also to
        # post before.
        status = put_data(connection, sub_url, sub_put_data, auth)

        if status not in [200, 201]:
            safe_post_data(connection, sub_url, sub_post_data, auth,
                           "sending submission %s" % sub_url)
            safe_put_data(connection, sub_url, sub_put_data, auth,
                          "sending submission %s" % sub_url)

    @rpc_method
    def submission_tokened(self, submission_id, timestamp):
        """This RPC inform ScoringService that the user has played the
        token on a submission.

        submission_id (int): the id of the submission that changed.
        timestamp (int): the time of the token.

        """
        with SessionGen(commit=False) as session:
            submission = Submission.get_from_id(submission_id, session)
            if submission is None:
                logger.error("Received request for "
                             "unexistent submission id %s." % submission_id)
                raise KeyError
            if submission.user.hidden:
                return

            sub_url = "/subs/%s" % submission_id
            sub_post_data = {"user": submission.user.username,
                             "task": submission.task.name,
                             "time": submission.timestamp,
                             "score": 0.0,
                             "token": False,
                             "extra": []}
            sub_put_data = {"time": timestamp,
                            "token": True},

        for ranking in self.rankings:
            self.operation_queue.append((self.send_token,
                                         [ranking, sub_url,
                                          sub_post_data, sub_put_data]))

    def send_token(self, ranking, sub_url, sub_post_data, sub_put_data):
        """Send the data that a token has been played.

        ranking ((string, string)): address and authorization string
                                    of ranking server.
        sub_url (string): relative url in the remote ranking.
        sub_post_data (dict): dictionary to send to the ranking to
                              create the submission.
        sub_put_data (dict): dictionary to send to the ranking to
                             update the submission.
        return (bool): success of operation.

        """
        logger.info("Posting token usage for submission %s." % sub_url)
        connection = httplib.HTTPConnection(ranking[0])
        auth = ranking[1]

        # We try to use put, if something goes wrong (i.e., the
        # submission does not exists in the server), we try also to
        # post before.
        status = put_data(connection, sub_url, sub_put_data, auth)

        if status not in [200, 201]:
            safe_post_data(connection, sub_url, sub_post_data, auth,
                           "sending submission %s" % sub_url)
            safe_put_data(connection, sub_url, sub_put_data, auth,
                          "sending token for submission %s" % sub_url)


def main():
    import sys
    if len(sys.argv) < 2:
        print sys.argv[0], "shard [contest]"
    else:
        ScoringService(int(sys.argv[1]),
                     ask_for_contest(1)).run()


if __name__ == "__main__":
    main()
