#!/usr/bin/python
# -*- coding: utf-8 -*-

import xmlrpclib
import socket
import sys
import os
import threading
import shutil
import random

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
	def __init__(self, fs_address = 'localhost', fs_port = 8000):
		self.bind_address = ''
		local_addresses = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] + ['localhost']
		self.local_address = local_addresses[0]
		self.remote_address = fs_address
		self.fs = xmlrpclib.ServerProxy('http://%s:%d' % (fs_address, fs_port))

	def put(self, path, description = ""):
		putSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		port = self.random_bind(putSocket, self.bind_address)
		putSocket.listen(1)
		with open(path) as putFile:
			ft = FilePutThread(putSocket, putFile)
			ft.start()
			res = self.fs.put(self.local_address, port, description)
		putSocket.close()
		return res

	def get(self, dig, path):
		getSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		port = self.random_bind(getSocket, self.bind_address)
		getSocket.listen(1)
		with open(path, "w") as getFile:
			ft = FileGetThread(getSocket, getFile)
			ft.start()
			res = self.fs.get(self.local_address, port, dig)
			ft.join()
		getSocket.close()
		return res

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
	FSL = FileStorageLib()
	dig = FSL.put("ciao.txt", "Interesting file")
	print "Put file ciao.txt, digest = %s" % (dig)
	res = FSL.get(dig, "ciao2.txt")
	print "Got file ciao2.txt, value =", res

