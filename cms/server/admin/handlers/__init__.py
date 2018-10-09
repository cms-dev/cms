#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

from .admin import \
    AddAdminHandler, \
    AdminsHandler, \
    AdminHandler
from .base import \
    FileFromDigestHandler, \
    SimpleHandler, \
    SimpleContestHandler
from .contest import \
    AddContestHandler, \
    ContestHandler, \
    OverviewHandler, \
    ResourcesListHandler, \
    ContestListHandler, \
    RemoveContestHandler
from .contestannouncement import \
    AddAnnouncementHandler, \
    AnnouncementHandler
from .contestquestion import \
    QuestionsHandler, \
    QuestionReplyHandler, \
    QuestionIgnoreHandler, \
    QuestionClaimHandler
from .contestranking import \
    RankingHandler
from .contestsubmission import \
    ContestSubmissionsHandler, \
    ContestUserTestsHandler
from .contesttask import \
    ContestTasksHandler, \
    AddContestTaskHandler
from .contestuser import \
    ContestUsersHandler, \
    RemoveParticipationHandler, \
    AddContestUserHandler, \
    ParticipationHandler, \
    MessageHandler
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
    DeleteTestcaseHandler, \
    DownloadTestcasesHandler
from .main import \
    LoginHandler, \
    LogoutHandler, \
    ResourcesHandler, \
    NotificationsHandler
from .submission import \
    SubmissionHandler, \
    SubmissionCommentHandler, \
    SubmissionOfficialStatusHandler, \
    SubmissionFileHandler
from .task import \
    AddTaskHandler, \
    TaskHandler, \
    AddDatasetHandler, \
    AddStatementHandler, \
    StatementHandler, \
    AddAttachmentHandler, \
    AttachmentHandler, \
    TaskListHandler, \
    RemoveTaskHandler
from .user import \
    AddUserHandler, \
    UserHandler, \
    UserListHandler, \
    RemoveUserHandler, \
    AddParticipationHandler, \
    EditParticipationHandler, \
    AddTeamHandler, \
    TeamHandler
from .usertest import \
    UserTestHandler, \
    UserTestFileHandler


HANDLERS = [
    (r"/", OverviewHandler),
    (r"/login", LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/resourceslist", ResourcesListHandler),
    (r"/resources", ResourcesHandler),
    (r"/resources/([0-9]+|all)", ResourcesHandler),
    (r"/resources/([0-9]+|all)/([0-9]+)", ResourcesHandler),
    (r"/notifications", NotificationsHandler),
    (r"/file/([a-f0-9]+)/([a-zA-Z0-9_.-]+)", FileFromDigestHandler),

    # Contest

    (r"/contests", ContestListHandler),
    (r"/contests/([0-9]+)/remove", RemoveContestHandler),
    (r"/contests/add", AddContestHandler),
    (r"/contest/([0-9]+)", ContestHandler),
    (r"/contest/([0-9]+)/overview", OverviewHandler),
    (r"/contest/([0-9]+)/resourceslist", ResourcesListHandler),

    # Contest's users

    (r"/contest/([0-9]+)/users", ContestUsersHandler),
    (r"/contest/([0-9]+)/users/add", AddContestUserHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/remove", RemoveParticipationHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/edit", ParticipationHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/message", MessageHandler),

    # Contest's tasks

    (r"/contest/([0-9]+)/tasks", ContestTasksHandler),
    (r"/contest/([0-9]+)/tasks/add", AddContestTaskHandler),

    # Contest's submissions / user tests

    (r"/contest/([0-9]+)/submissions", ContestSubmissionsHandler),
    (r"/contest/([0-9]+)/user_tests", ContestUserTestsHandler),

    # Contest's announcements

    (r"/contest/([0-9]+)/announcements",
     SimpleContestHandler("announcements.html")),
    (r"/contest/([0-9]+)/announcements/add", AddAnnouncementHandler),
    (r"/contest/([0-9]+)/announcement/([0-9]+)", AnnouncementHandler),

    # Contest's questions

    (r"/contest/([0-9]+)/questions", QuestionsHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/reply", QuestionReplyHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/ignore", QuestionIgnoreHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/claim", QuestionClaimHandler),

    # Contest's ranking

    (r"/contest/([0-9]+)/ranking", RankingHandler),
    (r"/contest/([0-9]+)/ranking/([a-z]+)", RankingHandler),

    # Tasks

    (r"/tasks", TaskListHandler),
    (r"/tasks/([0-9]+)/remove", RemoveTaskHandler),
    (r"/tasks/add", AddTaskHandler),
    (r"/task/([0-9]+)", TaskHandler),
    (r"/task/([0-9]+)/add_dataset", AddDatasetHandler),
    (r"/task/([0-9]+)/statements/add", AddStatementHandler),
    (r"/task/([0-9]+)/statement/([0-9]+)", StatementHandler),
    (r"/task/([0-9]+)/attachments/add", AddAttachmentHandler),
    (r"/task/([0-9]+)/attachment/([0-9]+)", AttachmentHandler),

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
    (r"/dataset/([0-9]+)/testcases/download", DownloadTestcasesHandler),

    # Users/Teams

    (r"/users", UserListHandler),
    (r"/users/([0-9]+)/remove", RemoveUserHandler),
    (r"/teams", SimpleHandler("teams.html")),
    (r"/users/add", AddUserHandler),
    (r"/teams/add", AddTeamHandler),
    (r"/user/([0-9]+)", UserHandler),
    (r"/team/([0-9]+)", TeamHandler),
    (r"/user/([0-9]+)/add_participation", AddParticipationHandler),
    (r"/user/([0-9]+)/edit_participation", EditParticipationHandler),

    # Admins

    (r"/admins", AdminsHandler),
    (r"/admins/add", AddAdminHandler),
    (r"/admin/([0-9]+)", AdminHandler),

    # Submissions

    (r"/submission/([0-9]+)(?:/([0-9]+))?", SubmissionHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?/comment", SubmissionCommentHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?/official",
     SubmissionOfficialStatusHandler),
    (r"/submission_file/([0-9]+)", SubmissionFileHandler),

    # User tests

    (r"/user_test/([0-9]+)(?:/([0-9]+))?", UserTestHandler),
    (r"/user_test_file/([0-9]+)", UserTestFileHandler),

    # The following prefixes are handled by WSGI middlewares:
    # * /rpc, defined in cms/io/web_service.py
    # * /static, defined in cms/io/web_service.py
]


__all__ = ["HANDLERS"]
