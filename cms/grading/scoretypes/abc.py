#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 wafrelka <wafrelka@gmail.com>
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


"""In this file there is the basic infrastructure from which we can
build a score type.

A score type is a class that receives all submissions for a task and
assign them a score, keeping the global state of the scoring for the
task.

"""

import logging
import re
from abc import ABCMeta, abstractmethod

from cms import FEEDBACK_LEVEL_RESTRICTED
from cms.db import SubmissionResult
from cms.grading.steps import EVALUATION_MESSAGES
from cms.locale import Translation, DEFAULT_TRANSLATION
from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT
from jinja2 import Template


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message: str):
    return message


class ScoreType(metaclass=ABCMeta):
    """Base class for all score types, that must implement all methods
    defined here.

    """

    TEMPLATE = ""

    def __init__(self, parameters: object, public_testcases: dict[str, bool]):
        """Initializer.

        parameters: format is specified in the subclasses.
        public_testcases: associate to each testcase's codename
                          a boolean indicating if the testcase
                          is public.

        """
        self.parameters = parameters
        self.public_testcases = public_testcases

        # Preload the maximum possible scores.
        try:
            self.max_score, self.max_public_score, self.ranking_headers = \
                self.max_scores()
        except Exception as e:
            raise ValueError(
                "Unable to instantiate score type (probably due to invalid "
                "values for the score type parameters): %s." % e)

        self.template: Template = GLOBAL_ENVIRONMENT.from_string(self.TEMPLATE)

    @staticmethod
    def format_score(
        score: float,
        max_score: float,
        unused_score_details: object,
        score_precision: int,
        translation: Translation = DEFAULT_TRANSLATION,
    ) -> str:
        """Produce the string of the score that is shown in CWS.

        In the submission table in the task page of CWS the global
        score of the submission is shown (the sum of all subtask and
        testcases). This method is in charge of producing the actual
        text that is shown there. It can be overridden to provide a
        custom message (e.g. "Accepted"/"Rejected").

        score: the global score of the submission.
        max_score: the maximum score that can be achieved.
        unused_score_details: the opaque data structure that
            the ScoreType produced for the submission when scoring it.
        score_precision: the maximum number of digits of the
            fractional digits to show.
        translation: the translation to use.

        return: the message to show.

        """
        return "%s / %s" % (
            translation.format_decimal(round(score, score_precision)),
            translation.format_decimal(round(max_score, score_precision)))

    def get_html_details(
        self,
        score_details: object,
        feedback_level: str = FEEDBACK_LEVEL_RESTRICTED,
        translation: Translation = DEFAULT_TRANSLATION,
    ) -> str:
        """Return an HTML string representing the score details of a
        submission.

        score_details: the data saved by the score type
            itself in the database; can be public or private.
        feedback_level: the level of details to show to users.
        translation: the translation to use.

        return: an HTML string representing score_details.

        """
        _ = translation.gettext
        n_ = translation.ngettext
        if score_details is None:
            logger.error("Found a null score details string. "
                         "Try invalidating scores.")
            return _("Score details temporarily unavailable.")
        else:
            # FIXME we should provide to the template all the variables
            # of a typical CWS context as it's entitled to expect them.
            try:
                return self.template.render(details=score_details,
                                            feedback_level=feedback_level,
                                            translation=translation,
                                            gettext=_, ngettext=n_)
            except Exception:
                logger.error("Found an invalid score details string. "
                             "Try invalidating scores.")
                return _("Score details temporarily unavailable.")

    @abstractmethod
    def max_scores(self) -> tuple[float, float, list[str]]:
        """Returns the maximum score that one could aim to in this
        problem. Also return the maximum score from the point of view
        of a user that did not play the token. And the headers of the
        columns showing extra information (e.g. subtasks) in RWS.
        Depend on the subclass.

        return: maximum score and maximum score with only public
            testcases; ranking headers.

        """
        pass

    @abstractmethod
    def compute_score(
        self, submission_result: SubmissionResult
    ) -> tuple[float, object, float, object, list[str]]:
        """Computes a score of a single submission.

        submission_result: the submission
            result of which we want the score

        return: respectively: the score, an opaque JSON-like data
            structure with additional information (e.g. testcases' and
            subtasks' score) that will be converted to HTML by
            get_html_details, the score and a similar data structure
            from the point of view of a user who did not play a token,
            the list of strings to send to RWS.

        """
        pass


class ScoreTypeAlone(ScoreType):
    """Intermediate class to manage tasks where the score of a
    submission depends only on the submission itself and not on the
    other submissions' outcome. Remains to implement compute_score to
    obtain the score of a single submission and max_scores.

    """
    pass


