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

import sys
import os

import tempfile
import shutil
import codecs
import hashlib

from AsyncLibrary import Service, rpc_method, rpc_binary_response, logger
from Utils import ServiceCoord, Address


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
        ret = ret and self._mkdir(self.base_dir)
        ret = ret and self._mkdir(self.tmp_dir)
        ret = ret and self._mkdir(self.obj_dir)
        ret = ret and self._mkdir(self.desc_dir)
        if not ret:
            logger.critical("Cannot create necessary directories.")


    def _mkdir(self, path):
        """Make a directory without complaining for errors.

        path (string): the path of the directory to create
        returns (bool): True if the dir is ok, False if it is not

        """
        logger.debug("FileStorage._mkdir")
        try:
            os.mkdir(path)
            return True
        except OSError:
            if os.path.isdir(path):
                return True
        logger.error("Cannot create directory %s" % path)
        return False

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
        logger.info("New file added: %s" % description)

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
        logger.debug("FileStorage.get")
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        FileStorage(shard=int(sys.argv[1]), base_dir="fs").run()

