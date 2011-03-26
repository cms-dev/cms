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

"""FileStorage is service to store and retrieve files, assumed to be binary.

"""

import os

import tempfile
import shutil
import codecs
import hashlib

from AsyncLibrary import Service, \
     rpc_method, rpc_binary_response, rpc_callback, \
     logger
from Utils import ServiceCoord, Address, mkdir


class FileStorage(Service):
    """Offer capibilities of storing and retrieving binary files.

    """

    def __init__(self, base_dir, shard):
        logger.initialize(ServiceCoord("FileStorage", shard))
        logger.debug("FileStorage.__init__")
        Service.__init__(self, shard)

        # Create server directories
        self.base_dir = base_dir
        self.tmp_dir = os.path.join(self.base_dir, "tmp")
        self.obj_dir = os.path.join(self.base_dir, "objects")
        self.desc_dir = os.path.join(self.base_dir, "descriptions")

        ret = True
        ret = ret and mkdir(self.base_dir)
        ret = ret and mkdir(self.tmp_dir)
        ret = ret and mkdir(self.obj_dir)
        ret = ret and mkdir(self.desc_dir)
        if not ret:
            logger.critical("Cannot create necessary directories.")


    @rpc_method
    def put_file(self, binary_data, description=""):
        """Method to put a file in the file storage.

        description (string): a human-readable description of the
                              content of the file (not used
                              internally, just for human convenience)
        returns (string): the SHA1 digest of the file

        """
        logger.debug("FileStorage.put")
        # Avoid too long descriptions, that can bloat our logs
        if len(description) > 1024:
            log.info("Description '%s...' trimmed because too long." %
                     description[:50])
            description = description[:1024]
        logger.info("New file added: `%s'" % description)

        # FIXME - Error management
        temp_file, temp_filename = tempfile.mkstemp(dir = self.tmp_dir)
        temp_file = os.fdopen(temp_file, "wb")

        # Get the file and compute the hash
        hasher = hashlib.sha1()
        temp_file.write(binary_data)
        hasher.update(binary_data)
        temp_file.close()
        digest = hasher.hexdigest()
        shutil.move(temp_filename, os.path.join(self.obj_dir, digest))

        # Update description
        with codecs.open(os.path.join(self.desc_dir, digest), "w",
                         "utf-8") as desc_file:
            print >> desc_file, description

        logger.debug("File with digest %s and description `%s' put" %
                     (digest, description))
        return digest

    @rpc_method
    @rpc_binary_response
    def get_file(self, digest):
        """Method to get a file from the file storage.

        digest (string): the SHA1 digest of the requested file
        returns (string): the binary string containing the content of
                          the file

        """
        logger.info("FileStorage.get")
        # Errors are managed by the caller
        input_file = open(os.path.join(self.obj_dir, digest), "rb")
        data = input_file.read()
        logger.debug("File with digest %s and description `%s' retrieved" %
                     (digest, self.describe(digest)))
        return data

    @rpc_method
    def delete(self, digest):
        logger.debug("FileStorage.delete")
        try:
            os.remove(os.path.join(self.desc_dir, digest))
            os.remove(os.path.join(self.obj_dir, digest))
        except IOError:
            return False
        return True

    @rpc_method
    def describe(self, digest):
        logger.debug("FileStorage.describe")
        try:
            fd = open(os.path.join(self.desc_dir, digest))
            desc = fd.read()
            fd.close()
            return desc.strip()
        except IOError:
            return None


