#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import logging

from importlib.metadata import entry_points


logger = logging.getLogger(__name__)


def plugin_list(entry_point_group: str) -> list[type]:
    """Return the list of plugin classes of the given group.

    The aspects of CMS that require the largest flexibility in behavior
    are controlled by arbitrary Python code, encapsulated in classes
    (e.g., task and score types, languages, ...). CMS ships with
    collections of common options for these, but users can provide
    their own custom ones using a plugin system. This is based on
    setuptools' entry points: distributions (e.g., PyPI packages) can
    list some of their classes in the entry_points section of their
    setup.py inside some CMS-specific groups and, once they are
    installed, CMS will be able to automatically discover and use those
    classes.

    entry_point_group: the name of the group of entry points that
        should be returned, typically one of cms.grading.tasktypes,
        scoretypes or languages.

    return: the requested plugin classes.

    """
    classes = []
    for entry_point in entry_points(group=entry_point_group):
        try:
            classes.append(entry_point.load())
        except Exception:
            logger.warning(
                "Failed to load entry point %s for group %s from %s, "
                "provided by distribution %s.",
                entry_point.name,
                entry_point_group,
                entry_point.value,
                entry_point.dist.name if entry_point.dist else "unknown",
                exc_info=True,
            )
    return classes
