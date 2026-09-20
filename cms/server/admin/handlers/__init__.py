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
    AdminHandler, \
    AdminThemeHandler
from .base import (
    FileFromDigestHandler,
    PictureHandler,
    SimpleHandler,
    SimpleContestHandler,
)
from .contest import \
    AddContestHandler, \
    ContestHandler, \
    OverviewHandler, \
    ContestListHandler, \
    RemoveContestHandler
from .contestannouncement import \
    AddAnnouncementHandler, \
    AnnouncementHandler, \
    ContestAnnouncementsHandler, \
    EditAnnouncementHandler
from .contestquestion import \
    QuestionsHandler, \
    QuestionReplyHandler, \
    QuestionIgnoreHandler, \
    QuestionClaimHandler
from .contestdelayrequest import \
    DelaysAndExtraTimesHandler, \
    DelayRequestApproveHandler, \
    DelayRequestRejectHandler, \
    RemoveDelayAndExtraTimeHandler, \
    ExportDelaysAndExtraTimesHandler, \
    RemoveAllDelaysAndExtraTimesHandler, \
    EraseAllStartTimesHandler, \
    ResetAllIPAddressesHandler, \
    AdminConfiguredDelayHandler
from .contestranking import \
    RankingHandler, \
    ScoreHistoryHandler, \
    ParticipationDetailHandler, \
    ParticipationSubmissionsHandler
from .contestsubmission import \
    ContestSubmissionsHandler, \
    ContestUserTestsHandler
from .contesttask import \
    ContestTasksHandler, \
    AddContestTaskHandler, \
    TaskVisibilityHandler
from .contestuser import \
    ContestUsersHandler, \
    RemoveParticipationHandler, \
    AddContestUserHandler, \
    BulkAddContestUsersHandler, \
    ParticipationHandler, \
    MessageHandler, \
    EditMessageHandler, \
    DeleteMessageHandler
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
    DeleteSelectedTestcasesHandler, \
    DownloadTestcasesHandler, \
    AddGeneratorHandler, \
    EditGeneratorHandler, \
    DeleteGeneratorHandler, \
    GenerateTestcasesHandler, \
    RenameTestcaseHandler, \
    BatchRenameTestcasesHandler, \
    ApplySubtaskPrefixesHandler
from .subtask_validators import (
    AddSubtaskValidatorHandler,
    DeleteSubtaskValidatorHandler,
    SubtaskDetailsHandler,
    UpdateSubtaskRegexHandler,
    UpdateSubtaskNameHandler,
    ReorderSubtasksHandler,
    RerunSubtaskValidatorsHandler,
)
from .main import (
    LoginHandler,
    LogoutHandler,
    ResourcesHandler,
    NotificationsHandler,
    FileCacherStatsHandler,
    FileCacherDeleteOrphansHandler,
    FileCacherSearchHandler,
    FileCacherListByDescriptionHandler,
    FileCacherDownloadHandler,
    MarkdownRenderHandler,
)
from .submission import \
    SubmissionHandler, \
    SubmissionCommentHandler, \
    SubmissionOfficialStatusHandler, \
    SubmissionFileHandler, \
    SubmissionDiffHandler
from .submissiondownload import \
    DownloadTaskSubmissionsHandler, \
    DownloadUserContestSubmissionsHandler, \
    DownloadContestSubmissionsHandler, \
    DownloadTrainingProgramSubmissionsHandler, \
    DownloadTrainingProgramStudentSubmissionsHandler
