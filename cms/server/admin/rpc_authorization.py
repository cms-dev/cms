#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Handle authorization for the RPC calls coming from AWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cms.db import Admin, SessionGen
from cms.io import WebService


AUTHENTICATED_USER_HEADER_IN_ENV = "HTTP_" + \
    WebService.AUTHENTICATED_USER_HEADER.upper().replace('-', '_')


RPCS_ALLOWED_FOR_AUTHENTICATED = [
    ("ResourceService", "get_resources"),
    ("EvaluationService", "workers_status"),
    ("EvaluationService", "submissions_status"),
    ("EvaluationService", "queue_status"),
    ("LogService", "last_messages"),
]


RPCS_ALLOWED_FOR_MESSAGING = RPCS_ALLOWED_FOR_AUTHENTICATED + []


RPCS_ALLOWED_FOR_ALL = RPCS_ALLOWED_FOR_MESSAGING + [
    ("ResourceService", "kill_service"),
    ("ResourceService", "toggle_autorestart"),
    ("EvaluationService", "enable_worker"),
    ("EvaluationService", "disable_worker"),
    ("EvaluationService", "invalidate_submission"),
    ("ScoringService", "invalidate_submission"),
]


def rpc_authorization_checker(environ):
    """Return whether to accept the request.

    environ ({}): WSGI environ object with the request metadata.

    return (bool): whether to accept the request or not.

    """
    try:
        admin_id = int(environ.get(AUTHENTICATED_USER_HEADER_IN_ENV, None))
        path_info = environ.get("PATH_INFO", "").strip("/").split("/")

        service = path_info[-3]
        # We don't check on shard = path_info[-2].
        method = path_info[-1]
    except (ValueError, TypeError, IndexError):
        return False

    with SessionGen() as session:
        # Load admin.
        admin = session.query(Admin)\
            .filter(Admin.id == admin_id)\
            .first()
        if admin is None:
            return False

        if admin.permission_all:
            return (service, method) in RPCS_ALLOWED_FOR_ALL

        elif admin.permission_messaging:
            return (service, method) in RPCS_ALLOWED_FOR_MESSAGING

        else:
            return (service, method) in RPCS_ALLOWED_FOR_AUTHENTICATED
