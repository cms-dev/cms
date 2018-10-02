#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from cms.db import Admin, SessionGen


RPCS_ALLOWED_FOR_AUTHENTICATED = [
    ("AdminWebServer", "submissions_status"),
    ("ResourceService", "get_resources"),
    ("EvaluationService", "workers_status"),
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


def rpc_authorization_checker(admin_id, service, unused_shard, method):
    """Return whether to accept the request.

    admin_id (id): the id of the administrator.
    service (string): name of the service the RPC is for.
    unused_shard (int): shard of the service the RPC is for.
    method (string): method of the service the RPC is calling.

    return (bool): whether to accept the request or not.

    """
    if admin_id is None:
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
