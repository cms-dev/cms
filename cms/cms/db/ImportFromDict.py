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

"""Class methods import_from_dict for all SQLALchemy classes.

"""

from cms.db.Contest import Contest, Announcement
from cms.db.View import RankingView, Score
from cms.db.User import User, Message, Question
from cms.db.Task import Task, Manager, Testcase, Attachment, \
     PublicTestcase, SubmissionFormatElement
from cms.db.Submission import Submission, Token, Evaluation, File, Executable


@classmethod
def basic_import_from_dict(cls, data):
    """Build the object using data from a dictionary.

    """
    return cls(**data)
for cls in [Announcement, Score, Question, Message, SubmissionFormatElement,
            PublicTestcase, Manager, Attachment, Testcase, Evaluation,
            File, Executable, Token]:
    cls.import_from_dict = basic_import_from_dict

@classmethod
def contest_import_from_dict(cls, data):
    """Build the object using data from a dictionary.

    """
    data['tasks'] = [Task.import_from_dict(task_data) for task_data in data['tasks']]
    data['users'] = [User.import_from_dict(user_data) for user_data in data['users']]
    data['announcements'] = [Announcement.import_from_dict(ann_data) for ann_data in data['announcements']]
    data['ranking_view'] = RankingView.import_from_dict(data['ranking_view'])
    return cls(**data)
Contest.import_from_dict = contest_import_from_dict

@classmethod
def rankingview_import_from_dict(cls, data):
    data['scores'] = [Score.import_from_dict(score_data) for score_data in data['scores']]
    data['scores'] = dict([(Score.rankingview_keyfunc(score), score) for score in data['scores']])
    return cls(**data)
RankingView.import_from_dict = rankingview_import_from_dict

@classmethod
def user_import_from_dict(cls, data):
    data['messages'] = [Message.import_from_dict(message_data) for message_data in data['messages']]
    data['questions'] = [Question.import_from_dict(question_data) for question_data in data['questions']]
    data['submissions'] = [Submission.import_from_dict(submission_data) for submission_data in data['submissions']]
    return cls(**data)
User.import_from_dict = user_import_from_dict

@classmethod
def task_import_from_dict(cls, data):
    data['attachments'] = [Attachment.import_from_dict(attch_data) for attch_data in data['attachments']]
    data['attachments'] = dict([(attachment.filename, attachment) for attachment in data['attachments']])
    data['submission_format'] = [SubmissionFormatElement.import_from_dict(sfe_data) for sfe_data in data['submission_format']]
    data['managers'] = [Manager.import_from_dict(manager_data) for manager_data in data['managers']]
    data['managers'] = dict([(manager.filename, manager) for manager in data['managers']])
    data['testcases'] = [Testcase.import_from_dict(testcase_data) for testcase_data in data['testcases']]
    data['public_testcases'] = [PublicTestcase.import_from_dict(testcase_data) for testcase_data in data['public_testcases']]
    return cls(**data)
Task.import_from_dict = task_import_from_dict

@classmethod
def submission_import_from_dict(cls, data):
    data['files'] = [File.import_from_dict(file_data) for file_data in data['files']]
    data['files'] = dict([(file.filename, file) for file in data['files']])
    data['executables'] = [Executable.import_from_dict(executable_data) for executable_data in data['executables']]
    data['executables'] = dict([(executable.filename, executable) for executable in data['executables']])
    data['evaluations'] = [Evaluation.import_from_dict(eval_data) for eval_data in data['evaluations']]
    if data['token_timestamp'] is not None:
        data['token_timestamp'] = Token.import_from_dict(data['token_timestamp'])
    return cls(**data)
Submission.import_from_dict = submission_import_from_dict
