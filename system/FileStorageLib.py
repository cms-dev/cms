#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

import Configuration

class FilePutThread(threading.Thread):
    def __init__(self, putSocket, putFile):
        threading.Thread.__init__(self)
        self.putSocket = putSocket
        self.putFile = putFile

    def run(self):
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

class FileGetThread(threading.Thread):
    def __init__(self, getSocket, getFile):
        threading.Thread.__init__(self)
        self.getSocket = getSocket
        self.getFile = getFile

    def run(self):
        (conn, addr) = self.getSocket.accept()
        while True:
            data = conn.recv(8192)
            if not data:
                break
            self.getFile.write(data)
        conn.close()

class FileStorageLib:
    def __init__(self, fs_address = None, fs_port = None):
        if fs_address == None:
            fs_address = Configuration.file_storage[0]
        if fs_port == None:
            fs_port = Configuration.file_storage[1]
        self.bind_address = ''
        local_addresses = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] + ['localhost']
        self.local_address = local_addresses[0]
        self.remote_address = fs_address
        self.fs = xmlrpclib.ServerProxy('http://%s:%d' % (fs_address, fs_port))

    def put_file(self, putFile, description = ""):
        putSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = self.random_bind(putSocket, self.bind_address)
        putSocket.listen(1)
        ft = FilePutThread(putSocket, putFile)
        ft.start()
        res = self.fs.put(self.local_address, port, description)
        ft.join()
        putSocket.close()
        return res

    def put(self, path, description = ""):
        with open(path) as putFile:
            return self.put_file(putFile, description)

    def get_file(self, dig, getFile):
        getSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port = self.random_bind(getSocket, self.bind_address)
        getSocket.listen(1)
        ft = FileGetThread(getSocket, getFile)
        ft.start()
        res = self.fs.get(self.local_address, port, dig)
        ft.join()
        getSocket.close()
        return res

    def get(self, dig, path):
        with open(path, "w") as getFile:
            return self.get_file(dig, getFile)

    def random_bind(self, bindSocket, address):
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

