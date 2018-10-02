#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utility functions for importers"""

import functools

from cms.db import Contest, Dataset, Task


__all__ = [
    "contest_from_db", "task_from_db",
    "update_contest", "update_task"
]


class ImportDataError(Exception):
    pass


def contest_from_db(contest_id, session):
    """Return the contest object with the given id

    contest_id (int|None): the id of the contest, or None to return None.
    session (Session): SQLAlchemy session to use.

    return (Contest|None): None if contest_id is None, or the contest.
    raise (ImportDataError): if there is no contest with the given id.

    """
    if contest_id is None:
        return None

    contest = Contest.get_from_id(contest_id, session)
    if contest is None:
        raise ImportDataError(
            "The specified contest (id %s) does not exist." % contest_id)
    return contest


def task_from_db(task_name, session):
    """Return the task object with the given name

    task_name (string|None): the name of the task, or None to return None.
    session (Session): SQLAlchemy session to use.

    return (Task|None): None if task_name is None, or the task.
    raise (ImportDataError): if there is no task with the given name.

    """
    if task_name is None:
        return None

    task = session.query(Task).filter(Task.name == task_name).first()
    if task is None:
        raise ImportDataError(
            "The specified task (name %s) does not exist." % task_name)
    return task


def _update_columns(old_object, new_object, spec=None):
    """Update the scalar columns of the object

    Update all non-relationship columns of old_object with the values in
    new_object, unless spec[attribute] is False.

    """
    assert type(old_object) == type(new_object)
    spec = spec if spec is not None else {}

    for prp in old_object._col_props:
        if spec.get(prp.class_attribute, True) is False:
            continue
        if hasattr(new_object, prp.key):
            setattr(old_object, prp.key, getattr(new_object, prp.key))


def _update_object(old_object, new_object, spec=None, parent=None):
    """Update old_object with the values in new_object

    Update all columns with this strategy:
    - for non-relationship columns, use _update_columns (in particular, all
      columns are updated by default, unless spec[attribute] is false);
    - for relationship columns:
      - if the name is equal to parent, then it is ignored;
      - otherwise, it needs to be defined in spec; if spec is False, the
        column is ignored; if it is True, it is updated with the default
        strategy (see _update_list and _update_dict); otherwise if spec is
        a function, that function is used to update.

    old_object (Base): object to update.
    new_object (Base): object whose values will be used.
    spec (
        {sqlalchemy.orm.attributes.InstrumentedAttribute: boolean|function}
        |None): a dictionary mapping attributes to a boolean (if not
        updating or using the default strategy) or to an updating function,
        with signature fn(old_value, new_value, parent=None).
    parent (string|None): the name of the relationship in the parent object,
        which is ignored.

    """
    assert type(old_object) == type(new_object)
    spec = spec if spec is not None else {}

    # Update all scalar columns by default, unless spec says otherwise.
    _update_columns(old_object, new_object, spec)

    for prp in old_object._rel_props:
        # Don't update the parent relationship (works both for backref and
        # back_populates relationships).
        if parent is not None:
            if (prp.backref is not None and prp.backref[0] == parent) \
                    or prp.back_populates == parent:
                continue

        # To avoid bugs when new relationships are introduced, we force the
        # caller to describe how to update all other relationships.
        assert prp.class_attribute in spec, (
            "Programming error: update specification not complete, "
            "missing relationship for %s.%s"
            % (prp.parent.class_, prp.class_attribute))

        # Spec is false, it means we should not update this relationship.
        if spec[prp.class_attribute] is False:
            continue

        old_value = getattr(old_object, prp.key)
        new_value = getattr(new_object, prp.key)
        if spec[prp.class_attribute] is True:
            # Spec is true, it means we update the relationship with the
            # default update method (for lists or dicts). Note that the
            # values cannot have other relationships than the parent's,
            # otherwise _update_object will complain it doesn't have the
            # spec for them.
            update_fn = functools.partial(_update_object, parent=prp.key)
            if isinstance(old_value, dict):
                _update_dict(old_value, new_value, update_fn)
            elif isinstance(old_value, list):
                _update_list(old_value, new_value, update_fn)
            else:
                raise AssertionError(
                    "Programming error: unknown type of relationship for "
                    "%s.%s." % (prp.parent.class_, prp.class_attribute))
        else:
            # Spec is not true, then it must be an update function, which
            # we duly apply.
            spec[prp.class_attribute](old_value, new_value, parent=prp.key)


