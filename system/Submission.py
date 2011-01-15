#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

import time

import Utils
from CouchObject import CouchObject

class Submission(CouchObject):

    _to_copy = ["timestamp", "files", "compilation_outcome", "evaluation_outcome",
                "executables",
                "compilation_text", "evaluation_text",
                "compilation_tentatives", "evaluation_tentatives",
                "score", "token_timestamp"]
    _to_copy_id = ["user", "task"]

    LANGUAGES = ["c", "cpp", "pas"]

    def __init__(self, user, task, timestamp, files,
                 compilation_outcome = None, evaluation_outcome = None,
                 executables = None,
                 compilation_text = None, evaluation_text = None,
                 compilation_tentatives = 0, evaluation_tentatives = 0,
                 score = None, token_timestamp = None,
                 couch_id = None, couch_rev = None):
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.compilation_outcome = compilation_outcome
        self.evaluation_outcome = evaluation_outcome
        self.executables = executables
        self.compilation_text = compilation_text
        self.evaluation_text = evaluation_text
        self.compilation_tentatives = compilation_tentatives
        self.evaluation_tentatives = evaluation_tentatives
        self.token_timestamp = token_timestamp
        self.score = score
        CouchObject.__init__(self, "submission", couch_id, couch_rev)

    def tokened(self):
        return self.token_timestamp != None

    def invalid(self):
        self.compilation_outcome = None
        self.evaluation_outcome = None
        self.compilation_text = None
        self.evaluation_text = None
        self.score = None
        self.executables = None
        self.to_couch()

    def choose_couch_id_basename(self):
        return "submission-%s-%s" % (self.user.username, self.task.name)

    def verify_source(self):
        if len(self.files) != len(self.task.submission_format):
            return (False, "Wrong number of files")
        language = None
        test_file = None

        # Try to understand if the task type is language dependent
        for name in self.task.submission_format:
            if name.find("%l") != -1:
                test_file = name

        # Try to detect the language used in the submission
        for test_lang in Submission.LANGUAGES:
            if test_file.replace("%l", test_lang) in self.files:
                language = test_lang
        if test_file != None and language == None:
            # If the task requires only one source file, be more
            # relaxed on the verification
            if len(self.task.submission_format) == 1:
                submitted_file = self.files.keys()[0]
                submitted_file_part = submitted_file.split(".")
                if len(submitted_file_part) > 1 and \
                        submitted_file_part[-1] in Submission.LANGUAGES:
                    language = submitted_file_part[-1]
                    correct_file = self.task.submission_format[0].replace("%l", language)
                    Utils.log("Adapted submission %s to %s" % (submitted_file, correct_file), Utils.Logger.SEVERITY_DEBUG)
                    self.files[correct_file] = self.files[submitted_file]
                    del self.files[submitted_file]
                else:
                    return (False, "Could not detect submission language")
            else:
                return (False, "Could not detect submission language")

        # Check the mapping between the submission format and the actual submission
        for name in self.task.submission_format:
            if name.replace("%l", language) not in self.files:
                return (False, "Files not corresponding to submission format")

        return (True, language)

def sample_submission(couch_id = None, user = None, task = None, files = []):
    import Task
    import User
    if user == None:
        user = User.sample_user()
    if task == None:
        task = Task.sample_task()
    from FileStorageLib import FileStorageLib
    FSL = FileStorageLib()
    files_dict = {}
    n = 0
    for f in files:
        files_dict[f] = FSL.put(f, "Submission file %s, n. %d" % (f, n))
        n += 1
    return Submission(user, task, time.time(), files_dict, couch_id = couch_id)

if __name__ == "__main__":
    s = sample_submission()
    print "Couch ID: %s" % (s.couch_id)