class FileCacher:
    """This class implement a local cache for files obtainable from a
    FileStorage service.

    """

    def __init__(self, service, file_storage, base_dir="fs-cache"):
        """
        service (Service): the service we are running in
        file_storage (RemoteService): the local instance of the
                                      FileStorage service.
        base_dir (string): the directory where to store the cache.
        """
        self.service = service
        self.file_storage = file_storage
        self.base_dir = base_dir
        self.tmp_dir = os.path.join(self.base_dir, "tmp")
        self.obj_dir = os.path.join(self.base_dir, "objects")
        ret = True
        ret = ret and mkdir(self.base_dir)
        ret = ret and mkdir(self.tmp_dir)
        ret = ret and mkdir(self.obj_dir)
        if not ret:
            logger.critical("Cannot create necessary directories.")

    def _get_from_cache(self, digest):
        """Check if a file is present in the local cache.

        digest (string): the sha1 sum of the file
        returns (string): the content of the file, or None

        """
        try:
            with open(os.path.join(self.obj_dir, digest), "rb") \
                     as cached_file:
                return cached_file.read()
        except IOError:
            return None

    def get_file(self, digest, path=None, callback=None, plus=None):
        """Get a file from the cache or from the service if not
        present.

        digest (string): the sha1 sum of the file
        path (string): a path where to save the file
        callback (function): to be called with the content of the file
        plus (object): additional data for the callback

        """
        from_cache = self._get_from_cache(digest)
        new_plus = {"path": path,
                    "digest": digest,
                    "callback": callback,
                    "plus": plus}

        if from_cache != None:
            new_plus["error"] = None
            new_plus["data"] = from_cache
            self.service.add_timeout(self._got_file, new_plus,
                                     100, immediately=True)
        else:
            self.file_storage.get_file(digest=digest,
                bind_obj=self,
                callback=FileCacher._got_file_remote,
                plus=new_plus)
        return True

    @rpc_callback
    def _got_file_remote(self, data, plus, error=None):
        """Callback for get_file when the file is taken from the
        remote FileStorage service.

        data (string): the content of the file
        plus (dict): a dictionary with the fields: path, digest,
                     callback, plus
        error (string): an error from FileStorage

        """
        plus["data"] = data
        plus["error"] = error
        if error == None:
            try:
                path = os.path.join(self.obj_dir, plus["digest"])
                with open(path, "wb") as f:
                    f.write(plus["data"])
            except IOError as e:
                log.info("Cannot store file in cache: %s" % repr(e))
                pass
        self._got_file(plus)

    def _got_file(self, plus):
        """Callback for get_file when the file is taken from the
        local cache.

        plus (dict): a dictionary with the fields: path, digest,
                     callback, plus, data, error

        """
        callback = plus["callback"]
        if plus["error"] != None:
            logger.error(plus["error"])
            if callback != None:
                callback(None, plus["plus"], plus["error"])
        else:
            if plus["path"] != None:
                try:
                    with open(plus["path"], "wb") as f:
                        f.write(plus["data"])
                except IOError as e:
                    if callback != None:
                        callback(None, plus["plus"], repr(e))
                    return
            callback(plus["data"], plus["plus"], plus["error"])

        # Do not call me again:
        return False

    def put_file(self, data=None, path=None, callback=None, plus=None):
        """Send a file to FileStorage, and keep a copy locally.

        data (string): the content of the file to send
        path (string): the file to send
        callback (function): to be called with the digest of the file
        plus (object): additional data for the callback

        """
        if (data == None and path == None) or \
               (data != None and path != None):
            logger.error("No content (or too many) specified in put_file.")
            raise ValueError

        temp_path = os.path.join(self.tmp_dir, random_string(16))
        new_plus = {"callback": callback,
                    "plus": plus,
                    "temp_path": temp_path
                    }
        if path != None:
            # If we cannot store locally the file, we do not report
            # errors
            try:
                shutil.copy(path, temp_path)
            except IOError:
                pass
            # But if we cannot read the actual data, we are forced to
            # report
            try:
                data = open(path, "rb").read()
            except IOError as e:
                new_plus["error"] = repr(e)
                new_plus["digest"] = None
                self.service.add_timeout(self._put_file_callback, new_plus,
                                         100, immediately=True)
        else:
            # Again, no error for inability of caching locally
            try:
                open(temp_path, "wb").write(data)
            except IOError:
                pass

        self.FS.put_file(binary_data=data,
                         callback=FileCacher._put_file_remote_callback,
                         bind_obj=self,
                         plus = new_plus)

    @rpc_callback
    def _put_file_remote_callback(self, data, plus, error=None):
        """Callback for put_file, obtains the digest and call the
        local callback.

        plus (dict): a dictionary with the fields: callback, plus,
                     temp_path

        """
        plus["digest"] = data
        plus["error"] = error
        self._put_file_callback(plus)

    def _put_file_callback(self, plus):
        """Callback for put_file, move the temporary file to the right
        place in the cache and call the real callback with the digest.

        plus (dict): a dictionary with the fields: digest,
                     callback, plus, error, temp_path

        """
        if plus["error"] != None:
            logger.error(plus["error"])
            if callback != None:
                callback(None, plus["plus"], plus["error"])
        else:
            shutil.move(plus["temp_path"],
                        os.path.join(self.obj_dir, plus["digest"]))
            callback(plus["digest"], plus["plus"], None)

        # Do not call me again:
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        FileStorage(shard=int(sys.argv[1]), base_dir="fs").run()

