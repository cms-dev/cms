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
from cms.locale import DEFAULT_TRANSLATION
from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class ScoreType(metaclass=ABCMeta):
    """Base class for all score types, that must implement all methods
    defined here.

    """

    TEMPLATE = ""

    def __init__(self, parameters, public_testcases):
        """Initializer.

        parameters (object): format is specified in the subclasses.
        public_testcases (dict): associate to each testcase's codename
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

        self.template = GLOBAL_ENVIRONMENT.from_string(self.TEMPLATE)

    @staticmethod
    def format_score(score, max_score, unused_score_details,
                     score_precision, translation=DEFAULT_TRANSLATION):
        """Produce the string of the score that is shown in CWS.

        In the submission table in the task page of CWS the global
        score of the submission is shown (the sum of all subtask and
        testcases). This method is in charge of producing the actual
        text that is shown there. It can be overridden to provide a
        custom message (e.g. "Accepted"/"Rejected").

        score (float): the global score of the submission.
        max_score (float): the maximum score that can be achieved.
        unused_score_details (string): the opaque data structure that
            the ScoreType produced for the submission when scoring it.
        score_precision (int): the maximum number of digits of the
            fractional digits to show.
        translation (Translation): the translation to use.

        return (string): the message to show.

        """
        return "%s / %s" % (
            translation.format_decimal(round(score, score_precision)),
            translation.format_decimal(round(max_score, score_precision)))

    def get_html_details(self, score_details,
                         feedback_level=FEEDBACK_LEVEL_RESTRICTED,
                         translation=DEFAULT_TRANSLATION):
        """Return an HTML string representing the score details of a
        submission.

        score_details (object): the data saved by the score type
            itself in the database; can be public or private.
        feedback_level (str): the level of details to show to users.
        translation (Translation): the translation to use.

        return (string): an HTML string representing score_details.

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
    def max_scores(self):
        """Returns the maximum score that one could aim to in this
        problem. Also return the maximum score from the point of view
        of a user that did not play the token. And the headers of the
        columns showing extra information (e.g. subtasks) in RWS.
        Depend on the subclass.

        return (float, float, [string]): maximum score and maximum
            score with only public testcases; ranking headers.

        """
        pass

    @abstractmethod
    def compute_score(self, unused_submission_result):
        """Computes a score of a single submission.

        unused_submission_result (SubmissionResult): the submission
            result of which we want the score

        return (float, object, float, object, [str]): respectively: the
            score, an opaque JSON-like data structure with additional
            information (e.g. testcases' and subtasks' score) that will
            be converted to HTML by get_html_details, the score and a
            similar data structure from the point of view of a user who
            did not play a token, the list of strings to send to RWS.

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
    {% if "score_fraction" in st and "max_score" in st %}
        {% set score = st["score_fraction"] * st["max_score"] %}
        <span class="score">
            ({{ score|round(2)|format_decimal }}
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
        {% if "outcome" in tc
               and (feedback_level == FEEDBACK_LEVEL_FULL
                    or tc["show_in_restricted_feedback"]) %}
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
                {% if "time" in tc and tc["time"] is not none %}
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
    {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endfor %}"""

    def retrieve_target_testcases(self):
        """Return the list of the target testcases for each subtask.

        Each element of the list consist of multiple strings.
        Each string represents the testcase name which should be included
        to the corresponding subtask.
        The order of the list is the same as 'parameters'.

        return ([[unicode]]): the list of the target testcases for each task.

        """

        t_params = [p[1] for p in self.parameters]

        if all(isinstance(t, int) for t in t_params):

            # XXX Lexicographical order by codename
            indices = sorted(self.public_testcases.keys())
            current = 0
            targets = []

            for t in t_params:
                next_ = current + t
                targets.append(indices[current:next_])
                current = next_

            return targets

        elif all(isinstance(t, str) for t in t_params):

            indices = sorted(self.public_testcases.keys())
            targets = []

            for t in t_params:
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
            score += parameter[0]
            if all(self.public_testcases[tc_idx] for tc_idx in target):
                public_score += parameter[0]
            headers += ["Subtask %d (%g)" % (st_idx + 1, parameter[0])]

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

        for st_idx, parameter in enumerate(self.parameters):
            target = targets[st_idx]

            testcases = []
            public_testcases = []
            previous_tc_all_correct = True
            for tc_idx in target:
                tc_outcome = self.get_public_outcome(
                    float(evaluations[tc_idx].outcome), parameter)

                testcases.append({
                    "idx": tc_idx,
                    "outcome": tc_outcome,
                    "text": evaluations[tc_idx].text,
                    "time": evaluations[tc_idx].execution_time,
                    "memory": evaluations[tc_idx].execution_memory,
                    "show_in_restricted_feedback": previous_tc_all_correct})
                if self.public_testcases[tc_idx]:
                    public_testcases.append(testcases[-1])
                    # Only block restricted feedback if this is the first
                    # *public* non-correct testcase, otherwise we might be
                    # leaking info on private testcases.
                    if tc_outcome != "Correct":
                        previous_tc_all_correct = False
                else:
                    public_testcases.append({"idx": tc_idx})

            st_score_fraction = self.reduce(
                [float(evaluations[tc_idx].outcome) for tc_idx in target],
                parameter)
            st_score = st_score_fraction * parameter[0]

            score += st_score
            subtasks.append({
                "idx": st_idx + 1,
                # We store the fraction so that an "example" testcase
                # with a max score of zero is still properly rendered as
                # correct or incorrect.
                "score_fraction": st_score_fraction,
                "max_score": parameter[0],
                "testcases": testcases})
            if all(self.public_testcases[tc_idx] for tc_idx in target):
                public_score += st_score
                public_subtasks.append(subtasks[-1])
            else:
                public_subtasks.append({"idx": st_idx + 1,
                                        "testcases": public_testcases})
            ranking_details.append("%g" % round(st_score, 2))

        return score, subtasks, public_score, public_subtasks, ranking_details

    @abstractmethod
    def get_public_outcome(self, unused_outcome, unused_parameter):
        """Return a public outcome from an outcome.

        The public outcome is shown to the user, and this method
        return the public outcome associated to the outcome of a
        submission in a testcase contained in the group identified by
        parameter.

        unused_outcome (float): the outcome of the submission in the
            testcase.
        unused_parameter (list): the parameters of the current group.

        return (str): the public output.

        """
        pass

    @abstractmethod
    def reduce(self, unused_outcomes, unused_parameter):
        """Return the score of a subtask given the outcomes.

        unused_outcomes ([float]): the outcomes of the submission in
            the testcases of the group.
        unused_parameter (list): the parameters of the group.

        return (float): the public output.

        """
        pass
