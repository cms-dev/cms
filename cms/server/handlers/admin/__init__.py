#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from .base import \
    SimpleHandler, \
    SimpleContestHandler, \
    ResourcesHandler, \
    NotificationsHandler
from .contest import \
    AddContestHandler, \
    ContestHandler, \
    MainHandler, \
    ResourcesListHandler
from .contestuser import \
    ContestUserlistHandler, \
    AssignContestUserHandler, \
    EditContestUserHandler, \
    ParticipationHandler, \
    MessageHandler
from .contesttask import \
    ContestTasklistHandler, \
    AssignContestTaskHandler, \
    EditContestTaskHandler
from .contestsubmission import \
    ContestSubmissionsHandler
from .contestannouncement import \
    AddAnnouncementHandler, \
    RemoveAnnouncementHandler
from .contestquestion import \
    QuestionsHandler, \
    QuestionReplyHandler, \
    QuestionIgnoreHandler
from .contestranking import \
    RankingHandler
from .task import \
    AddTaskHandler, \
    TaskHandler, \
    AddDatasetHandler, \
    AddStatementHandler, \
    DeleteStatementHandler, \
    AddAttachmentHandler, \
    DeleteAttachmentHandler
from .dataset import \
    DatasetSubmissionsHandler, \
    CloneDatasetHandler, \
    RenameDatasetHandler, \
    DeleteDatasetHandler, \
    ActivateDatasetHandler, \
    ToggleAutojudgeDatasetHandler, \
    AddManagerHandler, \
    DeleteManagerHandler, \
    AddTestcaseHandler, \
    AddTestcasesHandler, \
    DeleteTestcaseHandler
from .user import \
    AddUserHandler, \
    UserViewHandler, \
    AssignUserContestHandler, \
    EditUserContestHandler
from .submission import \
    SubmissionViewHandler, \
    SubmissionCommentHandler, \
    SubmissionFileHandler, \
    FileFromDigestHandler


HANDLERS = [
    (r"/", MainHandler),
    (r"/resourceslist", ResourcesListHandler),
    (r"/resources", ResourcesHandler),
    (r"/resources/([0-9]+|all)", ResourcesHandler),
    (r"/resources/([0-9]+|all)/([0-9]+)", ResourcesHandler),
    (r"/notifications", NotificationsHandler),

    # Contest

    (r"/contests", SimpleHandler("contestlist.html")),
    (r"/contests/new", AddContestHandler),
    (r"/contest/([0-9]+)", ContestHandler),
    (r"/contest/([0-9]+)/overview", MainHandler),
    (r"/contest/([0-9]+)/resourceslist", ResourcesListHandler),

    # Contest's users

    (r"/contest/([0-9]+)/users", ContestUserlistHandler),
    (r"/contest/([0-9]+)/users/add", AssignContestUserHandler),
    (r"/contest/([0-9]+)/users/edit", EditContestUserHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)", ParticipationHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/message", MessageHandler),

    # Contest's tasks

    (r"/contest/([0-9]+)/tasks", ContestTasklistHandler),
    (r"/contest/([0-9]+)/tasks/add", AssignContestTaskHandler),
    (r"/contest/([0-9]+)/tasks/edit", EditContestTaskHandler),

    # Contest's submissions

    (r"/contest/([0-9]+)/submissions", ContestSubmissionsHandler),

    # Contest's announcements

    (r"/contest/([0-9]+)/announcements",
     SimpleContestHandler("announcements.html")),
    (r"/contest/([0-9]+)/announcements/new", AddAnnouncementHandler),
    (r"/contest/([0-9]+)/announcement/([0-9]+)/delete",
     RemoveAnnouncementHandler),

    # Contest's questions

    (r"/contest/([0-9]+)/questions", QuestionsHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/reply", QuestionReplyHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/ignore", QuestionIgnoreHandler),

    # Contest's ranking

    (r"/contest/([0-9]+)/ranking", RankingHandler),
    (r"/contest/([0-9]+)/ranking/([a-z]+)", RankingHandler),

    # Tasks

    (r"/tasks", SimpleHandler("tasklist.html")),
    (r"/tasks/new", AddTaskHandler),
    (r"/task/([0-9]+)", TaskHandler),
    (r"/task/([0-9]+)/new_dataset", AddDatasetHandler),
    (r"/task/([0-9]+)/statements/add", AddStatementHandler),
    (r"/task/([0-9]+)/statement/([0-9]+)/delete", DeleteStatementHandler),
    (r"/task/([0-9]+)/attachments/add", AddAttachmentHandler),
    (r"/task/([0-9]+)/attachment/([0-9]+)/delete", DeleteAttachmentHandler),

    # Datasets

    (r"/dataset/([0-9]+)", DatasetSubmissionsHandler),
    (r"/dataset/([0-9]+)/clone", CloneDatasetHandler),
    (r"/dataset/([0-9]+)/rename", RenameDatasetHandler),
    (r"/dataset/([0-9]+)/delete", DeleteDatasetHandler),
    (r"/dataset/([0-9]+)/activate", ActivateDatasetHandler),
    (r"/dataset/([0-9]+)/autojudge", ToggleAutojudgeDatasetHandler),
    (r"/dataset/([0-9]+)/managers/add", AddManagerHandler),
    (r"/dataset/([0-9]+)/manager/([0-9]+)/delete", DeleteManagerHandler),
    (r"/dataset/([0-9]+)/testcases/add", AddTestcaseHandler),
    (r"/dataset/([0-9]+)/testcases/add_multiple", AddTestcasesHandler),
    (r"/dataset/([0-9]+)/testcase/([0-9]+)/delete", DeleteTestcaseHandler),

    # Users

    (r"/users", SimpleHandler("userlist.html")),
    (r"/users/new", AddUserHandler),
    (r"/user/([0-9]+)", UserViewHandler),
    (r"/user/([0-9]+)/add_participation", AssignUserContestHandler),
    (r"/user/([0-9]+)/edit_participation", EditUserContestHandler),

    # Submissions

    (r"/submission/([0-9]+)(?:/([0-9]+))?", SubmissionViewHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?/comment", SubmissionCommentHandler),
    (r"/submission_file/([0-9]+)", SubmissionFileHandler),
    (r"/file/([a-f0-9]+)/([a-zA-Z0-9_.-]+)", FileFromDigestHandler),
]


__all__ = [HANDLERS]
