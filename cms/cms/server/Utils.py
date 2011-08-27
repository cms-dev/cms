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

"""Random utilities for web servers.

"""

from functools import wraps

from cms.async.WebAsyncLibrary import rpc_callback
from cms.async import ServiceCoord

def file_handler_gen(BaseClass):
    """This generates an extension of the BaseHandler that allows us
    to send files to the user. This *Gen is needed because the code in
    the class FileHandler is exactly the same (in AWS and CWS) but
    they inherits from different BaseHandler.

    BaseClass (class): the BaseHandler of our server.
    returns (class): a FileHandler extending BaseClass.

    """
    class FileHandler(BaseClass):
        """Base class for handlers that need to serve a file to the user.

        """
        def fetch(self, digest, content_type, filename):
            """Sends the RPC to the FS.

            """
            service = ServiceCoord("FileStorage", 0)
            if service not in self.application.service.remote_services or \
                   not self.application.service.remote_services[service].connected:
                # TODO: Signal the user

                self.finish()
                return

            self.application.service.remote_services[service].get_file(
                callback=self._fetch_callback,
                plus=[content_type, filename],
                digest=digest)

        @rpc_callback
        def _fetch_callback(self, caller, data, plus, error=None):
            """This is the callback for the RPC method called from a web
            page, that just collects the response.

            """
            if data is None:
                self.finish()
                return

            (content_type, filename) = plus

            self.set_header("Content-Type", content_type)
            self.set_header("Content-Disposition",
                            "attachment; filename=\"%s\"" % filename)
            self.write(data)
            self.finish()

    return FileHandler
