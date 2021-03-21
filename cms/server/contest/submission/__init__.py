#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Package containing utilities for accepting submissions in CWS.

Some of the functions use a common "format" to represent the files sent
by the contestants as part of a submission or user test: it is a list of
ReceivedFile objects, each with an optional codename, optional filename
and content. The list is intended to represent a multiset, hence order
is irrelevant and duplicates are allowed.

"""

from .check import get_submission_count, check_max_number, \
    get_latest_submission, check_min_interval, is_last_minutes
from .file_matching import InvalidFilesOrLanguage, match_files_and_language
from .file_retrieval import ReceivedFile, InvalidArchive, \
    extract_files_from_archive, extract_files_from_tornado
from .utils import fetch_file_digests_from_previous_submission, StorageFailed, \
    store_local_copy
from .workflow import UnacceptableSubmission, accept_submission, \
    TestingNotAllowed, UnacceptableUserTest, accept_user_test


__all__ = [
    # check.py
    "get_submission_count", "check_max_number", "get_latest_submission",
    "check_min_interval", "is_last_minutes",
    # file_retrieval.py
    "ReceivedFile", "InvalidArchive", "extract_files_from_archive",
    "extract_files_from_tornado",
    # file_matching.py
    "InvalidFilesOrLanguage", "match_files_and_language",
    # utils.py
    "fetch_file_digests_from_previous_submission", "StorageFailed",
    "store_local_copy",
    # workflow.py
    "UnacceptableSubmission", "accept_submission", "TestingNotAllowed",
    "UnacceptableUserTest", "accept_user_test",
]
