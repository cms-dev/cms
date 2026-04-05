#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
# Copyright © 2026 Tobias Lenz <t_lenz94@web.de>
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

from datetime import datetime, timedelta
import logging

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_INFINITE
from cms.db import Token, Submission
from cms.db.session import Session
from cms.db.task import Task
from cms.db.user import Participation


__all__ = [
    "tokens_available",
    "UnacceptableToken", "TokenAlreadyPlayed", "accept_token"
]


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


def _tokens_available(
    mode: str,
    gen_initial: int,
    gen_number: int,
    gen_interval: timedelta,
    gen_max: int | None,
    max_number: int | None,
    min_interval: timedelta,
    start: datetime,
    history: list[datetime],
    timestamp: datetime,
) -> tuple[int, datetime | None, datetime | None]:
    """Return the same as tokens_available, on one set of parameters.

    Compute the same three values as tokens_available but taking into
    account only one set of parameters (either just contest-tokens or
    just task-tokens). What tokens_available will do is call this
    function twice, once for each type, and then combine the results.

    mode: one of the TOKEN_MODE_* constants.
    gen_initial: in finite mode, how many tokens the contestant
        starts with.
    gen_number: in finite mode, how many tokens the contestant
        receives (at most) at the end of each generation period.
    gen_interval: in finite mode, how long each generation
        period lasts.
    gen_max: in finite mode, a cap on the number of tokens
        that a contestant can have at any time due to generation (i.e.,
        generated tokens that would cause to exceed this number will be
        discarded).
    max_number: in finite mode, how many tokens can be used
        in total.
    min_interval: in finite mode, how much time needs to
        pass between two consecutive token usages.
    start: the time at which the contestant starts
        accumulating tokens.
    history: list of timestamps of played tokens, sorted
        in chronological order, up to the given timestamp.
    timestamp: the time relative to which the calculation
        should be made (has to be greater than or equal to all elements
        of history).

    return: same as tokens_available.

    """
    # If tokens are disabled there are no tokens available.
    if mode == TOKEN_MODE_DISABLED:
        return 0, None, None

    # If tokens are infinite there are always tokens available. Also,
    # the constraints don't apply.
    if mode == TOKEN_MODE_INFINITE:
        return -1, None, None

    # avail is the current number of available tokens. We are going to
    # rebuild all the history to know how many of them there are now.
    # We start with the initial number (it's already capped to max by
    # the DB). gen_initial can be ignored after this.
    avail = gen_initial

    def generate_tokens(begin_timestamp: datetime, end_timestamp: datetime) -> int:
        """Compute how many tokens are generated in the given interval.

        begin_timestamp: the beginning of the interval.
        end_timestamp: the end of the interval.

        return: the number of tokens generated.

        """
        # How many generation periods we passed from start to the
        # previous considered time?
        num_periods_before_begin = ((begin_timestamp - start).total_seconds()
                                    // gen_interval.total_seconds())
        # And from start to the current considered time?
        num_periods_before_end = ((end_timestamp - start).total_seconds()
                                  // gen_interval.total_seconds())
        # So...
        return gen_number * (num_periods_before_end - num_periods_before_begin)

    # Previous time we considered.
    prev_token_timestamp = start

    # Simulate!
    for next_token_timestamp in history:
        # Increment the number of tokens because of generation.
        assert prev_token_timestamp <= next_token_timestamp
        avail += generate_tokens(prev_token_timestamp, next_token_timestamp)
        if gen_max is not None:
            avail = min(avail, gen_max)

        # Play the token.
        avail -= 1

        prev_token_timestamp = next_token_timestamp

    assert prev_token_timestamp <= timestamp
    avail += generate_tokens(prev_token_timestamp, timestamp)
    if gen_max is not None:
        avail = min(avail, gen_max)

    # Compute the time at which the next token will be generated.
    next_gen_time = None
    if gen_number > 0 and (gen_max is None or avail < gen_max):
        num_periods_so_far = \
            (timestamp - start).total_seconds() // gen_interval.total_seconds()
        next_gen_time = start + gen_interval * (num_periods_so_far + 1)

    # If we have more tokens than how many we are allowed to play, cap
    # the result, and note that no more will be generated.
    if max_number is not None and avail >= max_number - len(history):
        avail = max_number - len(history)
        next_gen_time = None

    # expiration is the timestamp at which all min_intervals for the
    # tokens played up to now have expired (i.e. the first time at
    # which another token can be played). If no tokens have been played
    # so far, this time is the start of the contest.
    expiration = history[-1] + min_interval if len(history) > 0 else start

    # Don't report expiration when it has already passed or it is of no
    # use because no more tokens will ever be available to be played.
    if expiration <= timestamp or (avail == 0 and next_gen_time is None):
        expiration = None

    return avail, next_gen_time, expiration


def tokens_available(
    participation: Participation, task: Task, timestamp: datetime
) -> tuple[int, datetime | None, datetime | None]:
    """Return three pieces of data:

    [0] the number of available tokens the user can play on the task
        (independently from whether they can play any right now or not
        due to a min_interval waiting for expiration); -1 means
        infinite tokens;

    [1] the next time when a token will be generated (or None) from the
        user's perspective. That is, if the user does nothing, this is
        the first time in which their number of available tokens will
        be greater than [0];

    [2] the first time at which the user will be able to play any of
        their tokens, that is, the time when the min_interval for all
        relevant previously played tokens will expire, or None.

    More formally, let r the return value of this method. Then:

    if r[0] > 0 or r[0] == -1:
        we have tokens
        if r[2] is None:
            we can play a token
        else:
            we must wait till r[2] to play a token
        if r[1] is not None:
            next one will be generated at r[1]
        else:
            no other tokens will be generated (max/total reached?)
    else:
        we don't have tokens right now
        if r[1] is not None:
            next one will be generated at r[1]
            if r[2] is not None and r[2] > r[1]:
                but we must wait also until r[2] to play it
        else:
            no other tokens will be generated (max/total reached ?)

    Note also that this method assumes that all played tokens were
    regularly played, and that there are no tokens played in the
    future. Also, if r[0] == 0 and r[1] is None, then r[2] should be
    ignored.

    participation: the participation.
    task: the task.
    timestamp: the time relative to which making the
        calculation.

    return: see description above.

    """
    contest = participation.contest
    assert task.contest is contest

    # Take the list of the tokens already played (sorted by time).
    token_timestamps: list[tuple[datetime, int]] = (
        participation.sa_session.query(Token.timestamp, Submission.task_id)
        .select_from(Token)
        .filter(Token.timestamp <= timestamp)
        .join(Submission)
        .filter(Submission.participation == participation)
        .order_by(Token.timestamp)
        .all()
    )

    contest_history = list(
        ts for ts, _ in token_timestamps)
    task_history = list(
        ts for ts, task_id in token_timestamps if task_id == task.id)

    # If the contest is USACO-style (i.e., each user starts when they
    # decide so), then the tokens start being generated at the user's
    # starting time; otherwise, at the start of the contest.
    if participation.group.per_user_time is not None:
        start = participation.starting_time
    else:
        start = participation.group.start

    # Compute separately for contest and task.
    res_contest = _tokens_available(
        contest.token_mode, contest.token_gen_initial, contest.token_gen_number,
        contest.token_gen_interval, contest.token_gen_max,
        contest.token_max_number, contest.token_min_interval, start,
        contest_history, timestamp)
    res_task = _tokens_available(
        task.token_mode, task.token_gen_initial, task.token_gen_number,
        task.token_gen_interval, task.token_gen_max, task.token_max_number,
        task.token_min_interval, start, task_history, timestamp)

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
        # same as having a finite number that is strictly greater than
        # the number of task tokens. The same holds the other way, too.
        if res_contest[0] == -1:
            res_contest = (res_task[0] + 1,) + res_contest[1:]
        if res_task[0] == -1:
            res_task = (res_contest[0] + 1,) + res_task[1:]

        # About the next token generation time: we need to find out
        # when the *minimum* between res_contest[0] and res_task[0] is
        # increased by one, so if there is a strict minimum we need
        # to consider only the next generation time for it. Otherwise,
        # if they are equal, we need to wait for an additional token of
        # both types to be generated and we store the maximum between
        # the two next times of generation.
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


class UnacceptableToken(Exception):
    """Raised when a token request can't be accepted."""

    def __init__(self, subject: str, text: str):
        super().__init__(subject, text)
        self.subject = subject
        self.text = text


class TokenAlreadyPlayed(Exception):
    """Raised when the same token request is received more than once."""

    def __init__(self, subject: str, text: str):
        super().__init__(subject, text)
        self.subject = subject
        self.text = text


def accept_token(
    sql_session: Session, submission: Submission, timestamp: datetime
) -> Token:
    """Add a token to the database.

    This function is primarily called by CWS when a contestant sends a
    request to play a token on a submission. It received the arguments
    of such a request, it validates them and, if there are no issues,
    it adds a token to the database, for the given submission at the
    given timestamp.

    sql_session: the SQLAlchemy database session to use.
    submission: the submission on which the token should
        be applied (the participation, task and contest will be
        extracted from here).
    timestamp: the moment at which the request occurred.

    return: the Token that was added to the database.

    raise (UnacceptableToken): if some of the requirements that have to
        be met in order for the request to be accepted don't hold.
    raise (TokenAlreadyPlayed): if the request is for adding a token to
        a submission that already has one.

    """
    tokens_available_ = tokens_available(submission.participation,
                                         submission.task, timestamp)

    if tokens_available_[0] == 0 or tokens_available_[2] is not None:
        logger.warning("User %s tried to play a token when they "
                       "shouldn't.", submission.participation.user.username)
        raise UnacceptableToken(
            N_("Token request discarded"),
            N_("Your request has been discarded because you have no "
               "tokens available."))

    if submission.token is not None:
        raise TokenAlreadyPlayed(
            N_("Token request discarded"),
            N_("Your request has been discarded because "
               "you already used a token on that submission."))

    token = Token(timestamp, submission=submission)
    sql_session.add(token)

    return token
