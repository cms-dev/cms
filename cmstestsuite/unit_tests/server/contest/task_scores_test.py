"""Regression checks for task counters and their polling updates."""

from datetime import datetime, timedelta
import json
import shutil
import subprocess
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
import pytest

from cms import TOKEN_MODE_DISABLED
from cms.db import SubmissionResult
from cms.locale import DEFAULT_TRANSLATION
from cms.server.contest.handlers.base import BaseHandler
from cms.server.contest.handlers.tasksubmission import SubmissionStatusHandler
from cms.server.contest.jinja2_toolbox import CWS_ENVIRONMENT
from cmscommon.datetime import utc


def make_handler(phase=0, public_max=20, tokened=False, official=True):
    score_type = NS(
        max_score=100, max_public_score=public_max,
        format_score=lambda score, maximum, *a, **kw: f"{score:g} / {maximum:g}")
    task = NS(
        id=1, name="task1", title="Task one", score_mode="max", score_precision=2,
        token_mode=TOKEN_MODE_DISABLED, submission_format=[],
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
        token_mode=TOKEN_MODE_DISABLED, allow_questions=True, allow_user_tests=True,
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
    # Stub only the ORM query construction; execute the real scoring functions.
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
                    assert data["task_use_tokened_score"] == full
                    if not full and public_max == 0:
                        assert h.task_scores == {}
                        continue
                    use_full = full and public_max < 100
                    key = "task_tokened_score" if use_full else "task_public_score"
                    expected = (80 if use_full else min(80, public_max)) if official else 0
                    assert h.task_scores[1][0] == data[key] == expected
                    assert h.task_scores[1][2] == data[key + "_message"]


def test_unofficial_token_does_not_hide_official_public_score():
    h, task = make_handler(tokened=True, official=False)
    h.current_user.submissions.append(NS(
        task=task, task_id=1, official=True, timestamp=2, tokened=lambda: False,
        get_result=h.current_user.submissions[0].get_result))
    data = poll(h, task)
    assert data["task_use_tokened_score"] is False
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


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is needed to execute polling JavaScript")
def test_polling_javascript_preserves_analysis_and_official_scores():
    template = CWS_ENVIRONMENT.get_template("task_submissions.html")
    for phase, official, status in ((3, True, SubmissionResult.SCORED),
                                    (3, True, SubmissionResult.COMPILATION_FAILED),
                                    (0, False, SubmissionResult.SCORED)):
        h, task = make_handler(phase, tokened=not official, official=official)
        if not official:
            h.current_user.submissions.append(NS(
                task=task, task_id=1, official=True, timestamp=2, tokened=lambda: False,
                get_result=h.current_user.submissions[0].get_result))
        data = poll(h, task)
        data.update(status=status, status_text="Evaluated", max_score=100,
                    max_public_score=20)
        if status == SubmissionResult.SCORED:
            data["score"] = 80
        context = template.new_context(dict(
            task=task, actual_phase=phase, can_use_tokens=False,
            static_url=h.contest_url, gettext=DEFAULT_TRANSLATION.gettext))
        script = "".join(template.blocks["additional_js"](context))
        expected = "80 / 100" if phase == 3 else "20 / 20"
        harness = """
const assert = require('node:assert/strict');
const chain = new Proxy(function() {}, {get: () => chain, apply: () => chain});
global.$ = () => chain;
global.document = {};
""" + script + """
update_score = () => {};
let badge;
update_sidebar_task_score = (score, message) => { badge = message; };
""" + f"update_scores(1, {json.dumps(data)});\nassert.equal(badge, {json.dumps(expected)});"
        subprocess.run(["node"], input=harness, text=True, check=True,
                       capture_output=True)
