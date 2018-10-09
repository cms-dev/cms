#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Submission-related helpers for CWS.

"""

import os.path
import pickle

from cms import config
from cms.db import Submission, UserTest
from .check import get_latest_submission


def fetch_file_digests_from_previous_submission(
        sql_session, participation, task, language, codenames, cls=Submission):
    """Retrieve digests of files with given codenames from latest submission.

    Get the most recent submission of the given contestant on the given
    task and, if it is of the given language, return the digests of its
    files that correspond to the given codenames. In case of UserTests
    lookup also among the user-provided managers.

    sql_session (Session): the SQLAlchemy session to use.
    participation (Participation): the participation whose submissions
        should be considered.
    task (Task): the task whose submissions should be considered.
    language (Language|None): the language the submission has to be in
        for the lookup to be allowed.
    codenames ({str}): the filenames-with-%l that need to be retrieved.
    cls (type): if the UserTest class is given, lookup user tests rather
        than submissions.

    return ({str: str}): for every codename, the digest of the file of
        that codename in the previous submission; if the previous
        submission didn't have that file it won't be included in the
        result; if there is no previous submission or if it isn't in the
        desired language, return an empty result.

    """
    # FIXME Instead of taking the latest submission *if* it is of the
    # right language, take the latest *among* those of that language.
    latest_submission = get_latest_submission(
        sql_session, participation, task=task, cls=cls)

    language_name = language.name if language is not None else None
    if latest_submission is None or language_name != latest_submission.language:
        return dict()

    digests = dict()
    for codename in codenames:
        # The expected behavior of this code is undefined when a task's
        # submission format, its task type's user_managers and {"input"}
        # are not pairwise disjoint sets. That is not supposed to happen
        # and it would probably already create issues upon submission.
        if codename in latest_submission.files:
            digests[codename] = latest_submission.files[codename].digest
        elif cls is UserTest:
            if codename == "input":
                digests["input"] = latest_submission.input
            else:
                if codename.endswith(".%l"):
                    if language is None:
                        raise ValueError("language not given when submission "
                                         "format requires it")
                    filename = (os.path.splitext(codename)[0]
                                + language.source_extension)
                else:
                    filename = codename
                if filename in latest_submission.managers:
                    digests[codename] = \
                        latest_submission.managers[filename].digest

    return digests


class StorageFailed(Exception):
    pass


def store_local_copy(path, participation, task, timestamp, files):
    """Write the files plus some metadata to a local backup

    Add a new file to the local backup storage (rooted in the given
    directory), containing the data of the given files and some details
    about the user, the task and the contest of the submission. The
    files are organized in directories (one for each contestant, named
    as their usernames) and their names are the dates and times of the
    submissions. The files' contents are pickle-encoded tuples whose
    first three elements are the contest ID, the user ID and the task ID
    and whose fourth element is a dict describing the files.

    path (str): the directory in which to build the archive; it will be
        created if it doesn't exist; if it contains `%s` it will be
        replaced with the data_dir specified in the config.
    participation (Participation): the participation that submitted.
    task (Task): the task on which they submitted.
    timestamp (datetime): when the submission happened.
    files ({str: bytes}): the files that were sent in: the keys are the
        codenames (filenames-with-%l), the values are the contents.

    raise (StorageFailed): in case of problems.

    """
    try:
        path = os.path.join(path.replace("%s", config.data_dir),
                            participation.user.username)
        if not os.path.exists(path):
            os.makedirs(path)
        with open(os.path.join(path, "%s" % timestamp), "wb") as f:
            pickle.dump((participation.contest.id, participation.user.id,
                         task.id, files), f)
    except OSError as e:
        raise StorageFailed("Failed to store local copy of submission: %s", e)
