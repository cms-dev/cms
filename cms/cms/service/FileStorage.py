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
import sys
import time

import tempfile
import shutil
import codecs
import hashlib

from cms.async.AsyncLibrary import Service, \
    rpc_method, rpc_binary_response, rpc_callback, \
    logger
from cms.async import ServiceCoord, Address, Config, \
    make_async, async_response, async_error
from cms.service.Utils import mkdir, random_string


class FileStorage(Service):
    """Offer capabilities of storing and retrieving binary files.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("FileStorage", shard))
        logger.debug("FileStorage.__init__")
        Service.__init__(self, shard)

        # Create server directories
        self.base_dir = os.path.join(Config._data_dir, "fs")
        self.tmp_dir = os.path.join(self.base_dir, "tmp")
        self.obj_dir = os.path.join(self.base_dir, "objects")
        self.desc_dir = os.path.join(self.base_dir, "descriptions")
        logger.info("Using %s as base directory." % self.base_dir)

        if not mkdir(Config._data_dir) or \
               not mkdir(self.base_dir) or \
               not mkdir(self.tmp_dir) or \
               not mkdir(self.obj_dir) or \
               not mkdir(self.desc_dir):
            logger.error("Cannot create necessary directories.")
            self.exit()

        # Remember put operation yet to finish.
        # Format: chunk_ref (= temp_filename) -> (temp_file, hasher).
        self.partial = {}

        self.stats = {"put": [0, 0.0], "get": [0, 0.0]}

    @rpc_method
    def put_file(self, binary_data, description=None,
                 chunk_ref=None, final_chunk=True):
        """Method to put a file in the file storage.

        binary_data (string): the content of the file.
        description (string): a human-readable description of the
                              content of the file (not used
                              internally, just for human convenience).
        chunk_ref (string): None if we are sending the first chunk of
                            a file, the previously got return value if
                            we are sending a middle chunk.
        final_chunk (bool): True if the file ends after the current
                            chunk.
        returns (string): the SHA1 digest of the file

        """
        start_time = time.time()
        logger.debug("FileStorage.put")
        if not final_chunk and description is not None:
            raise ValueError("Description will get lost "
                             "if chunk is not final.")

        # Avoid too long descriptions, that can bloat our logs
        if description is not None and len(description) > 1024:
            log.info("Description '%s...' trimmed because too long." %
                     description[:50])
            description = description[:1024]

        logger.info("New chunk received")

        if chunk_ref is None:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            chunk_ref = temp_filename
            temp_file = os.fdopen(temp_file, "wb")
            hasher = hashlib.sha1()
            if not final_chunk:
                self.partial[chunk_ref] = (temp_file, hasher)

        else:
            if chunk_ref not in self.partial:
                raise KeyError("Chunk reference not found.")
            temp_file, hasher = self.partial[chunk_ref]

        temp_file.write(binary_data)
        hasher.update(binary_data)

        if final_chunk:
            # Close file and move to destination.
            temp_file.close()
            digest = hasher.hexdigest()
            shutil.move(chunk_ref, os.path.join(self.obj_dir, digest))
            if chunk_ref in self.partial:
                del self.partial[chunk_ref]

            # Update description
            with codecs.open(os.path.join(self.desc_dir, digest), "w",
                             "utf-8") as desc_file:
                desc_file.write(description)

            logger.debug("File with digest %s and description `%s' put" %
                         (digest, description))
            self.stats["put"][0] += 1
            self.stats["put"][1] += time.time() - start_time
            logger.info("Calls: %d" % self.stats["put"][0])
            logger.info("Total time: %.3lf" % self.stats["put"][1])
            logger.info("Average time: %.5lf" % (self.stats["put"][1] /
                                                 self.stats["put"][0]))
            self.stats["put"] = [0, 0.0]
            return digest
        else:
            self.stats["put"][0] += 1
            self.stats["put"][1] += time.time() - start_time
            return chunk_ref


    @rpc_method
    @rpc_binary_response
    def get_file(self, digest, start=0, chunk_size=None):
        """Method to get a file from the file storage.

        digest (string): the SHA1 digest of the requested file.
        start (int): where to start to serve file.
        chunk_size (int): how many bytes to serve, or None to serve
                          everything.
        returns (string): the binary string containing the content of
                          the file.

        """
        start_time = time.time()
        logger.debug("FileStorage.get")
        logger.info("Getting file %s." % digest)
        # Errors are managed by the caller
        input_file = open(os.path.join(self.obj_dir, digest), "rb")
        input_file.seek(start)
        if chunk_size is None:
            data = input_file.read()
            logger.debug("File with digest %s and description `%s' "
                         "retrieved" % (digest, self.describe(digest)))
        else:
            data = input_file.read(chunk_size)
            logger.debug("Chunk of file with digest %s, of length %d "
                         "starting from %d, and description `%s' retrieved" %
                         (digest, chunk_size, start, self.describe(digest)))
        self.stats["get"][0] += 1
        self.stats["get"][1] += time.time() - start_time
        if chunk_size is None or len(data) < chunk_size:
            logger.info("Calls: %d" % self.stats["get"][0])
            logger.info("Total time: %.3lf" % self.stats["get"][1])
            logger.info("Average time: %.5lf" % (self.stats["get"][1] /
                                                 self.stats["get"][0]))
            self.stats["get"] = [0, 0.0]
        return data

    @rpc_method
    def delete(self, digest):
        logger.debug("FileStorage.delete")
        logger.info("Deleting file %s." % digest)
        res = True
        try:
            os.remove(os.path.join(self.desc_dir, digest))
        except IOError:
            res = False
        try:
            os.remove(os.path.join(self.obj_dir, digest))
        except IOError:
            res = False
        return res

    @rpc_method
    def is_file_present(self, digest):
        logger.debug("FileStorage.is_file_present")
        return os.path.exists(os.path.join(self.obj_dir, digest))

    @rpc_method
    def describe(self, digest):
        logger.debug("FileStorage.describe")
        try:
            with open(os.path.join(self.desc_dir, digest)) as fd:
                return fd.read().strip()
        except IOError:
            return None


class FileCacher:
    """This class implement a local cache for files obtainable from a
    FileStorage service. This class uses the make_async decorator,
    hence it may be called as the operations it does were
    synchronous. One has to be aware that some other code may be
    executed between the call and the return.

    """

    CHUNK_SIZE = 2**20

    def __init__(self, service, file_storage):
        """Initialization.

        service (Service): the service we are running in.
        file_storage (RemoteService): the local instance of the
                                      FileStorage service.

        """
        self.service = service
        self.file_storage = file_storage
        self.base_dir = os.path.join(
            Config._cache_dir,
            "fs-cache-%s-%d" % (service._my_coord.name,
                                service._my_coord.shard))
        self.tmp_dir = os.path.join(self.base_dir, "tmp")
        self.obj_dir = os.path.join(self.base_dir, "objects")
        if not mkdir(Config._cache_dir) or \
               not mkdir(self.base_dir) or \
               not mkdir(self.tmp_dir) or \
               not mkdir(self.obj_dir):
            logger.error("Cannot create necessary directories.")

    @make_async
    def get_file(self, digest, path=None, file_obj=None,
                 string=False, temp_path=False):
        """Get a file from the cache or from the service if not
        present.

        digest (string): the sha1 sum of the file.
        path (string): a path where to save the file.
        file_obj (file): a handler where to save the file (that is not
                         closed at return).
        string (bool): True to return content as a string.
        temp_path (bool): True to return path of a temporary file with
                          that content. The file is reserved to the
                          caller, who has the duty to unlink it.

        """
        if string and temp_path:
            raise ValueError("Cannot ask for both content and temp path.")

        cache_path = os.path.join(self.obj_dir, digest)
        cache_exists = os.path.exists(cache_path)
        data = None

        if cache_exists:
            # If there is the file in the cache, maybe it has been
            # deleted remotely. We need to ask.
            # TODO: since we never delete files, we could just give
            # the file without checking... and even if we delete file,
            # what's the problem?
            present = yield self.file_storage.is_file_present(digest=digest,
                                                              timeout=True)
            # File not available remotely, deleting from cache.
            if not present:
                try:
                    os.unlink(os.path.join(self.obj_dir, digest))
                except OSError:
                    pass
                yield async_error("IOError: 2 No such file or directory.")
                return

        else:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            temp_file = os.fdopen(temp_file, "wb")
            start = 0
            while True:
                data = yield self.file_storage.get_file(
                    digest=digest, start=start,
                    chunk_size=FileCacher.CHUNK_SIZE, timeout=True)
                if data is None:
                    break
                start += len(data)
                temp_file.write(data)
                if len(data) < FileCacher.CHUNK_SIZE:
                    break
            temp_file.close()
            shutil.move(temp_filename, cache_path)

        # Saving to path
        if path is not None:
            shutil.copy(cache_path, path)

        # Saving to file object
        if file_obj is not None:
            with open(cache_path, "rb") as f:
                shutil.copyfileobj(f, file_obj)

        # Returning string?
        if string == True:
            data = open(cache_path, "rb").read()
            yield async_response(data)

        # Returning temporary file?
        elif temp_path == True:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            os.close(temp_file)
            shutil.copy(cache_path, temp_filename)
            yield async_response(temp_filename)

        # Nothing to say otherwise
        else:
            yield async_response(None)

    @make_async
    def put_file(self, binary_data=None, description="",
                 file_obj=None, path=None):
        """Send a file to FileStorage, and keep a copy locally. The
        caller has to provide exactly one among binary_data, file_obj
        and path.

        binary_data (string): the content of the file to send.
        description (string): a human-readable description of the
                              content.
        file_obj (file): the file-like object to send.
        path (string): the file to send.

        """
        temp_path = os.path.join(self.tmp_dir, random_string(16))

        if [binary_data, file_obj, path].count(None) != 2:
            logger.error("No content (or too many) specified in put_file.")
            raise ValueError

        if path is not None:
            # If we cannot store locally the file, we do not report
            # errors.
            try:
                shutil.copy(path, temp_path)
            except IOError:
                pass
            # But if we cannot read the actual data, we are forced to
            # report.
            try:
                binary_data = open(path, "rb").read()
            except IOError as e:
                yield async_error(repr(e))
                return

        elif binary_data is not None:
            # Again, no error for inability of caching locally.
            try:
                open(temp_path, "wb").write(binary_data)
            except IOError:
                pass

        else: # file_obj is not None.
            binary_data = file_obj.read()
            try:
                open(temp_path, "wb").write(binary_data)
            except IOError:
                pass

        try:
            chunk_ref = None
            while len(binary_data) > FileCacher.CHUNK_SIZE:
                data = binary_data[:FileCacher.CHUNK_SIZE]
                binary_data = binary_data[FileCacher.CHUNK_SIZE:]
                chunk_ref = yield self.file_storage.put_file(
                    binary_data=data, chunk_ref=chunk_ref,
                    final_chunk=False, timeout=True)
            digest = yield self.file_storage.put_file(
                binary_data=binary_data, description=description,
                chunk_ref=chunk_ref, final_chunk=True, timeout=True)
            shutil.move(temp_path,
                        os.path.join(self.obj_dir, digest))
            yield async_response(digest)
        except Exception as e:
            yield async_error(repr(e))

    @make_async
    def describe(self, digest):
        """Return the description of a file given its digest. This
        request is not actually cached, since is mostly meant for
        debugging purposes and it isn't used by the contest system
        itself.

        digest (string): the digest to describe.
        return (string): the description associated.

        """
        yield self.file_storage.describe(digest=digest)

    @make_async
    def delete(self, digest):
        """Delete from cache and FS the file with that digest.

        digest (string): the file to delete.

        """
        self.delete_from_cache(digest)
        yield self.file_storage.delete(digest=digest, timeout=True)

    def delete_from_cache(self, digest):
        """Delete the specified file from the local cache.

        digest (string): the file to delete.

        """
        os.unlink(os.path.join(self.obj_dir, digest))


def main():
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        FileStorage(shard=int(sys.argv[1])).run()


if __name__ == "__main__":
    main()
