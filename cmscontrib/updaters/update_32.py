#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""A class to update a dump created by CMS.

Used by DumpImporter and DumpUpdater.

This updater updates time and memory limit to enforce the constraint of being
positive or null (for no limit).

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iteritems

import logging


logger = logging.getLogger(__name__)


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 31
        self.objs = data

    def run(self):
        for k, v in iteritems(self.objs):
            if k.startswith("_"):
                continue

            if v["_class"] == "Dataset":

                limit = v["time_limit"]
                # Zero explicitly meant no limits.
                if limit == 0.0:
                    limit = None
                # Negative was undefined though.
                if limit is not None and limit <= 0.0:
                    logger.warning("Previous time limit %s was updated, "
                                   "no time limit is enforced now.",
                                   limit)
                    limit = None
                v["time_limit"] = limit

                limit = v["memory_limit"]
                # Zero explicitly meant no limits.
                if limit == 0:
                    limit = None
                # Negative was undefined though.
                if limit is not None and limit <= 0:
                    logger.warning("Previous memory limit %s was updated, "
                                   "no memory limit is enforced now.",
                                   limit)
                    limit = None
                v["memory_limit"] = limit

        return self.objs
