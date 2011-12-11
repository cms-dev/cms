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

"""Cache to store and retrieve files, assumed to be binary.

"""

import os
import sys
import time

import tempfile
import shutil
import codecs
import hashlib

from cms import Config
from cms.db.SQLAlchemyAll import SessionGen, FSObject
from cms.service.Utils import mkdir, random_string


class FileCacher:
    """This class implement a local cache for files stored as FSObject
    in the database.

    """

    CHUNK_SIZE = 2**20

    def __init__(self, service):
        """Initialization.

        service (Service): the service we are running in.

        """
        self.service = service
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

    def get_file(self, digest, path=None, file_obj=None,
                 string=False, temp_path=False, temp_file_obj=False):
        """Get a file from the storage, possibly using the cache if
        the file is available there.

        digest (string): the sha1 sum of the file.
        path (string): a path where to save the file.
        file_obj (file): a handler where to save the file (that is not
                         closed at return).
        string (bool): True to return content as a string.
        temp_path (bool): True to return path of a temporary file with
                          that content. The file is reserved to the
                          caller, who has the duty to unlink it.
        temp_file-obj (bool): True to return a file object opened to a
                              temporary file with that content. The
                              file is reserved to the caller. Use this
                              method only for debugging purpose, as it
                              leave a file lying in the temporary
                              directory of FileCacher.

        """
        if [string, temp_path, temp_file_obj].count(True) > 1:
            raise ValueError("Ask for at most one amongst content, "
                             "temp path and temp file obj.")

        cache_path = os.path.join(self.obj_dir, digest)
        cache_exists = os.path.exists(cache_path)
        data = None

        if not cache_exists:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            temp_file = os.fdopen(temp_file, "wb")

            # Receives the file from the database
            with open(temp_filename, 'wb') as temp_file:
                #hasher = hashlib.sha1()
                with SessionGen() as session:
                    fso = FSObject.get_from_digest(digest, session)

                    # Copy the file into the lobject
                    with fso.get_lobject(mode='rb') as lo:
                        buf = lo.read(self.CHUNK_SIZE) 
                        while buf != '':
                            #hasher.update(buf)
                            temp_file.write(buf)
                            self.service._step()
                            buf = lo.read(self.CHUNK_SIZE)

            # And move it in the cache
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
            with open(cache_path, "rb") as cache_file:
                return cache_file.read()

        # Returning temporary file?
        elif temp_path == True:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            os.close(temp_file)
            shutil.copy(cache_path, temp_filename)
            return temp_filename

        # Returning temporary file object?
        elif temp_file_obj == True:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            os.close(temp_file)
            shutil.copy(cache_path, temp_filename)
            temp_file = open(temp_filename, "rb")
            return temp_file

    def put_file(self, description="", binary_data=None,
                 file_obj=None, path=None):
        """Put a file in the storage, and keep a copy locally. The
        caller has to provide exactly one among binary_data, file_obj
        and path.

        description (string): a human-readable description of the
                              content.
        binary_data (string): the content of the file to send.
        file_obj (file): the file-like object to send.
        path (string): the file to send.

        """
        temp_fd, temp_path = tempfile.mkstemp(dir=self.tmp_dir)
        os.close(temp_fd)

        # Input checking
        if [binary_data, file_obj, path].count(None) != 2:
            logger.error("No content (or too many) specified in put_file.")
            raise ValueError

        # Copy the file content, whatever forms it arrives, into the
        # temporary file
        # TODO - This could be long lasting: probably it would be wise
        # to call self.service._step() periodically, but this would
        # require reimplementing of shutil functions
        if path is not None:
            shutil.copy(path, temp_path)
        elif binary_data is not None:
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(binary_data)
        else: # file_obj is not None.
            with open(temp_path, 'wb') as temp_file:
                shutil.copyfileobj(file_obj, temp_file)

        # (Re)open the temporary file and send it to the database
        with open(temp_path, 'rb') as temp_file:
            hasher = hashlib.sha1()
            fso = FSObject(description=description)
            with SessionGen() as session:

                # Copy the file into the lobject
                with fso.get_lobject(session, mode='wb') as lo:
                    buf = temp_file.read(self.CHUNK_SIZE) 
                    while buf != '':
                        hasher.update(buf)
                        while len(buf) > 0:
                            written = lo.write(buf)
                            buf = buf[written:]
                            self.service._step()
                        buf = temp_file.read(self.CHUNK_SIZE)

                # Check the digest uniqueness
                # TODO - This is done after the file has been
                # uploaded; we could save bandwidth if the digest were
                # computed before, but then we need to process the
                # file twice; which one is better?
                digest = hasher.hexdigest()
                if FSObject.get_from_digest(digest, session) is not None:
                    # Apparently the rollback also deletes the loaded
                    # large object, which is good
                    session.rollback()

                else:
                    fso.digest = digest
                    session.add(fso)
                    session.commit()

        # Move the temporary file in the cache
        shutil.move(temp_path,
                    os.path.join(self.obj_dir, digest))

        return digest


    def describe(self, digest):
        """Return the description of a file given its digest.

        digest (string): the digest to describe.
        return (string): the description associated.

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)
            if fso is not None:
                return fso.description
            else:
                return None

    def delete(self, digest):
        """Delete from cache and FS the file with that digest.

        digest (string): the file to delete.

        """
        self.delete_from_cache(digest)
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)
            with fso.get_lobject() as lo:
                lo.unlink()
            session.delete(fso)
            session.commit()

    def delete_from_cache(self, digest):
        """Delete the specified file from the local cache.

        digest (string): the file to delete.

        """
        try:
            os.unlink(os.path.join(self.obj_dir, digest))
        except OSError:
            pass

    def list(self, session=None):
        """List the files available in the storage.

        """
        def _list(session):
            return map(lambda x: (x.digest, x.description), session.query(FSObject))

        if session is not None:
            return _list(session)
        else:
            with SessionGen() as session:
                return _list(session)

def main():
    global ls, fc, Session
    from cms.db.SQLAlchemyAll import Session, metadata
    metadata.create_all()
    from cms.service import LogService
    ls = LogService.LogService(0)
    fc = FileCacher(ls)
    #fc.put_file(description="ciao", path="/etc/resolv.conf")

if __name__ == '__main__':
    main()