from .task import (
    AddTaskHandler,
    TaskHandler,
    AddDatasetHandler,
    AddStatementHandler,
    StatementHandler,
    AddAttachmentHandler,
    AttachmentHandler,
    TaskListHandler,
    RemoveTaskHandler,
    DefaultSubmissionFormatHandler,
)
from .import_handlers import (
    ImportTaskHandler,
    ImportContestHandler,
)
from .user import \
    AddUserHandler, \
    UserHandler, \
    UserListHandler, \
    ExportUsersHandler, \
    ImportUsersHandler, \
    ImportUsersConfirmHandler, \
    RemoveUserHandler, \
    AddParticipationHandler, \
    EditParticipationHandler, \
    AddTeamHandler, \
    TeamHandler, \
    TeamListHandler, \
    RemoveTeamHandler, \
    ClearResetTokenHandler, \
    ApprovePasswordResetHandler, \
    DenyPasswordResetHandler, \
    RemovePictureHandler, \
    NewSchoolYearHandler
from .usertest import \
    UserTestHandler, \
    UserTestFileHandler
from .modelsolution import \
    AddModelSolutionHandler, \
    ModelSolutionHandler, \
    EditModelSolutionHandler, \
    DeleteModelSolutionHandler, \
    ReplaceModelSolutionHandler, \
    ConfigureImportedModelSolutionsHandler
from .folder import \
    FolderListHandler, \
    FolderHandler, \
    AddFolderHandler, \
    RemoveFolderHandler
from .export_handlers import \
    ExportTaskHandler, \
    ExportContestHandler
from .trainingprogram import \
    TrainingProgramListHandler, \
    TrainingProgramHandler, \
    AddTrainingProgramHandler, \
    RemoveTrainingProgramHandler, \
    TrainingProgramTasksHandler, \
    AddTrainingProgramTaskHandler, \
    RemoveTrainingProgramTaskHandler, \
    TrainingProgramRankingHandler
from .trainingday import \
    TrainingProgramTrainingDaysHandler, \
    AddTrainingDayHandler, \
    RemoveTrainingDayHandler, \
    AddTrainingDayGroupHandler, \
    UpdateTrainingDayGroupsHandler, \
    RemoveTrainingDayGroupHandler, \
    TrainingDayTypesHandler, \
    UpdateArchivedTrainingDayDescriptionHandler, \
    ScoreboardSharingHandler
from .student import \
    TrainingProgramStudentsHandler, \
    AddTrainingProgramStudentHandler, \
    BulkAddTrainingProgramStudentsHandler, \
    RemoveTrainingProgramStudentHandler, \
    StudentHandler, \
    StudentTagsHandler, \
    StudentTasksHandler, \
    StudentTaskSubmissionsHandler, \
    AddStudentTaskHandler, \
    RemoveStudentTaskHandler, \
    BulkAssignTaskHandler
from .archive import \
    ArchiveTrainingDayHandler, \
    TrainingProgramAttendanceHandler, \
    TrainingProgramCombinedRankingHandler, \
    TrainingProgramCombinedRankingHistoryHandler, \
    TrainingProgramCombinedRankingDetailHandler, \
    UpdateAttendanceHandler, \
    ExportAttendanceHandler, \
    ExportCombinedRankingHandler, \
    ExportAnalysedRankingHandler, \
    ExportArchivedTaskScoresHandler
from .import_contest_as_td import \
    ImportContestAsTrainingDayHandler
from .import_td_from_csv import \
    ImportTrainingDayFromCsvHandler


