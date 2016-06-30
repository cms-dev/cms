#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
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

"""This service exports every data that CMS knows. The process of
exporting and importing again should be idempotent.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import logging

from datetime import timedelta

from sqlalchemy.types import \
    Boolean, Integer, Float, String, Unicode, DateTime, Interval, Enum

from cms import utf8_decoder
import cms.db as class_hook
from cms.db import SessionGen, Contest, Task, \
    Submission, UserTest, SubmissionResult, UserTestResult, \
    RepeatedUnicode
from cms.db.filecacher import FileCacher

from cmscommon.datetime import make_timestamp
from cmscommon.datetime import make_datetime

logger = logging.getLogger(__name__)


class CloneTask(object):

    """This utility clones a task.

    """

    def __init__(self, task_name, cloned_task_name):
        with SessionGen() as session:
            task = session.query(Task)\
                .filter(Task.name == task_name).first()
            if not task:
                print("No task called `%s' found." % task_name)
                return
            self.task_id = task.id

        self.file_cacher = FileCacher()
        self.cloned_task_name = cloned_task_name

    def do_export(self):
        with SessionGen() as session:
            self.queue = []
            self.ids = {}
            datas = dict()
            cloned_task_id = self.get_id(
                Task.get_from_id(self.task_id, session)
            )
            while len(self.queue) > 0:
                obj = self.queue.pop(0)
                datas[self.ids[obj.sa_identity_key]] = \
                    self.export_object(obj)
            datas[cloned_task_id]["name"] = self.cloned_task_name
            self.objs = dict()
            for id_, data in datas.iteritems():
                if not id_.startswith("_"):
                    self.objs[id_] = self.import_object(data)
            for id_, data in datas.iteritems():
                if not id_.startswith("_"):
                    self.add_relationships(data, self.objs[id_])
            session.add(self.objs[cloned_task_id])
            session.commit()
        return True

    def get_id(self, obj):
        obj_key = obj.sa_identity_key
        if obj_key not in self.ids:
            # We use strings because they'll be the keys of a JSON object
            self.ids[obj_key] = "%d" % len(self.ids)
            self.queue.append(obj)

        return self.ids[obj_key]

    def export_object(self, obj):

        """Export the given object, returning a JSON-encodable dict.

        The returned dict will contain a "_class" item (the name of the
        class of the given object), an item for each column property
        (with a value properly translated to a JSON-compatible type)
        and an item for each relationship property (which will be an ID
        or a collection of IDs).

        The IDs used in the exported dict aren't related to the ones
        used in the DB: they are newly generated and their scope is
        limited to the exported file only. They are shared among all
        classes (that is, two objects can never share the same ID, even
        if they are of different classes).

        If, when exporting the relationship, we find an object without
        an ID we generate a new ID, assign it to the object and append
        the object to the queue of objects to export.

        """

        cls = type(obj)

        data = {"_class": cls.__name__}

        for prp in cls._col_props:
            col, = prp.columns
            col_type = type(col.type)

            val = getattr(obj, prp.key)
            if col_type in \
                    [Boolean, Integer, Float, Unicode, RepeatedUnicode, Enum]:
                data[prp.key] = val
            elif col_type is String:
                data[prp.key] = \
                    val.decode('latin1') if val is not None else None
            elif col_type is DateTime:
                data[prp.key] = \
                    make_timestamp(val) if val is not None else None
            elif col_type is Interval:
                data[prp.key] = \
                    val.total_seconds() if val is not None else None
            else:
                raise RuntimeError("Unknown SQLAlchemy column type: %s"
                                   % col_type)
        for prp in cls._rel_props:
            other_cls = prp.mapper.class_

            # Skip submissions if requested
            if other_cls in (Submission, UserTest,
                             SubmissionResult, UserTestResult, Contest):
                continue

            val = getattr(obj, prp.key)
            if val is None:
                data[prp.key] = None
            elif isinstance(val, other_cls):
                data[prp.key] = self.get_id(val)
            elif isinstance(val, list):
                data[prp.key] = list(self.get_id(i) for i in val)
            elif isinstance(val, dict):
                data[prp.key] = \
                    dict((k, self.get_id(v)) for k, v in val.iteritems())
            else:
                raise RuntimeError("Unknown SQLAlchemy relationship type: %s"
                                   % type(val))

        return data

    def import_object(self, data):

        """Import objects from the given data (without relationships).

        The given data is assumed to be a dict in the format produced by
        ContestExporter. This method reads the "_class" item and tries
        to find the corresponding class. Then it loads all column
        properties of that class (those that are present in the data)
        and uses them as keyword arguments in a call to the class
        constructor (if a required property is missing this call will
        raise an error).

        Relationships are not handled by this method, since we may not
        have all referenced objects available yet. Thus we prefer to add
        relationships in a later moment, using the add_relationships
        method.

        Note that both this method and add_relationships don't check if
        the given data has more items than the ones we understand and
        use.

        """

        cls = getattr(class_hook, data["_class"])

        args = dict()

        for prp in cls._col_props:
            if prp.key not in data:
                # We will let the __init__ of the class check if any
                # argument is missing, so it's safe to just skip here.
                continue

            col = prp.columns[0]
            col_type = type(col.type)

            val = data[prp.key]
            if col_type in \
                    [Boolean, Integer, Float, Unicode, RepeatedUnicode, Enum]:
                args[prp.key] = val
            elif col_type is String:
                args[prp.key] = \
                    val.encode('latin1') if val is not None else None
            elif col_type is DateTime:
                args[prp.key] = \
                    make_datetime(val) if val is not None else None
            elif col_type is Interval:
                args[prp.key] = \
                    timedelta(seconds=val) if val is not None else None
            else:
                raise RuntimeError(
                    "Unknown SQLAlchemy column type: %s" % col_type)

        return cls(**args)

    def add_relationships(self, data, obj):

        """Add the relationships to the given object, using the given data.

        Do what we didn't in import_objects: importing relationships.
        We already now the class of the object so we simply iterate over
        its relationship properties trying to load them from the data (if
        present), checking wheter they are IDs or collection of IDs,
        dereferencing them (i.e. getting the corresponding object) and
        reflecting all on the given object.

        Note that both this method and import_object don't check if the
        given data has more items than the ones we understand and use.

        """

        cls = type(obj)

        for prp in cls._rel_props:
            if prp.key not in data:
                # Relationships are always optional
                continue

            val = data[prp.key]
            if val is None:
                setattr(obj, prp.key, None)
            elif type(val) == unicode:
                setattr(obj, prp.key, self.objs[val])
            elif type(val) == list:
                setattr(obj, prp.key, list(self.objs[i] for i in val))
            elif type(val) == dict:
                setattr(obj, prp.key,
                        dict((k, self.objs[v]) for k, v in val.iteritems()))
            else:
                raise RuntimeError(
                    "Unknown RelationshipProperty value: %s" % type(val))


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Clone a task."
    )

    parser.add_argument(
        "task_name",
        action="store", type=utf8_decoder,
        help="short name of the task"
    )
    parser.add_argument(
        "cloned_task_name",
        action="store", type=utf8_decoder,
        help="short name of the cloned task"
    )
    args = parser.parse_args()

    CloneTask(
        task_name=args.task_name,
        cloned_task_name=args.cloned_task_name
    ).do_export()


if __name__ == "__main__":
    main()
