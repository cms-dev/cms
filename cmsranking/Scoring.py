#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2019 Luca Chiodini <luca@chiodini.org>
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

from collections.abc import Callable, Generator
import heapq
import logging
from itertools import zip_longest
from typing import Any

from cmscommon.constants import \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK, SCORE_MODE_MAX_TOKENED_LAST
from cmsranking.Store import Store
from cmsranking.Subchange import Subchange
from cmsranking.Submission import Submission
from cmsranking.Task import Task


logger = logging.getLogger(__name__)


class NumberSet:
    """A fast data structure on numbers.

    It supports:
    - inserting a value
    - removing a value
    - querying the maximum value

    It can hold the same value multiple times.

    This data structure could be implemented with a binary tree, but
    at the moment we're actually using a standard python list.

    """
    def __init__(self):
        self._impl: list[float] = list()

    def insert(self, val: float):
        self._impl.append(val)

    def remove(self, val: float):
        self._impl.remove(val)

    def query(self) -> float:
        return max(self._impl + [0.0])

    def clear(self):
        del self._impl[:]


class Score:
    """The score of a user for a task.

    It computes the current score (and its history) for this
    user/task.  It gets notified in case a submission is created,
    updated and deleted.

    """
    # We assume that the submissions will all have different times,
    # since cms enforces a minimum delay between two submissions of
    # the same user for the same task.
    # On the other hand, different subchanges may have the same time
    # but cms assures that the order in which the subchanges have to
    # be processed is the ascending order of their keys (actually,
    # this is enforced only for subchanges with the same time).
    def __init__(self, score_mode: str):
        # The submissions in their current status.
        self._submissions: dict[str, Submission] = dict()

        # The list of changes of the submissions.
        self._changes: list[Subchange] = list()

        # The set of the scores of the currently released submissions.
        self._released = NumberSet()

        # The last submitted submission (with at least one subchange).
        self._last: Submission | None = None

        # The history of score changes (the actual "output" of this
        # object).
        self._history: list[tuple[int, float]] = list()

        self._score_mode: str = score_mode

    def append_change(self, change: Subchange):
        # Remove from released submission (if needed), apply changes,
        # add back to released submissions (if needed) and check if
        # it's the last. Compute the new score and, if it changed,
        # append it to the history.
        s_id = change.submission
        if self._submissions[s_id].token:
            self._released.remove(self._submissions[s_id].score)
        if change.score is not None:
            self._submissions[s_id].score = change.score
        if change.token is not None:
            self._submissions[s_id].token = change.token
        if change.extra is not None:
            self._submissions[s_id].extra = change.extra
        if self._submissions[s_id].token:
            self._released.insert(self._submissions[s_id].score)
        if change.score is not None and \
                (self._last is None or
                 self._submissions[s_id].time > self._last.time):
            self._last = self._submissions[s_id]

        if self._score_mode == SCORE_MODE_MAX:
            score = max((submission.score
                         for submission in self._submissions.values()),
                        default=0.0)
        elif self._score_mode == SCORE_MODE_MAX_SUBTASK:
            scores_by_submission = (map(float, s.extra or [s.score])
                                    for s in self._submissions.values())
            scores_by_subtask = zip_longest(*scores_by_submission,
                                            fillvalue=0.0)
            score = float(sum(max(s) for s in scores_by_subtask))
        elif self._score_mode == SCORE_MODE_MAX_TOKENED_LAST:
            score = max(self._released.query(),
                        self._last.score if self._last is not None else 0.0)
        else:
            raise ValueError("Unexpected score mode '%s'" % self._score_mode)

        if score != self.get_score():
            self._history.append((change.time, score))

    def get_score(self) -> float:
        return self._history[-1][1] if len(self._history) > 0 else 0.0

    def reset_history(self):
        # Delete everything except the submissions and the subchanges.
        self._last = None
        self._released.clear()
        del self._history[:]

        # Reset the submissions at their default value.
        for sub in self._submissions.values():
            sub.score = 0.0
            sub.token = False
            sub.extra = list()

        # Append each change, one at a time.
        for change in self._changes:
            self.append_change(change)

    def create_subchange(self, key: str, subchange: Subchange):
        # Insert the subchange at the right position inside the
        # (sorted) list and call the appropriate method (append_change
        # or reset_history)
        if len(self._changes) == 0 or \
                subchange.time > self._changes[-1].time or \
                (subchange.time == self._changes[-1].time and
                 subchange.key > self._changes[-1].key):
            self._changes.append(subchange)
            self.append_change(subchange)
        else:
            for idx, val in enumerate(self._changes):
                if subchange.time < val.time or \
                   (subchange.time == val.time and subchange.key < val.key):
                    self._changes.insert(idx, subchange)
                    break
            self.reset_history()
            logger.info("Reset history for user '%s' and task '%s' after "
                        "creating subchange '%s' for submission '%s'",
                        self._submissions[subchange.submission].user,
                        self._submissions[subchange.submission].task,
                        key, subchange.submission)

    def update_subchange(self, key: str, subchange: Subchange):
        # Update the subchange inside the (sorted) list and,
        # regardless of its position in that list, reset the history.
        for i in range(len(self._changes)):
            if self._changes[i].key == key:
                self._changes[i] = subchange
        self.reset_history()
        logger.info("Reset history for user '%s' and task '%s' after "
                    "creating subchange '%s' for submission '%s'",
                    self._submissions[subchange.submission].user,
                    self._submissions[subchange.submission].task,
                    key, subchange.submission)

    def delete_subchange(self, key: str):
        # Delete the subchange from the (sorted) list and reset the
        # history.
        self._changes = [c for c in self._changes if c.key != key]
        self.reset_history()
        logger.info("Reset history after deleting subchange '%s'", key)

    def create_submission(self, key: str, submission: Submission):
        # A new submission never triggers an update in the history,
        # since it doesn't have a score.
        submission.score = 0.0
        submission.token = False
        submission.extra = list()
        self._submissions[key] = submission

    def update_submission(self, key: str, submission: Submission):
        # An updated submission may cause an update in history because
        # it may change the "last" submission at some point in
        # history.
        self._submissions[key] = submission
        self.reset_history()

    def delete_submission(self, key: str):
        # A deleted submission shouldn't cause any history changes
        # (because its associated subchanges are deleted before it)
        # but we reset it just to be sure...
        if key in self._submissions:
            del self._submissions[key]
            # Delete all its subchanges.
            self._changes = [c for c in self._changes if c.submission != key]
            self.reset_history()

    def update_score_mode(self, score_mode: str):
        self._score_mode = score_mode


