#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Pasit Sangprachathanarak <ouipingpasit@gmail.com>
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

"""Regression checks for task counters and their polling updates."""

from datetime import datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_INFINITE
from cms.locale import DEFAULT_TRANSLATION
from cms.server.contest.handlers.base import BaseHandler
from cms.server.contest.handlers.tasksubmission import SubmissionStatusHandler
from cms.server.contest.jinja2_toolbox import CWS_ENVIRONMENT
from cmscommon.datetime import utc


def make_handler(phase=0, public_max=20, tokened=False, official=True,
                 tokens=True):
    score_type = NS(
        max_score=100, max_public_score=public_max,
        format_score=lambda score, maximum, *a, **kw: f"{score:g} / {maximum:g}")
    task = NS(
        id=1, name="task1", title="Task one", score_mode="max", score_precision=2,
        token_mode=TOKEN_MODE_INFINITE if tokens else TOKEN_MODE_DISABLED,
        submission_format=[],
        get_allowed_languages=lambda: [],
        active_dataset=NS(score_type_object=score_type, time_limit=1,
                          memory_limit=1024, task_type_object=NS(name="Batch")))
    result = NS(score=80, public_score=min(80, public_max), score_details=[],
                public_score_details=[], scored=lambda: True)
    submission = NS(task=task, task_id=1, official=official, timestamp=1,
                    tokened=lambda: tokened, get_result=lambda dataset: result)
    now = datetime(2026, 1, 1, 12)
    group = NS(start=now - timedelta(hours=1), stop=now + timedelta(hours=1),
               analysis_enabled=False, per_user_time=None, phase=lambda t: 0)
    contest = NS(
        name="contest", description="Contest", tasks=[task], languages=[],
        show_task_scores_in_sidebar=True, show_task_scores_in_overview=True,
        token_mode=TOKEN_MODE_INFINITE if tokens else TOKEN_MODE_DISABLED,
        allow_questions=True, allow_user_tests=True,
        max_submission_number=None, max_user_test_number=None, timezone="UTC")
    participation = NS(
        contest=contest, submissions=[submission], group=group, unrestricted=False,
        starting_time=None, delay_time=timedelta(), extra_time=timedelta(),
        user=NS(username="user", first_name="", last_name="", timezone=None))
    handler = SubmissionStatusHandler.__new__(SubmissionStatusHandler)
    handler._current_user = participation
    handler.contest = contest
    handler.translation = DEFAULT_TRANSLATION
    handler.timestamp = now
    handler.contest_url = lambda *parts: "/" + "/".join(parts)
    handler.sql_session = MagicMock()
    handler.r_params = {"actual_phase": phase}
    handler._load_participation_for_scores = MagicMock(return_value=participation)
    handler._load_official_submissions = MagicMock(
        side_effect=lambda p: {1: [x for x in p.submissions if x.official]})
    return handler, task


def render_overview(handler):
    p = handler.current_user
    translation = DEFAULT_TRANSLATION
    return CWS_ENVIRONMENT.get_template("overview.html").render(
        handler=handler, contest=handler.contest, participation=p, user=p.user,
        phase=0, actual_phase=handler.r_params["actual_phase"], now=handler.timestamp,
        current_phase_begin=p.group.start, current_phase_end=p.group.stop,
        utc=utc, timezone=utc, available_translations={},
        translation=translation, gettext=translation.gettext,
        ngettext=translation.ngettext, testing_enabled=False,
        tokens_contest=TOKEN_MODE_DISABLED, tokens_tasks=TOKEN_MODE_DISABLED,
        xsrf_form_html="", url=handler.contest_url, contest_url=handler.contest_url,
        static_url=handler.contest_url)


def poll(handler, task):
    data = {}
    # Stub only the ORM query construction (returning the submissions of the
    # task); execute the real scoring functions.
    query = MagicMock()
    for method in ("filter", "options"):
        getattr(query, method).return_value = query
    query.all.return_value = [
        s for s in handler.current_user.submissions if s.task_id == task.id]
    handler.sql_session.query.return_value = query
    with patch("cms.server.contest.handlers.tasksubmission.Submission"), \
            patch("cms.server.contest.handlers.tasksubmission.joinedload"):
        handler.add_task_score(handler.current_user, task, data)
    return data


def test_initial_and_polled_scores_agree():
    for mode in ("max", "max_subtask", "max_tokened_last"):
        for phase in (0, 1, 2, 3, 4):
            for public_max in (0, 20, 100):
                for tokened, official in ((False, True), (True, True), (True, False)):
                    h, task = make_handler(phase, public_max, tokened, official)
                    task.score_mode = mode
                    data = poll(h, task)
                    full = phase == 3 or (tokened and official)
                    if not full and public_max == 0:
                        assert h.task_scores == {}
                        assert data["task_badge_score"] is None
                        continue
                    use_full = full and public_max < 100
                    key = "task_tokened_score" if use_full else "task_public_score"
                    expected = (80 if use_full else min(80, public_max)) if official else 0
                    assert h.task_scores[1][0] == data[key] == expected
                    assert h.task_scores[1][2] == data[key + "_message"]
                    assert_badge_matches(h, data)


