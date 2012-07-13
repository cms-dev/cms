#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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
from cms.db.User import User, Message, Question
from cms.db.Task import Task
from cms.db.Submission import Submission


@classmethod
def contest_import_from_dict(cls, data):
    """Build the object using data from a dictionary.

    """
    data['tasks'] = [Task.import_from_dict(task_data)
                     for task_data in data['tasks']]
    tasks_by_name = dict(map(lambda x: (x.name, x), data['tasks']))
    data['users'] = [User.import_from_dict(user_data,
                                           tasks_by_name=tasks_by_name)
                     for user_data in data['users']]
    data['announcements'] = [Announcement.import_from_dict(ann_data)
                             for ann_data in data['announcements']]
    return cls(**data)


@classmethod
def user_import_from_dict(cls, data, tasks_by_name):
    """Build the object using data from a dictionary.

    """
    data['messages'] = [Message.import_from_dict(message_data)
                        for message_data in data['messages']]
    data['questions'] = [Question.import_from_dict(question_data)
                         for question_data in data['questions']]
    data['submissions'] = [Submission.import_from_dict(
        submission_data, tasks_by_name=tasks_by_name)
                           for submission_data in data['submissions']]
    obj = cls(**data)
    for submission in obj.submissions:
        submission.user = obj
    return obj


Contest.import_from_dict = contest_import_from_dict
User.import_from_dict = user_import_from_dict