HANDLERS = [
    (r"/", OverviewHandler),
    (r"/login", LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/resources", ResourcesHandler),
    (r"/resources/([0-9]+|all)", ResourcesHandler),
    (r"/resources/([0-9]+|all)/([0-9]+)", ResourcesHandler),
    (r"/notifications", NotificationsHandler),
    (r"/filecacher/stats", FileCacherStatsHandler),
    (r"/filecacher/delete_orphans", FileCacherDeleteOrphansHandler),
    (r"/filecacher/search", FileCacherSearchHandler),
    (r"/filecacher/list_by_description", FileCacherListByDescriptionHandler),
    (r"/filecacher/download", FileCacherDownloadHandler),
    (r"/file/([a-f0-9]+)/([a-zA-Z0-9_.-]+)", FileFromDigestHandler),
    (r"/picture/([a-f0-9]+)", PictureHandler),
    (r"/render_markdown", MarkdownRenderHandler),
    # Contest
    (r"/contests", ContestListHandler),
    (r"/contests/([0-9]+)/remove", RemoveContestHandler),
    (r"/contests/add", AddContestHandler),
    (r"/contests/import", ImportContestHandler),
    (r"/contest/([0-9]+)", ContestHandler),
    (r"/(contest|training_program)/([0-9]+)/export", ExportContestHandler),
    (r"/(contest|training_program)/([0-9]+)/overview", OverviewHandler),
    # Contest's users
    (r"/contest/([0-9]+)/users", ContestUsersHandler),
    (r"/contest/([0-9]+)/users/add", AddContestUserHandler),
    (r"/contest/([0-9]+)/users/bulk_add", BulkAddContestUsersHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/remove", RemoveParticipationHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/edit", ParticipationHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/message", MessageHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/message/([0-9]+)/edit", EditMessageHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/message/([0-9]+)", DeleteMessageHandler),
    # Contest's tasks
    (r"/contest/([0-9]+)/tasks", ContestTasksHandler),
    (r"/contest/([0-9]+)/tasks/add", AddContestTaskHandler),
    (r"/contest/([0-9]+)/task_visibility/([0-9]+)", TaskVisibilityHandler),
    # Contest's submissions / user tests
    (r"/(contest|training_program)/([0-9]+)/submissions", ContestSubmissionsHandler),
    (r"/contest/([0-9]+)/submissions/download", DownloadContestSubmissionsHandler),
    (
        r"/contest/([0-9]+)/user/([0-9]+)/submissions/download",
        DownloadUserContestSubmissionsHandler,
    ),
    (r"/contest/([0-9]+)/user_tests", ContestUserTestsHandler),
    # Contest's announcements
    (
        r"/(contest|training_program)/([0-9]+)/announcements",
        ContestAnnouncementsHandler,
    ),
    (r"/contest/([0-9]+)/announcements/add", AddAnnouncementHandler),
    (r"/contest/([0-9]+)/announcements/edit/([0-9]+)", EditAnnouncementHandler),
    (
        r"/(contest|training_program)/([0-9]+)/announcement/([0-9]+)",
        AnnouncementHandler,
    ),
    # Contest's questions
    (r"/(contest|training_program)/([0-9]+)/questions", QuestionsHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/reply", QuestionReplyHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/ignore", QuestionIgnoreHandler),
    (r"/contest/([0-9]+)/question/([0-9]+)/claim", QuestionClaimHandler),
    # Contest's delay requests and extra times
    (r"/contest/([0-9]+)/delays_and_extra_times", DelaysAndExtraTimesHandler),
    (
        r"/contest/([0-9]+)/delays_and_extra_times/export",
        ExportDelaysAndExtraTimesHandler,
    ),
    (
        r"/contest/([0-9]+)/delays_and_extra_times/remove_all",
        RemoveAllDelaysAndExtraTimesHandler,
    ),
    (
        r"/contest/([0-9]+)/delays_and_extra_times/erase_start_times",
        EraseAllStartTimesHandler,
    ),
    (
        r"/contest/([0-9]+)/delays_and_extra_times/reset_ip_addresses",
        ResetAllIPAddressesHandler,
    ),
    (
        r"/contest/([0-9]+)/delays_and_extra_times/admin_configure",
        AdminConfiguredDelayHandler,
    ),
    (r"/contest/([0-9]+)/delay_request/([0-9]+)/approve", DelayRequestApproveHandler),
    (r"/contest/([0-9]+)/delay_request/([0-9]+)/reject", DelayRequestRejectHandler),
    (
        r"/contest/([0-9]+)/participation/([0-9]+)/remove_delay_and_extra_time",
        RemoveDelayAndExtraTimeHandler,
    ),
    # Contest's ranking
    (r"/contest/([0-9]+)/ranking", RankingHandler),
    (r"/contest/([0-9]+)/ranking/history", ScoreHistoryHandler),
    (r"/contest/([0-9]+)/ranking/([a-z]+)", RankingHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/detail", ParticipationDetailHandler),
    (r"/contest/([0-9]+)/user/([0-9]+)/submissions", ParticipationSubmissionsHandler),
    # Tasks
    (r"/tasks", TaskListHandler),
    (r"/tasks/([0-9]+)/remove", RemoveTaskHandler),
    (r"/tasks/add", AddTaskHandler),
    (r"/tasks/import", ImportTaskHandler),
    (r"/task/([0-9]+)", TaskHandler),
    (r"/task/([0-9]+)/export", ExportTaskHandler),
    (r"/task/([0-9]+)/submissions/download", DownloadTaskSubmissionsHandler),
    (r"/task/([0-9]+)/add_dataset", AddDatasetHandler),
    (r"/task/([0-9]+)/statements/add", AddStatementHandler),
    (r"/task/([0-9]+)/statement/([0-9]+)", StatementHandler),
    (r"/task/([0-9]+)/attachments/add", AddAttachmentHandler),
    (r"/task/([0-9]+)/attachment/([0-9]+)", AttachmentHandler),
    (r"/task/([0-9]+)/default_submission_format", DefaultSubmissionFormatHandler),
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
    (r"/dataset/([0-9]+)/testcases/delete_selected", DeleteSelectedTestcasesHandler),
    (r"/dataset/([0-9]+)/testcases/download", DownloadTestcasesHandler),
    (r"/dataset/([0-9]+)/generators/add", AddGeneratorHandler),
    (r"/dataset/([0-9]+)/generator/([0-9]+)/edit", EditGeneratorHandler),
    (r"/dataset/([0-9]+)/generator/([0-9]+)/delete", DeleteGeneratorHandler),
    (r"/dataset/([0-9]+)/generator/([0-9]+)/generate", GenerateTestcasesHandler),
    # Subtask validators
    (r"/dataset/([0-9]+)/subtask/([0-9]+)/validator/add", AddSubtaskValidatorHandler),
    (r"/dataset/([0-9]+)/validator/([0-9]+)/delete", DeleteSubtaskValidatorHandler),
    (r"/dataset/([0-9]+)/subtask/([0-9]+)/details", SubtaskDetailsHandler),
    (r"/dataset/([0-9]+)/subtask/([0-9]+)/regex", UpdateSubtaskRegexHandler),
    (r"/dataset/([0-9]+)/subtask/([0-9]+)/name", UpdateSubtaskNameHandler),
    (r"/dataset/([0-9]+)/testcase/([0-9]+)/rename", RenameTestcaseHandler),
    (r"/dataset/([0-9]+)/testcases/batch_rename", BatchRenameTestcasesHandler),
    (
        r"/dataset/([0-9]+)/testcases/apply_subtask_prefixes",
        ApplySubtaskPrefixesHandler,
    ),
    (r"/dataset/([0-9]+)/subtasks/reorder", ReorderSubtasksHandler),
    (r"/dataset/([0-9]+)/validators/rerun", RerunSubtaskValidatorsHandler),
    # Users/Teams
    (r"/users", UserListHandler),
    (r"/users/export", ExportUsersHandler),
    (r"/users/import", ImportUsersHandler),
    (r"/users/import/confirm", ImportUsersConfirmHandler),
    (r"/users/new_school_year", NewSchoolYearHandler),
    (r"/users/([0-9]+)/remove", RemoveUserHandler),
    (r"/teams", TeamListHandler),
    (r"/teams/([0-9]+)/remove", RemoveTeamHandler),
    (r"/users/add", AddUserHandler),
    (r"/teams/add", AddTeamHandler),
    (r"/user/([0-9]+)", UserHandler),
    (r"/team/([0-9]+)", TeamHandler),
    (r"/user/([0-9]+)/add_participation", AddParticipationHandler),
    (r"/user/([0-9]+)/edit_participation", EditParticipationHandler),
    (r"/user/([0-9]+)/clear_reset_token", ClearResetTokenHandler),
    (r"/user/([0-9]+)/approve_password_reset", ApprovePasswordResetHandler),
    (r"/user/([0-9]+)/deny_password_reset", DenyPasswordResetHandler),
    (r"/user/([0-9]+)/remove_picture", RemovePictureHandler),
    # Folders
    (r"/folders", FolderListHandler),
    (r"/folders/([0-9]+)/remove", RemoveFolderHandler),
    (r"/folders/add", AddFolderHandler),
    (r"/folder/([0-9]+)", FolderHandler),
    # Training Programs
    (r"/training_programs", TrainingProgramListHandler),
    (r"/training_programs/([0-9]+)/remove", RemoveTrainingProgramHandler),
    (r"/training_programs/add", AddTrainingProgramHandler),
    (r"/training_program/([0-9]+)", TrainingProgramHandler),
    # Training Program tabs
    (r"/training_program/([0-9]+)/students", TrainingProgramStudentsHandler),
    (r"/training_program/([0-9]+)/students/add", AddTrainingProgramStudentHandler),
    (
        r"/training_program/([0-9]+)/students/bulk_add",
        BulkAddTrainingProgramStudentsHandler,
    ),
    (
        r"/training_program/([0-9]+)/student/([0-9]+)/remove",
        RemoveTrainingProgramStudentHandler,
    ),
    (r"/training_program/([0-9]+)/student/([0-9]+)/edit", StudentHandler),
    (r"/training_program/([0-9]+)/student/([0-9]+)/tags", StudentTagsHandler),
    (r"/training_program/([0-9]+)/student/([0-9]+)/tasks", StudentTasksHandler),
    (r"/training_program/([0-9]+)/student/([0-9]+)/tasks/add", AddStudentTaskHandler),
    (
        r"/training_program/([0-9]+)/student/([0-9]+)/task/([0-9]+)/remove",
        RemoveStudentTaskHandler,
    ),
    (
        r"/training_program/([0-9]+)/student/([0-9]+)/task/([0-9]+)/submissions",
        StudentTaskSubmissionsHandler,
    ),
    (r"/training_program/([0-9]+)/bulk_assign_task", BulkAssignTaskHandler),
    (r"/training_program/([0-9]+)/tasks", TrainingProgramTasksHandler),
    (r"/training_program/([0-9]+)/tasks/add", AddTrainingProgramTaskHandler),
    (
        r"/training_program/([0-9]+)/task/([0-9]+)/remove",
        RemoveTrainingProgramTaskHandler,
    ),
    (r"/training_program/([0-9]+)/ranking", TrainingProgramRankingHandler),
    (r"/training_program/([0-9]+)/ranking/([a-z]+)", TrainingProgramRankingHandler),
    (
        r"/training_program/([0-9]+)/submissions/download",
        DownloadTrainingProgramSubmissionsHandler,
    ),
    (
        r"/training_program/([0-9]+)/student/([0-9]+)/submissions/download",
        DownloadTrainingProgramStudentSubmissionsHandler,
    ),
    (r"/training_program/([0-9]+)/training_days", TrainingProgramTrainingDaysHandler),
    (r"/training_program/([0-9]+)/training_days/add", AddTrainingDayHandler),
    (
        r"/training_program/([0-9]+)/training_day/([0-9]+)/remove",
        RemoveTrainingDayHandler,
    ),
    (
        r"/training_program/([0-9]+)/training_day/([0-9]+)/types",
        TrainingDayTypesHandler,
    ),
    (
        r"/training_program/([0-9]+)/training_day/([0-9]+)/description",
        UpdateArchivedTrainingDayDescriptionHandler,
    ),
    (
        r"/training_program/([0-9]+)/training_day/([0-9]+)/scoreboard_sharing",
        ScoreboardSharingHandler,
    ),
    (
        r"/training_program/([0-9]+)/training_day/([0-9]+)/archive",
        ArchiveTrainingDayHandler,
    ),
    (
        r"/training_program/([0-9]+)/import_contest_as_training_day",
        ImportContestAsTrainingDayHandler,
    ),
    (
        r"/training_program/([0-9]+)/training_days/export_task_scores",
        ExportArchivedTaskScoresHandler,
    ),
    (r"/training_program/([0-9]+)/attendance", TrainingProgramAttendanceHandler),
    (r"/training_program/([0-9]+)/attendance/export", ExportAttendanceHandler),
    (r"/training_program/([0-9]+)/attendance/([0-9]+)", UpdateAttendanceHandler),
    (
        r"/training_program/([0-9]+)/import_training_day_from_csv",
        ImportTrainingDayFromCsvHandler,
    ),
    (
        r"/training_program/([0-9]+)/combined_ranking",
        TrainingProgramCombinedRankingHandler,
    ),
    (
        r"/training_program/([0-9]+)/combined_ranking/export",
        ExportCombinedRankingHandler,
    ),
    (
        r"/training_program/([0-9]+)/combined_ranking/export_analysed",
        ExportAnalysedRankingHandler,
    ),
    (
        r"/training_program/([0-9]+)/combined_ranking/history",
        TrainingProgramCombinedRankingHistoryHandler,
    ),
    (
        r"/training_program/([0-9]+)/student/([0-9]+)/combined_ranking_detail",
        TrainingProgramCombinedRankingDetailHandler,
    ),
    # Training day groups (main groups configuration on contest page)
    (r"/contest/([0-9]+)/training_day_group/add", AddTrainingDayGroupHandler),
    (r"/contest/([0-9]+)/training_day_groups/update", UpdateTrainingDayGroupsHandler),
    (
        r"/contest/([0-9]+)/training_day_group/([0-9]+)/remove",
        RemoveTrainingDayGroupHandler,
    ),
    # Admins
    (r"/admins", AdminsHandler),
    (r"/admins/add", AddAdminHandler),
    (r"/admin/([0-9]+)", AdminHandler),
    (r"/admin/theme", AdminThemeHandler),
    # Submissions
    (r"/submission/([0-9]+)(?:/([0-9]+))?", SubmissionHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?/comment", SubmissionCommentHandler),
    (r"/submission/([0-9]+)(?:/([0-9]+))?/official", SubmissionOfficialStatusHandler),
    (r"/submission_file/([0-9]+)", SubmissionFileHandler),
    (r"/submission_diff/([0-9]+)/([0-9]+)", SubmissionDiffHandler),
    # User tests
    (r"/user_test/([0-9]+)(?:/([0-9]+))?", UserTestHandler),
    (r"/user_test_file/([0-9]+)", UserTestFileHandler),
    # Model Solutions
    (r"/dataset/([0-9]+)/model_solutions/add", AddModelSolutionHandler),
    (r"/model_solution/([0-9]+)(?:/([0-9]+))?", ModelSolutionHandler),
    (r"/model_solution/([0-9]+)/edit", EditModelSolutionHandler),
    (r"/model_solution/([0-9]+)/delete", DeleteModelSolutionHandler),
    (r"/model_solution/([0-9]+)/replace", ReplaceModelSolutionHandler),
    (
        r"/task/([0-9]+)/model_solutions/configure",
        ConfigureImportedModelSolutionsHandler,
    ),
    # The following prefixes are handled by WSGI middlewares:
    # * /rpc, defined in cms/io/web_service.py
    # * /static, defined in cms/io/web_service.py
]


__all__ = ["HANDLERS"]