class ScoringStore:
    """A manager for all instances of Scoring.

    It listens to the events of submission_store and subchange_store and
    redirects them to the corresponding Score (based on their user/task).
    When asked to provide a global history of score changes it takes the
    ones of each Score and combines them toghether (using a binary heap).

    """
    # We can do an important assumption here too: since the data has
    # to be consistent we are sure that if there's at least one
    # subchange there's also at least one submission (and if there's
    # no submission there's no subchange). We can also assume that
    # when a submission is deleted its subchanges have already been
    # deleted. So we are sure that we can delete the Score after we
    # delete the last submission, but we cannot after we delete the
    # last subchange.
    def __init__(self, stores: dict[str, Store]):
        self.task_store: Store[Task] = stores["task"]
        self.submission_store: Store[Submission] = stores["submission"]
        self.subchange_store: Store[Subchange] = stores["subchange"]
        self.submission_store.add_create_callback(self.create_submission)
        self.submission_store.add_update_callback(self.update_submission)
        self.submission_store.add_delete_callback(self.delete_submission)
        self.subchange_store.add_create_callback(self.create_subchange)
        self.subchange_store.add_update_callback(self.update_subchange)
        self.subchange_store.add_delete_callback(self.delete_subchange)

        self._scores: dict[str, dict[str, Score]] = dict()
        self._callbacks: list[Callable[[str, str, float], Any]] = list()

    def init_store(self):
        """Load the scores from the stores.

        This method must be called by RankingWebServer after it
        finishes loading the data from disk.

        """
        for key, value in self.submission_store._store.items():
            self.create_submission(key, value)
        for key, value in sorted(self.subchange_store._store.items()):
            self.create_subchange(key, value)

    def add_score_callback(self, callback: Callable[[str, str, float], Any]):
        """Add a callback to be called when a score changes.

        Callbacks can be any kind of callable objects. They must
        accept three arguments: the user, the task and the new score.

        """
        self._callbacks.append(callback)

    def notify_callbacks(self, user: str, task: str, score: float):
        for call in self._callbacks:
            call(user, task, score)

    def create_submission(self, key: str, submission: Submission):
        if submission.user not in self._scores:
            self._scores[submission.user] = dict()
        if submission.task not in self._scores[submission.user]:
            task = self.task_store.retrieve(submission.task)
            self._scores[submission.user][submission.task] = \
                Score(score_mode=task["score_mode"])

        score_obj = self._scores[submission.user][submission.task]
        old_score = score_obj.get_score()
        score_obj.create_submission(key, submission)
        new_score = score_obj.get_score()
        if old_score != new_score:
            self.notify_callbacks(submission.user, submission.task, new_score)

    def update_submission(self, key: str, old_submission: Submission, submission: Submission):
        if old_submission.user != submission.user or \
                old_submission.task != submission.task:
            # TODO Delete all subchanges from the Score of the old
            # submission and create them on the new one.
            self.delete_submission(key, old_submission)
            self.create_submission(key, submission)
            return

        task = self.task_store.retrieve(submission.task)

        score_obj = self._scores[submission.user][submission.task]
        old_score = score_obj.get_score()
        score_obj.update_submission(key, submission)
        score_obj.update_score_mode(task["score_mode"])
        new_score = score_obj.get_score()
        if old_score != new_score:
            self.notify_callbacks(submission.user, submission.task, new_score)

    def delete_submission(self, key: str, submission: Submission):
        score_obj = self._scores[submission.user][submission.task]
        old_score = score_obj.get_score()
        score_obj.delete_submission(key)
        new_score = score_obj.get_score()
        if old_score != new_score:
            self.notify_callbacks(submission.user, submission.task, new_score)

        if len(self._scores[submission.user][submission.task]
               ._submissions) == 0:
            del self._scores[submission.user][submission.task]
        if len(self._scores[submission.user]) == 0:
            del self._scores[submission.user]

    def create_subchange(self, key: str, subchange: Subchange):
        submission = self.submission_store._store[subchange.submission]
        score_obj = self._scores[submission.user][submission.task]
        old_score = score_obj.get_score()
        score_obj.create_subchange(key, subchange)
        new_score = score_obj.get_score()
        if old_score != new_score:
            self.notify_callbacks(submission.user, submission.task, new_score)

    def update_subchange(self, key: str, old_subchange: Subchange, subchange: Subchange):
        if old_subchange.submission != subchange.submission:
            self.delete_subchange(key, old_subchange)
            self.create_subchange(key, subchange)
            return

        submission = self.submission_store._store[subchange.submission]
        score_obj = self._scores[submission.user][submission.task]
        old_score = score_obj.get_score()
        score_obj.update_subchange(key, subchange)
        new_score = score_obj.get_score()
        if old_score != new_score:
            self.notify_callbacks(submission.user, submission.task, new_score)

    def delete_subchange(self, key: str, subchange: Subchange):
        if subchange.submission not in self.submission_store:
            # Submission has just been deleted. We cannot retrieve the
            # user and the task, so we cannot clean up the Score obj.
            # But the delete_submission callback will do it for us!
            return
        submission = self.submission_store._store[subchange.submission]
        score_obj = self._scores[submission.user][submission.task]
        old_score = score_obj.get_score()
        score_obj.delete_subchange(key)
        new_score = score_obj.get_score()
        if old_score != new_score:
            self.notify_callbacks(submission.user, submission.task, new_score)

    def get_score(self, user: str, task: str) -> float:
        if user not in self._scores or task not in self._scores[user]:
            # We may want to raise an exception to distinguish between
            # "no submissions" and "submission with 0 points"
            return 0
        return self._scores[user][task].get_score()

    def get_submissions(self, user: str, task: str) -> dict[str, Submission]:
        if user not in self._scores or task not in self._scores[user]:
            return dict()
        return self._scores[user][task]._submissions

    def get_global_history(self) -> Generator[tuple[str, str, int, float]]:
        """Merge all individual histories into a global one.

        Take all per-user/per-task histories and merge them, providing
        a global history of all schore changes and return it using a
        generator.  Returned data is in the form (user_id, task_id,
        time, score).

        """
        # Use a priority queue, containing only one entry
        # per-user/per-task.
        queue: list[tuple[tuple[int, float], str, str, Score, int]] = list()
        for user, dic in self._scores.items():
            for task, scoring in dic.items():
                if scoring._history:
                    heapq.heappush(queue, (scoring._history[0],
                                           user, task, scoring, 0))

        # When an entry is popped, push the next entry for that
        # user/task (if any).
        while len(queue) != 0:
            (time, score), user, task, scoring, index = heapq.heappop(queue)
            yield (user, task, time, score)
            if len(scoring._history) > index + 1:
                heapq.heappush(queue, (scoring._history[index + 1],
                                       user, task, scoring, index + 1))