def _update_list(old_list, new_list, update_value_fn=None):
    """Update a SQLAlchemy relationship with type list

    Make old_list look like new_list, by:
    - up to the minimum length, calling update_value_fn on each element, to
      overwrite the values;
    - deleting additional entries in old_list, if they exist;
    - moving additional entries in new_list, if they exist.

    """
    if update_value_fn is None:
        update_value_fn = _update_object

    old_len = len(old_list)
    new_len = len(new_list)

    # Update common elements.
    for old_value, new_value in zip(old_list, new_list):
        update_value_fn(old_value, new_value)

    # Delete additional elements of old_list.
    del old_list[new_len:]

    # Move additional elements from new_list to old_list.
    for _ in range(old_len, new_len):
        # For some funny behavior of SQLAlchemy-instrumented collections when
        # copying values, that resulted in new objects being added to the
        # session.
        temp = new_list[old_len]
        del new_list[old_len]
        old_list.append(temp)


def _update_dict(old_dict, new_dict, update_value_fn=None):
    """Update a SQLAlchemy relationship with type dict

    Make old_dict look like new_dict, by:
    - calling update_value_fn to overwrite the values of old_dict with a
      corresponding value in new_dict;
    - deleting all entries in old_dict whose key is not in new_dict;
    - moving all entries in new_dict whose key is not in old_dict.

    """
    if update_value_fn is None:
        update_value_fn = _update_object
    for key in set(old_dict.keys()) | set(new_dict.keys()):
        if key in new_dict:
            if key not in old_dict:
                # Move the object from new_dict to old_dict. For some funny
                # behavior of SQLAlchemy-instrumented collections when
                # copying values, that resulted in new objects being added
                # to the session.
                temp = new_dict[key]
                del new_dict[key]
                old_dict[key] = temp
            else:
                # Update the old value with the new value.
                update_value_fn(old_dict[key], new_dict[key])
        else:
            # Delete the old value if no new value for that key.
            del old_dict[key]


def _update_list_with_key(old_list, new_list, key,
                          preserve_old=False, update_value_fn=None):
    """Update a SQLAlchemy list-relationship, using key for identity

    Make old_list look like new_list, in a similar way to _update_dict, as
    if the list was a dictionary with key computed using the key function.

    If preserve_old is true, elements in old_list with a key not present in
    new_list will be preserved.

    """
    if update_value_fn is None:
        update_value_fn = _update_object

    old_dict = dict((key(v), v) for v in old_list)
    new_dict = dict((key(v), v) for v in new_list)

    for k in set(old_dict.keys()) | set(new_dict.keys()):
        if k in new_dict:
            if k not in old_dict:
                # Add new value to the old dictionary.
                temp = new_dict[k]
                new_list.remove(temp)
                old_list.append(temp)
            else:
                # Update the value in old_dict with the new value.
                update_value_fn(old_dict[k], new_dict[k])
        elif not preserve_old:
            # Remove the old value not anymore present.
            old_list.remove(old_dict[k])


def update_dataset(old_dataset, new_dataset, parent=None):
    """Update old_dataset with information from new_dataset"""
    _update_object(old_dataset, new_dataset, {
        # Since we know it, hardcode to ignore the parent relationship.
        Dataset.task: False,
        # Relationships to update (all others).
        Dataset.managers: True,
        Dataset.testcases: True,
    }, parent=parent)


def update_task(old_task, new_task, parent=None, get_statements=True):
    """Update old_task with information from new_task"""
    def update_datasets_fn(o, n, parent=None):
        _update_list_with_key(
            o, n, key=lambda d: d.description, preserve_old=True,
            update_value_fn=functools.partial(update_dataset, parent=parent))

    _update_object(old_task, new_task, {
        # Since we know it, hardcode to ignore the parent relationship.
        Task.contest: False,
        # Relationships not to update because not provided by the loader.
        Task.active_dataset: False,
        Task.submissions: False,
        Task.user_tests: False,
        # Relationships to update.
        Task.statements: get_statements,
        Task.datasets: update_datasets_fn,
        Task.attachments: True,
        # Scalar columns exceptions.
        Task.num: False,
        Task.primary_statements: get_statements,
    }, parent=parent)


def update_contest(old_contest, new_contest, parent=None):
    """Update old_contest with information from new_contest"""
    _update_object(old_contest, new_contest, {
        # Announcements are not provided by the loader, we should keep
        # those we have.
        Contest.announcements: False,
        # Tasks and participations are top level objects for the loader, so
        # must be handled differently.
        Contest.tasks: False,
        Contest.participations: False,
    }, parent=parent)
