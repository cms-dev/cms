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

import xmlrpclib
import socket
import sys
import os
import threading
import shutil
import random
import tempfile

import Configuration
import Utils

class FilePutThread(threading.Thread):
    def __init__(self, putSocket, putFile):
        threading.Thread.__init__(self)
        self.putSocket = putSocket
        self.putFile = putFile

    def run(self):
        try:
            (conn, addr) = self.putSocket.accept()
            while True:
                data = self.putFile.read(8192)
                if not data:
                    break
                remaining = len(data)
                while remaining > 0:
                    sent = conn.send(data[-remaining:])
                    remaining -= sent
            conn.close()
        except socket.timeout:
            Utils.log("Failed to put a file: connection timeout.",Utils.Logger.SEVERITY_IMPORTANT)
            return

class FileGetThread(threading.Thread):
    def __init__(self, getSocket, getFiles):
        threading.Thread.__init__(self)
        self.getSocket = getSocket
        self.getFiles = getFiles

    def run(self):
        try:
            (conn, addr) = self.getSocket.accept()
            while True:
                data = conn.recv(8192)
                if not data:
                    break
                for (getFile, errorHandler) in self.getFiles:
                    try:
                        getFile.write(data)
                    except IOError:
                        del self.getFiles[(getFile, errorHandler)]
                        if errorHandler != None:
                            errorHandler()
            conn.close()
        except socket.timeout:
            Utils.log("Failed to get a file: connection timeout.",Utils.Logger.SEVERITY_IMPORTANT)
            return

class FileStorageLib:
    def __init__(self, fs_address = None, fs_port = None, basedir = None):
        if fs_address == None:
            fs_address = Configuration.file_storage[0]
        if fs_port == None:
            fs_port = Configuration.file_storage[1]
        if basedir == None:
            basedir = Configuration.file_storage_cache_basedir
        self.basedir = basedir

        # Create directories
        self.tmpdir = os.path.join(self.basedir, "tmp")
        self.objdir = os.path.join(self.basedir, "objects")
        Utils.maybe_mkdir(self.basedir)
        Utils.maybe_mkdir(self.tmpdir)
        Utils.maybe_mkdir(self.objdir)

        # Bad hack to detect our address
        self.bind_address = ''
        local_addresses = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] + ['localhost']
        self.local_address = local_addresses[0]
        Utils.log("Using %s as local address." % self.local_address, Utils.Logger.SEVERITY_DEBUG)
        self.remote_address = fs_address

        self.fs = xmlrpclib.ServerProxy('http://%s:%d' % (fs_address, fs_port))

    def put_file(self, putFile, description = ""):
        putSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = self.random_bind(putSocket, self.bind_address)
        putSocket.listen(1)
        # Timeout needed to gracefully stop the thread
        putSocket.settimeout(Configuration.FS_connection_timeout)
        ft = FilePutThread(putSocket, putFile)
        ft.start()
        res = self.fs.put(self.local_address, port, description)
        ft.join()
        putSocket.close()
        return res

    def put(self, path, description = ""):
        with open(path) as putFile:
            return self.put_file(putFile, description)

    def get_file_from_cache(self, dig, getFile):
        try:
            with open(os.path.join(self.objdir, dig)) as cachedFile:
                shutil.copyfileobj(cachedFile, getFile)
                return True
        except IOError:
            return None

    def get_file(self, dig, getFile):
        # TODO: Clear cache periodically, or when the file is too old
        if self.get_file_from_cache(dig, getFile):
            return True
        getSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = self.random_bind(getSocket, self.bind_address)
        getSocket.listen(1)
        # Timeout needed to gracefully stop the thread
        getSocket.settimeout(Configuration.FS_connection_timeout)

        tempFile, tempFilename = tempfile.mkstemp(dir = self.tmpdir)
        ft = FileGetThread(getSocket, [(getFile, None), (os.fdopen(tempFile, 'w'), None)])
        ft.start()
        res = self.fs.get(self.local_address, port, dig)
        ft.join()
        getSocket.close()
        shutil.move(tempFilename, os.path.join(self.objdir, dig))
        return res

    def get(self, dig, path):
        with open(path, "w") as getFile:
            return self.get_file(dig, getFile)

    def random_bind(self, bindSocket, address):
        """Try to bind bindSocket to a random port using the specified
        address. Keeps searching a free port until one if found, but
        raise an exception if the bind() call failed for some other
        reason."""
        ok = False
        while not ok:
            try:
                port = random.randint(10000, 60000)
                bindSocket.bind((address, port))
                ok = True
            except socket.error as (errno, strerror):
                if errno != os.errno.EADDRINUSE:
                    raise
        return port

if __name__ == "__main__":
    print "Give a filename you don't care of: ",
    filename = raw_input()
    assert(filename != '')
    with open(filename, "w") as fileHandler:
        fileHandler.write("1\n2\n3\n")
    FSL = FileStorageLib()
    dig = FSL.put(filename, "Interesting file")
    print "Put file %s, digest = %s" % (filename, dig)
    os.remove(filename)
    res = FSL.get(dig, filename)
    print "Got file %s, value = %s" % (filename, res)
    content = open(filename).read()
    if content == "1\n2\n3\n":
        print "Correct"
    else:
        print "Wrong result"
    os.remove(filename)

