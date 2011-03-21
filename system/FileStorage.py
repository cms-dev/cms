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

import socket
import sys
import os
import codecs
import tempfile
import shutil
import hashlib
from RPCServer import RPCServer

import Configuration
import Utils

class FileStorage(RPCServer):
    def __init__(self, basedir, listen_address = None, listen_port = None):
        if listen_address == None:
            listen_address = Configuration.file_storage[0]
        if listen_port == None:
            listen_port = Configuration.file_storage[1]

        # Create server directories
        self.basedir = basedir
        self.tmpdir = os.path.join(self.basedir, "tmp")
        self.objdir = os.path.join(self.basedir, "objects")
        self.descdir = os.path.join(self.basedir, "descriptions")
        Utils.maybe_mkdir(self.basedir)
        Utils.maybe_mkdir(self.tmpdir)
        Utils.maybe_mkdir(self.objdir)
        Utils.maybe_mkdir(self.descdir)

        RPCServer.__init__(self, "FileStorage", listen_address, listen_port,
                           [self.get,
                            self.put,
                            self.delete,
                            self.describe])

    def put(self, address, port, description = ""):
        # Avoid too long descriptions, that can bloat our logs
        if len(description) > 1024:
            description = description[:1024]
        fileSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fileSocket.connect((address, port))
        # FIXME - Error management
        tempFile, tempFilename = tempfile.mkstemp(dir = self.tmpdir)
        tempFile = os.fdopen(tempFile, "w")
        hasher = hashlib.sha1()
        while True:
            data = fileSocket.recv(8192)
            if not data:
                break
            tempFile.write(data)
            hasher.update(data)
        tempFile.close()
        fileSocket.close()
        digest = hasher.hexdigest()
        shutil.move(tempFilename, os.path.join(self.objdir, digest))
        descFile = codecs.open(os.path.join(self.descdir, digest), "w", "utf-8")
        print >> descFile, description
        descFile.close()
        Utils.log("File with digest %s and description `%s' put" % (digest, description), Utils.Logger.SEVERITY_DEBUG)
        return digest

    def get(self, address, port, digest):
        fileSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fileSocket.connect((address, port))
        # FIXME - Error management
        try:
            with open(os.path.join(self.objdir, digest)) as inputFile:
                while True:
                    data = inputFile.read(8192)
                    if not data:
                        break
                    remaining = len(data)
                    while remaining > 0:
                        sent = fileSocket.send(data[-remaining:])
                        remaining -= sent
        except IOError:
            fileSocket.close()
            return False
        fileSocket.close()
        Utils.log("File with digest %s and description `%s' retrieved" % (digest, self.describe(digest)), Utils.Logger.SEVERITY_DEBUG)
        return True

    def delete(self, digest):
        try:
            os.remove(os.path.join(self.descdir, digest))
            os.remove(os.path.join(self.objdir, digest))
        except IOError:
            return False
        return True

    def describe(self, digest):
        try:
            fd = codecs.open(os.path.join(self.descdir, digest), "utf-8")
            desc = fd.read()
            fd.close()
            return desc.strip()
        except IOError:
            return None

if __name__ == "__main__":
    Utils.set_service("file storage")
    fs = FileStorage("fs")