def assert_badge_matches(h, data):
    """The JSON badge fields are exactly what the sidebar renders initially."""
    entry = h.task_scores.get(1)
    got = (data["task_badge_score"], data["task_badge_max_score"],
           data["task_badge_message"], data["task_badge_is_partial"])
    assert got == (entry if entry is not None else (None,) * 4)


def test_tokened_total_ignored_when_tokens_are_disabled():
    h, task = make_handler(tokened=True, tokens=False)
    data = poll(h, task)
    assert h.task_scores[1][2] == data["task_public_score_message"] == "20 / 20"
    assert_badge_matches(h, data)
    # ... except in analysis mode, where everything is shown.
    h, task = make_handler(phase=3, tokened=True, tokens=False)
    assert h.task_scores[1][2] == "80 / 100"


def test_partial_flag_is_kept():
    h, task = make_handler()
    sub = h.current_user.submissions[0]
    sub.get_result = lambda dataset: None
    data = poll(h, task)
    assert h.task_scores[1][3] is True
    assert data["task_badge_is_partial"] is True
    soup = BeautifulSoup(render_overview(h), "html.parser")
    assert soup.select_one(".main_task_list td.public_score img.task_score_loading")


def test_broken_task_does_not_break_other_tasks():
    h, task = make_handler()
    other = NS(**{**vars(task), "id": 2, "name": "task2"})
    h.contest.tasks.append(other)
    h.current_user.submissions.append(NS(
        task=other, task_id=2, official=True, timestamp=1, tokened=lambda: False,
        get_result=h.current_user.submissions[0].get_result))
    h._load_official_submissions.side_effect = lambda p: {
        s.task_id: [s] for s in p.submissions}

    class BrokenDataset:
        @property
        def score_type_object(self):
            raise ValueError("bad parameters")

    task.active_dataset = BrokenDataset()

    with patch("cms.server.contest.handlers.contest.logger") as logger:
        assert list(h.task_scores) == [2]
    logger.exception.assert_called_once()
    assert "task1" in logger.exception.call_args.args

    # An unknown score mode is handled in the same way.
    h, task = make_handler()
    task.score_mode = "nonsense"
    with patch("cms.server.contest.handlers.contest.logger"):
        assert h.task_scores == {}
    soup = BeautifulSoup(render_overview(h), "html.parser")
    assert soup.select_one(".task_score_badge.undefined").get_text(strip=True) == "N/A"


def test_unofficial_token_does_not_hide_official_public_score():
    h, task = make_handler(tokened=True, official=False)
    h.current_user.submissions.append(NS(
        task=task, task_id=1, official=True, timestamp=2, tokened=lambda: False,
        get_result=h.current_user.submissions[0].get_result))
    data = poll(h, task)
    assert data["task_badge_message"] == "20 / 20"
    assert_badge_matches(h, data)
    assert h.task_scores[1][2] == data["task_public_score_message"] == "20 / 20"


def test_prepare_parameters_do_not_load_scores():
    h, _ = make_handler()
    with patch.object(BaseHandler, "render_params", return_value={}):
        h.r_params = h.render_params()
    h._load_participation_for_scores.assert_not_called()
    # Neither a JSON response nor a details fragment accesses the lazy property.
    CWS_ENVIRONMENT.get_template("submission_details.html").render(sr=None, details=None)
    h._load_participation_for_scores.assert_not_called()


def test_overview_loads_once_only_when_counters_are_visible():
    for sidebar, overview, phase in ((True, True, 0), (False, True, 0),
                                      (True, False, 0), (False, False, 0),
                                      (True, True, -1)):
        h, _ = make_handler(phase)
        h.contest.show_task_scores_in_sidebar = sidebar
        h.contest.show_task_scores_in_overview = overview
        html = render_overview(h)
        assert h._load_participation_for_scores.call_count == int(
            (sidebar or overview) and phase >= 0)
        if (sidebar or overview) and phase >= 0:
            assert "20 / 20" in html


def test_missing_dataset_and_hidden_scores_render_as_unavailable():
    for missing_dataset in (False, True):
        h, task = make_handler(public_max=0)
        if missing_dataset:
            task.active_dataset = None
        assert h.task_scores == {}
        soup = BeautifulSoup(render_overview(h), "html.parser")
        assert soup.select_one(".task_score_badge.undefined").get_text(strip=True) == "N/A"
        assert soup.select_one(".main_task_list td.public_score.undefined").get_text(strip=True) == "N/A"
        assert "0 / 0" not in str(soup)


def test_overview_shows_total_score():
    h, _ = make_handler()
    soup = BeautifulSoup(render_overview(h), "html.parser")
    total = soup.select_one("#overview_total_score")
    assert "20 / 20" in total.get_text(" ", strip=True)
    # No total when no task has a score to show.
    h, _ = make_handler(public_max=0)
    soup = BeautifulSoup(render_overview(h), "html.parser")
    assert soup.select_one("#overview_total_score") is None