class ScoreTypeGroup(ScoreTypeAlone):
    """Intermediate class to manage tasks whose testcases are
    subdivided in groups (or subtasks). The score type parameters must
    be in the form [[m, t, ...], [...], ...], where m is the maximum
    score for the given subtask and t is the parameter for specifying
    testcases.

    If t is int, it is interpreted as the number of testcases
    comprising the subtask (that are consumed from the first to the
    last, sorted by num). If t is unicode, it is interpreted as the regular
    expression of the names of target testcases. All t must have the same type.

    A subclass must implement the method 'get_public_outcome' and
    'reduce'.

    """
    # the format of parameters is impossible to type-hint correctly, it seems...
    # this hint is (mostly) correct for the methods this base class implements,
    # subclasses might need a longer tuple.
    parameters: list[tuple[float, int | str]]

    # Mark strings for localization.
    N_("Subtask %(index)s")
    N_("#")
    N_("Outcome")
    N_("Details")
    N_("Execution time")
    N_("Memory used")
    N_("N/A")
    TEMPLATE = """\
{% for st in details %}
    {% if "score_fraction" in st %}
        {% if st["score_fraction"] >= 1.0 %}
<div class="subtask correct">
        {% elif st["score_fraction"] <= 0.0 %}
<div class="subtask notcorrect">
        {% else %}
<div class="subtask partiallycorrect">
        {% endif %}
    {% else %}
<div class="subtask undefined">
    {% endif %}
    <div class="subtask-head">
        <span class="title">
            {% trans index=st["idx"] %}Subtask {{ index }}{% endtrans %}
        </span>
    {% if "score" in st and "max_score" in st %}
        <span class="score">
            ({{ st["score"]|format_decimal }}
             / {{ st["max_score"]|format_decimal }})
        </span>
    {% else %}
        <span class="score">
            ({% trans %}N/A{% endtrans %})
        </span>
    {% endif %}
    </div>
    <div class="subtask-body">
        <table class="testcase-list">
            <thead>
                <tr>
                    <th class="idx">
                        {% trans %}#{% endtrans %}
                    </th>
                    <th class="outcome">
                        {% trans %}Outcome{% endtrans %}
                    </th>
                    <th class="details">
                        {% trans %}Details{% endtrans %}
                    </th>
    {% if feedback_level == FEEDBACK_LEVEL_FULL %}
                    <th class="execution-time">
                        {% trans %}Execution time{% endtrans %}
                    </th>
                    <th class="memory-used">
                        {% trans %}Memory used{% endtrans %}
                    </th>
    {% endif %}
                </tr>
            </thead>
            <tbody>
    {% for tc in st["testcases"] %}
        {% set show_tc = "outcome" in tc
               and ((feedback_level == FEEDBACK_LEVEL_FULL)
               or (feedback_level == FEEDBACK_LEVEL_RESTRICTED
               and tc["show_in_restricted_feedback"])
               or (feedback_level == FEEDBACK_LEVEL_OI_RESTRICTED
               and tc["show_in_oi_restricted_feedback"])) %}
        {% if show_tc %}
            {% if tc["outcome"] == "Correct" %}
                <tr class="correct">
            {% elif tc["outcome"] == "Not correct" %}
                <tr class="notcorrect">
            {% else %}
                <tr class="partiallycorrect">
            {% endif %}
                    <td class="idx">{{ loop.index }}</td>
                    <td class="outcome">{{ _(tc["outcome"]) }}</td>
                    <td class="details">
                      {{ tc["text"]|format_status_text }}
                    </td>
            {% if feedback_level == FEEDBACK_LEVEL_FULL %}
                    <td class="execution-time">
                {% if "time_limit_was_exceeded" in tc and tc["time_limit_was_exceeded"] %}
                        &gt; {{ tc["time_limit"]|format_duration }}
                {% elif "time" in tc and tc["time"] is not none %}
                        {{ tc["time"]|format_duration }}
                {% else %}
                        {% trans %}N/A{% endtrans %}
                {% endif %}
                    </td>
                    <td class="memory-used">
                {% if "memory" in tc and tc["memory"] is not none %}
                        {{ tc["memory"]|format_size }}
                {% else %}
                        {% trans %}N/A{% endtrans %}
                {% endif %}
                    </td>
            {% endif %}
                </tr>
        {% else %}
            {% if feedback_level != FEEDBACK_LEVEL_OI_RESTRICTED %}
                <tr class="undefined">
                    <td class="idx">{{ loop.index }}</td>
                {% if feedback_level == FEEDBACK_LEVEL_FULL %}
                    <td colspan="4">
                {% else %}
                    <td colspan="2">
                {% endif %}
                        {% trans %}N/A{% endtrans %}
                    </td>
                </tr>
            {% endif %}
        {% endif %}
    {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endfor %}"""

    def retrieve_target_testcases(self) -> list[list[str]]:
        """Return the list of the target testcases for each subtask.

        Each element of the list consist of multiple strings.
        Each string represents the testcase name which should be included
        to the corresponding subtask.
        The order of the list is the same as 'parameters'.

        return: the list of the target testcases for each task.

        """

        t_params = [p[1] for p in self.parameters]

        if all(isinstance(t, int) for t in t_params):

            # XXX Lexicographical order by codename
            indices = sorted(self.public_testcases.keys())
            current = 0
            targets = []

            for t in t_params:
                # this assert is guaranteed by the `if` check, but the type checker is dumb...
                assert isinstance(t, int)
                next_ = current + t
                targets.append(indices[current:next_])
                current = next_

            return targets

        elif all(isinstance(t, str) for t in t_params):

            indices = sorted(self.public_testcases.keys())
            targets = []

            for t in t_params:
                assert isinstance(t, str)
                regexp = re.compile(t)
                target = [tc for tc in indices if regexp.match(tc)]
                if not target:
                    raise ValueError(
                        "No testcase matches against the regexp '%s'" % t)
                targets.append(target)

            return targets

        raise ValueError(
            "In the score type parameters, the second value of each element "
            "must have the same type (int or unicode)")

    def max_scores(self):
        """See ScoreType.max_score."""
        score = 0.0
        public_score = 0.0
        headers = list()

        targets = self.retrieve_target_testcases()

        for st_idx, parameter in enumerate(self.parameters):
            target = targets[st_idx]
            if (parameter[0] > 0):
                score += parameter[0]
            if all(self.public_testcases[tc_idx] for tc_idx in target):
                if (parameter[0] > 0):
                    public_score += parameter[0]
            headers += ["Subtask %d (%g)" % (st_idx, parameter[0])]

        return score, public_score, headers

    def compute_score(self, submission_result):
        """See ScoreType.compute_score."""
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return 0.0, [], 0.0, [], ["%lg" % 0.0 for _ in self.parameters]

        score = 0
        subtasks = []
        public_score = 0
        public_subtasks = []
        ranking_details = []

        targets = self.retrieve_target_testcases()
        evaluations = {ev.codename: ev for ev in submission_result.evaluations}

        score_precision = submission_result.submission.task.score_precision

        for st_idx, parameter in enumerate(self.parameters):
            target = targets[st_idx]

            testcases = []
            public_testcases = []
            # In "Restricted" feedback mode:
            #   show until the first testcase with a lowest score
            # In "OI Restricted" feedback mode:
            #   show only the first testcase with a lowest score

            tc_first_lowest_idx = None
            tc_first_lowest_score = None
            for tc_idx in target:
                tc_score = float(evaluations[tc_idx].outcome)
                tc_outcome = self.get_public_outcome(
                    tc_score, parameter)

                time_limit_was_exceeded = False
                if evaluations[tc_idx].text == [EVALUATION_MESSAGES.get("timeout").message]:
                    time_limit_was_exceeded = True

                testcases.append({
                    "idx": tc_idx,
                    "outcome": tc_outcome,
                    "text": evaluations[tc_idx].text,
                    "time": evaluations[tc_idx].execution_time,
                    "time_limit": evaluations[tc_idx].dataset.time_limit,
                    "time_limit_was_exceeded": time_limit_was_exceeded,
                    "memory": evaluations[tc_idx].execution_memory,
                    "show_in_restricted_feedback": self.public_testcases[tc_idx],
                    "show_in_oi_restricted_feedback": self.public_testcases[tc_idx]})

                if self.public_testcases[tc_idx]:
                    public_testcases.append(testcases[-1])
                    if tc_first_lowest_score is None or \
                            tc_score < tc_first_lowest_score:
                        tc_first_lowest_idx = tc_idx
                        tc_first_lowest_score = tc_score
                else:
                    public_testcases.append({"idx": tc_idx})

            st_score_fraction = self.reduce(
                [float(evaluations[tc_idx].outcome) for tc_idx in target],
                parameter)
            st_score = st_score_fraction * parameter[0]
            rounded_score = round(st_score, score_precision)

            if tc_first_lowest_idx is not None and st_score_fraction < 1.0:
                for tc in testcases:
                    if not self.public_testcases[tc["idx"]]:
                        continue
                    tc["show_in_restricted_feedback"] = (
                        tc["idx"] <= tc_first_lowest_idx)
                    tc["show_in_oi_restricted_feedback"] = (
                        tc["idx"] == tc_first_lowest_idx)

            score += st_score
            subtasks.append({
                "idx": st_idx,
                # We store the fraction so that an "example" testcase
                # with a max score of zero is still properly rendered as
                # correct or incorrect.
                "score_fraction": st_score_fraction,
                # But we also want the properly rounded score for display.
                "score": rounded_score,
                "max_score": parameter[0],
                "testcases": testcases})
            if all(self.public_testcases[tc_idx] for tc_idx in target):
                public_score += st_score
                public_subtasks.append(subtasks[-1])
            else:
                public_subtasks.append({"idx": st_idx,
                                        "testcases": public_testcases})
            ranking_details.append("%g" % st_score)

        return score, subtasks, public_score, public_subtasks, ranking_details

    @abstractmethod
    def get_public_outcome(self, outcome: float, parameter: list) -> str:
        """Return a public outcome from an outcome.

        The public outcome is shown to the user, and this method
        return the public outcome associated to the outcome of a
        submission in a testcase contained in the group identified by
        parameter.

        outcome: the outcome of the submission in the testcase.
        parameter: the parameters of the current group.

        return: the public output.

        """
        pass

    @abstractmethod
    def reduce(self, outcomes: list[float], parameter: list) -> float:
        """Return the score of a subtask given the outcomes.

        outcomes: the outcomes of the submission in
            the testcases of the group.
        parameter: the parameters of the group.

        return: the public output.

        """
        pass
