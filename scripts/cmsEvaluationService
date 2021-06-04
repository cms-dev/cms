#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import logging
import sys

from cms import ConfigError, default_argument_parser
from cms.db import ask_for_contest, test_db_connection
from cms.service.EvaluationService import EvaluationService


logger = logging.getLogger(__name__)


def main():
    """Parse arguments and launch service.

    """
    test_db_connection()
    success = default_argument_parser(
        "Submission's compiler and evaluator for CMS.",
        EvaluationService,
        ask_contest=ask_for_contest).run()
    return 0 if success is True else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as error:
        logger.critical(error)
        sys.exit(1)
