#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""This directory holds utilities to import and export data to and
from CMS for different formats. Examples are ContestImport and
ContestExport, whose aim is to be one the inverse of the other (hence
losing no data in the process).

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import io
import os

from cms.db import Base, Contest, Participation, Submission, Task


def sha1sum(path):
    """Calculates the SHA1 sum of a file, given by its path.

    path (string): path of the file we are interested in.

    return (string): SHA1 sum of the file in path.

    """
    buffer_length = 8192
    with io.open(path, 'rb') as fin:
        hasher = hashlib.new("sha1")
        buf = fin.read(buffer_length)
        while buf != b'':
            hasher.update(buf)
            buf = fin.read(buffer_length)
        return hasher.hexdigest()


# Taken from
# http://stackoverflow.com/questions/1158076/implement-touch-using-python
def touch(path):
    """Touch path, which must be regular file.

    This behaves like the UNIX touch utility.

    path (str): the path to be touched.

    """
    with io.open(path, 'ab'):
        os.utime(path, None)


def _is_rel(prp, attr):
    # The target of the relationship is in prp.mapper.class_
    return prp.parent.class_ == attr.class_ and prp.key == attr.key


class BaseImporter(object):

    def _update_columns(self, old_object, new_object, ignore=None):
        ignore = ignore if ignore is not None else set()
        for prp in old_object._col_props:
            if prp.key in ignore:
                continue
            if hasattr(new_object, prp.key):
                setattr(old_object, prp.key, getattr(new_object, prp.key))

    def _update_object(self, old_object, new_object, ignore=None):
        # This method copies the scalar column properties from the new
        # object into the old one, and then tries to do the same for
        # relationships too. The data model isn't a tree: for example
        # there are two distinct paths from Contest to Submission, one
        # through User and one through Task. Yet, at the moment, if we
        # ignore Submissions and UserTest (and thus their results, too)
        # we get a tree-like structure and Task.active_dataset and
        # Submission.token are the only scalar relationships that don't
        # refer to the parent. Therefore, if we catch these as special
        # cases, we can use a simple DFS to explore the whole data
        # graph, recursing only on "vector" relationships.
        # TODO Find a better way to handle all of this.

        ignore = ignore if ignore is not None else set()
        self._update_columns(old_object, new_object, ignore)

        for prp in old_object._rel_props:
            if prp.key in ignore:
                continue

            old_value = getattr(old_object, prp.key)
            new_value = getattr(new_object, prp.key)

            # Special case #1: Contest.announcements, User.questions,
            #                  User.messages
            if _is_rel(prp, Contest.announcements):
                # A loader should not provide new Announcements,
                # Questions or Messages, since they are data generated
                # by the users during the contest: don't update them.
                # TODO Warn the admin if these attributes are non-empty
                # collections.
                pass

            # Special case #2: Task.datasets
            elif _is_rel(prp, Task.datasets):
                old_datasets = dict((d.description, d) for d in old_value)
                new_datasets = dict((d.description, d) for d in new_value)

                for key in set(new_datasets.keys()):
                    if key not in old_datasets:
                        # create
                        temp = new_datasets[key]
                        new_value.remove(temp)
                        old_value.append(temp)
                    else:
                        # update
                        self._update_object(old_datasets[key],
                                            new_datasets[key])

            # Special case #3: Task.active_dataset
            elif _is_rel(prp, Task.active_dataset):
                # We don't want to update the existing active dataset.
                pass

            # Special case #4: User.submissions, Task.submissions,
            #                 User.user_tests, Task.user_tests
            elif (_is_rel(prp, Task.submissions) or
                  _is_rel(prp, Participation.submissions) or
                  _is_rel(prp, Task.user_tests) or
                  _is_rel(prp, Participation.user_tests)):
                # A loader should not provide new Submissions or
                # UserTests, since they are data generated by the users
                # during the contest: don't update them.
                # TODO Warn the admin if these attributes are non-empty
                # collections.
                pass

            # Special case #5: Submission.token
            elif _is_rel(prp, Submission.token):
                # We should never reach this point! We should never try
                # to update Submissions! We could even assert False...
                pass

            # General case #1: a dict
            elif isinstance(old_value, dict):
                for key in set(old_value.keys()) | set(new_value.keys()):
                    if key in new_value:
                        if key not in old_value:
                            # create
                            # FIXME This hack is needed because of some
                            # funny behavior of SQLAlchemy-instrumented
                            # collections when copying values, that
                            # resulted in new objects being added to
                            # the session. We need to investigate it.
                            temp = new_value[key]
                            del new_value[key]
                            old_value[key] = temp
                        else:
                            # update
                            self._update_object(old_value[key], new_value[key])
                    else:
                        # delete
                        del old_value[key]

            # General case #2: a list
            elif isinstance(old_value, list):
                old_len = len(old_value)
                new_len = len(new_value)
                for i in xrange(min(old_len, new_len)):
                    self._update_object(old_value[i], new_value[i])
                if old_len > new_len:
                    del old_value[new_len:]
                elif new_len > old_len:
                    for i in xrange(old_len, new_len):
                        # FIXME This hack is needed because of some
                        # funny behavior of SQLAlchemy-instrumented
                        # collections when copying values, that
                        # resulted in new objects being added to the
                        # session. We need to investigate it.
                        temp = new_value[i]
                        del new_value[i]
                        old_value.append(temp)

            # General case #3: a parent object
            elif isinstance(old_value, Base):
                # No need to climb back up the recursion tree...
                pass

            # General case #4: None
            elif old_value is None:
                # That should only happen in case of a scalar
                # relationship (i.e. a many-to-one or a one-to-one)
                # that is nullable. "Parent" relationships aren't
                # nullable, so the only possible cases are the active
                # datasets and the tokens, but we should have already
                # caught them. We could even assert False...
                pass

            else:
                raise RuntimeError(
                    "Unknown type of relationship for %s.%s." %
                    (prp.parent.class_.__name__, prp.key))
