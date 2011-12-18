#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import os
from cms import Config

# ssl_options are the same options for ssl.wrap_socket.
# server side is already included.
# ssl_options = {"certfile": "cert.pem"}
ssl_options = None


quick_answers = {
    "yes": "Yes",
    "no": "No",
    "answered": "Answered in task description",
    "invalid": "Invalid question",
    "nocomment": "No comment",
    }

# FIXME - Implement some smarter search function
tornado_files_basepath = os.path.dirname(__file__)

contest_parameters = {
    "login_url": "/",
    "template_path": os.path.join(tornado_files_basepath,
                                  "templates", "contest"),
    "static_path": os.path.join(tornado_files_basepath,
                                "static", "contest"),
    "cookie_secret": Config.tornado_secret_key,
    "debug": Config.tornado_debug,
    }

admin_parameters = {
    "login_url": "/",
    "template_path": os.path.join(tornado_files_basepath,
                                  "templates", "admin"),
    "static_path": os.path.join(tornado_files_basepath,
                                "static", "admin"),
    "cookie_secret": Config.tornado_secret_key,
    "debug": Config.tornado_debug,
    }
