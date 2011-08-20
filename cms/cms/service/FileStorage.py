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

import tempfile
import shutil
import codecs
import hashlib

from cms.async.AsyncLibrary import Service, \
     rpc_method, rpc_binary_response, rpc_callback, \
     logger, sync_call
from cms.async import ServiceCoord, Address
from cms.service.Utils import mkdir, random_string


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

        if not mkdir(self.base_dir) or \
           not mkdir(self.tmp_dir) or \
           not mkdir(self.obj_dir) or \
           not mkdir(self.desc_dir):
            logger.critical("Cannot create necessary directories.")
            self.exit()

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
        temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
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
        logger.info("Getting file %s." % digest)
        # Errors are managed by the caller
        input_file = open(os.path.join(self.obj_dir, digest), "rb")
        data = input_file.read()
        logger.debug("File with digest %s and description `%s' retrieved" %
                     (digest, self.describe(digest)))
        return data

    @rpc_method
    def delete(self, digest):
        logger.debug("FileStorage.delete")
        logger.info("Deleting file %s." % digest)
        try:
            os.remove(os.path.join(self.desc_dir, digest))
            os.remove(os.path.join(self.obj_dir, digest))
        except IOError:
            return False
        return True

    @rpc_method
    def is_file_present(self, digest):
        logger.debug("FileStorage.is_file_present")
        return os.path.exists(os.path.join(self.obj_dir, digest))

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

    ## GET ##

    def _get_from_cache(self, digest):
        """Check if a file is present in the local cache.

        digest (string): the sha1 sum of the file
        returns (file): the cached open file, or None; the caller is responsible
        for closing it

        """
        try:
            cached_file = open(os.path.join(self.obj_dir, digest), "rb")
            return cached_file
        except IOError:
            return None

    def get_file(self, digest, path=None, callback=None,
                 plus=None, bind_obj=None):
        """Get a file from the cache or from the service if not
        present.

        digest (string): the sha1 sum of the file
        path (string): a path where to save the file
        callback (function): to be called with the open file
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCacher)
        return (bool): True if request got passed along

        """
        from_cache = self._get_from_cache(digest)
        if bind_obj is None:
            bind_obj = self.service
        new_plus = {"path": path,
                    "digest": digest,
                    "callback": callback,
                    "plus": plus,
                    "bind_obj": bind_obj}

        if from_cache != None:
            # If there is the file in the cache, maybe it has been
            # deleted remotely. We need to ask.
            new_plus["error"] = None
            new_plus["data"] = from_cache
            self.file_storage.is_file_present(digest=digest,
                bind_obj=self,
                callback=FileCacher._got_file,
                plus=new_plus)
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
        if error == None:
            try:
                path = os.path.join(self.obj_dir, plus["digest"])
                with open(path, "wb") as f:
                    f.write(plus["data"])
            except IOError as e:
                error = repr(e)
        self._got_file(True, plus, error)

    @rpc_callback
    def _got_file(self, data, plus, error=None):
        """Callback for get_file when the file is taken from the local
        cache. This is the callback for the is_file_present request.

        data (bool): if the file is really present in the storage
        plus (dict): a dictionary with the fields: path, digest,
                     callback, plus, data, error

        """
        callback = plus["callback"]
        bind_obj = plus["bind_obj"]
        if error != None:
            logger.error(error)
            if callback != None:
                callback(bind_obj, None, plus["plus"], error)
        elif not data:
            try:
                os.unlink(os.path.join(self.obj_dir, plus["digest"]))
            except OSError:
                pass
            if callback != None:
                callback(bind_obj, None, plus["plus"],
                         "IOError: 2 No such file or directory.")
        else:
            if plus["path"] != None:
                try:
                    with open(plus["path"], "wb") as f:
                        f.write(plus["data"].read())
                except IOError as e:
                    if callback != None:
                        callback(bind_obj, None, plus["plus"], repr(e))
                    return
            if callback != None:
                cached_file = open(os.path.join(self.obj_dir, plus["digest"]), "rb")
                callback(bind_obj, cached_file, plus["plus"], error)

        # Do not call me again:
        return False

    @rpc_callback
    def _got_file_to_string(self, data, plus, error=None):
        """Callback for get_file_to_string that unpacks the file-like object
        to a string representing its content.

        data(file): the file got from get_file()
        plus(dict): a dictionary with the fields: callback, plus, bind_obj

        """
        orig_callback, orig_plus, bind_obj = plus['callback'], plus['plus'], plus['bind_obj']
        if orig_callback != None:
            if error != None:
                orig_callback(bind_obj, None, orig_plus, error)
            else:
                file_content = data.read()
                data.close()
                orig_callback(bind_obj, file_content, orig_plus)

    @rpc_callback
    def _got_file_to_write_file(self, data, plus, error=None):
        """Callback for get_file_to_write_file that copies the content
        of the received file to the specified file-like object.

        data(file): the file got from get_file()
        plus(dict): a dictionary with the fields: callback, plus, bind_obj,
                    file_obj

        """
        orig_callback, orig_plus, bind_obj, file_obj = \
            plus['callback'], plus['plus'], plus['bind_obj'], plus['file_obj']
        if orig_callback != None:
            if error != None:
                orig_callback(bind_obj, None, orig_plus, error)
            else:
                file_content = data.read()
                file_obj.write(file_content)
                orig_callback(bind_obj, file_content, orig_plus)

    ## GET VARIATIONS ##

    def get_file_to_file(self, digest,
                         callback=None, plus=None, bind_obj=None, sync=False):
        """Get a file from the cache or from the service if not
        present. Returns it as a file-like object.

        digest (string): the sha1 sum of the file
        callback (function): to be called with the received
                             file-like object
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCacher)

        """
        args = {'digest': digest}
        return sync_call(function=self.get_file,
                         args=args,
                         callback=callback,
                         plus=plus,
                         bind_obj=bind_obj,
                         sync=sync)

    def get_file_to_write_file(self, digest, file_obj,
                               callback=None, plus=None, bind_obj=None, sync=False):
        """Get a file from the cache or from the service if not
        present. It writes it on a file-like object.

        digest (string): the sha1 sum of the file
        file_obj (file): the file-like object on which to write
                         the received file
        callback (function): to be called upon completion
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCacher)

        """
        if bind_obj is None:
            bind_obj = self.service
        new_plus = {'callback': callback,
                    'plus': plus,
                    'bind_obj': bind_obj,
                    'file_obj': file_obj}

        args = {'digest': digest}
        if not sync:
            return sync_call(function=self.get_file,
                             args=args,
                             callback=FileCacher._got_file_to_write_file,
                             plus=new_plus,
                             bind_obj=self,
                             sync=False)

        else:
            read_file_obj = sync_call(function=self.get_file,
                                      args=args,
                                      sync=True)
            content = read_file_obj.read()
            file_obj.write(content)
            return content

    def get_file_to_path(self, digest, path,
                         callback=None, plus=None, bind_obj=None, sync=False):
        """Get a file from the cache or from the service if not
        present. Returns it by putting it in the specified path.

        digest (string): the sha1 sum of the file
        path (string): the path where to copy the received file
        callback (function): to be called upon completion
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCacher)

        """
        args = {'digest': digest,
                'path': path}
        return sync_call(function=self.get_file,
                         args=args,
                         callback=callback,
                         plus=plus,
                         bind_obj=bind_obj,
                         sync=sync)

    def get_file_to_string(self, digest,
                           callback=None, plus=None, bind_obj=None, sync=False):
        """Get a file from the cache or from the service if not
        present. Returns it as a string.

        digest (string): the sha1 sum of the file
        callback (function): to be called with the received
                             file content
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCacher)

        """
        if bind_obj is None:
            bind_obj = self.service
        new_plus = {'callback': callback,
                    'plus': plus,
                    'bind_obj': bind_obj}

        args = {'digest': digest}
        if not sync:
            return sync_call(function=self.get_file,
                             args=args,
                             callback=FileCacher._got_file_to_string,
                             plus=new_plus,
                             bind_obj=self,
                             sync=False)

        else:
            file_obj = sync_call(function=self.get_file,
                                 args=args,
                                 sync=True)
            content = file_obj.read()
            file_obj.close()
            return content

    ## PUT ##

    def put_file(self, binary_data=None, description="", file_obj=None,
                 path=None, callback=None, plus=None, bind_obj=None):
        """Send a file to FileStorage, and keep a copy locally. The caller has to
        provide exactly one among binary_data, file_obj and path.

        binary_data (string): the content of the file to send
        description (string): a human-readable description of the content
        file_obj (file): the file-like object to send
        path (string): the file to send
        callback (function): to be called with the digest of the file
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCacher)

        """
        if sum(map(lambda x: {True: 1, False: 0}[x is not None],
                   [binary_data, file_obj, path])) != 1:
            logger.error("No content (or too many) specified in put_file.")
            raise ValueError

        if bind_obj is None:
            bind_obj = self.service
        temp_path = os.path.join(self.tmp_dir, random_string(16))
        new_plus = {"callback": callback,
                    "plus": plus,
                    "temp_path": temp_path,
                    "bind_obj": bind_obj
                    }
        if path is not None:
            # If we cannot store locally the file, we do not report
            # errors
            try:
                shutil.copy(path, temp_path)
            except IOError:
                pass
            # But if we cannot read the actual data, we are forced to
            # report
            try:
                binary_data = open(path, "rb").read()
            except IOError as e:
                new_plus["error"] = repr(e)
                new_plus["digest"] = None
                self.service.add_timeout(self._put_file_callback, new_plus,
                                         100, immediately=True)

        elif binary_data is not None:
            # Again, no error for inability of caching locally
            try:
                open(temp_path, "wb").write(binary_data)
            except IOError:
                pass

        else: # file_obj is not None
            binary_data = file_obj.read()
            try:
                open(temp_path, "wb").write(binary_data)
            except IOError:
                pass

        self.file_storage.put_file(binary_data=binary_data,
            description=description,
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
        callback, bind_obj = plus["callback"], plus["bind_obj"]
        if plus["error"] != None:
            logger.error(plus["error"])
            if callback != None:
                callback(bind_obj, None, plus["plus"], plus["error"])
        else:
            shutil.move(plus["temp_path"],
                        os.path.join(self.obj_dir, plus["digest"]))
            callback(bind_obj, plus["digest"], plus["plus"], None)

        # Do not call me again:
        return False

    ## PUT SYNTACTIC SUGARS ##

    def put_file_from_string(self, content, description="",
                             callback=None, plus=None, bind_obj=None, sync=False):
        """Send a file to FileStorage keeping a copy locally. The file is
        obtained from a string.

        This call is actually a syntactic sugar over put_file().

        content (string): the content of the file to send
        description (string): a human-readable description of the content
        callback (function): to be called with the digest of the file
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCached)

        """
        args = {'binary_data': content,
                'description': description}
        return sync_call(function=self.put_file,
                         args=args,
                         callback=callback,
                         plus=plus,
                         bind_obj=bind_obj,
                         sync=sync)

    def put_file_from_file(self, file_obj, description="",
                           callback=None, plus=None, bind_obj=None, sync=False):
        """Send a file to FileStorage keeping a copy locally. The file is
        obtained from a file-like object.

        This call is actually a syntactic sugar over put_file().

        file_obj (file): the file-like object to send
        description (string): a human-readable description of the content
        callback (function): to be called with the digest of the file
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCached)

        """
        args = {'file_obj': file_obj,
                'description': description}
        return sync_call(function=self.put_file,
                         args=args,
                         callback=callback,
                         plus=plus,
                         bind_obj=bind_obj,
                         sync=sync)

    def put_file_from_path(self, path, description="",
                           callback=None, plus=None, bind_obj=None, sync=False):
        """Send a file to FileStorage keeping a copy locally. The file is
        obtained from a file specified by its path.

        This call is actually a syntactic sugar over put_file().

        path (string): the file to send
        description (string): a human-readable description of the content
        callback (function): to be called with the digest of the file
        plus (object): additional data for the callback
        bind_obj (object): context for the callback (None means
                           the service that created the FileCached)

        """
        args = {'path': path,
                'description': description}
        return sync_call(function=self.put_file,
                         args=args,
                         callback=callback,
                         plus=plus,
                         bind_obj=bind_obj,
                         sync=sync)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        FileStorage(shard=int(sys.argv[1]), base_dir="fs").run()

