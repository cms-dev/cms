#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import tempfile
import shutil
import hashlib

from cms import config, logger, mkdir
from cms.db.SQLAlchemyAll import SessionGen, FSObject

from sqlalchemy.exc import IntegrityError


class FileCacherBackend:

    def __init__(self, service=None):
        """Initialization.

        service (Service): the service we are running in. If None, we
                           simply avoid caching and allowing the
                           service to step in once in a while.

        """
        self.service = service

    def get_file(self, digest, dest):
        """Retrieve a file from the storage. If the requested digest
        isn't available in the storage, raise an exception.

        digest (string): the digest of the file to retrieve.
        dest (string): the location where to put the retrieved file;
                       it musn't exist and it will be created by
                       get_file().

        """
        raise NotImplementedError("Please subclass this class.")

    def put_file(self, digest, origin, description=""):
        """Put a file to the storage.

        digest (string): the digest that the file will receive.
        origin (string): the location from where to get the file to be
                         sent to the storage; it musn't be destroyed
                         or modified by put_file().
        description (string): the optional description of the file to
                              store, intended for human beings.

        """
        raise NotImplementedError("Please subclass this class.")

    def describe(self, digest):
        """Return the description of a file given its digest.

        digest (string): the digest to describe.

        returns (string): the description associated.

        """
        raise NotImplementedError("Please subclass this class.")

    def get_size(self, digest):
        """Return the size of a file given its digest.

        digest (string): the digest of which to calculate the size.

        returns (int): the size of the file.

        """
        raise NotImplementedError("Please subclass this class.")

    def delete(self, digest):
        """Delete a file from the storage.

        digest (string): the file to delete.

        """
        raise NotImplementedError("Please subclass this class.")

    def list(self):
        """List the files available in the storage.

        return (list): a list of tuples, each representing a file in
                       the form (digest, description).

        """
        raise NotImplementedError("Please subclass this class.")


class FSBackend(FileCacherBackend):
    """This class implements a backend for FileCacher that keeps all
    the files in a file system directory, named after their digest. Of
    course this directory can be shared, for example with NFS, acting
    as an actual remote file storage.

    TODO: Actually store the descriptions, that get discarded at the
    moment.

    TODO: Use an additional level of directories, to alleviate the
    work of the file system driver (e.g., 'ROOT/a/abcdef...' instead
    of 'ROOT/abcdef...'.

    """
    def __init__(self, path, service=None):
        """Initialization.

        path (string): the base path for the storage.
        service (Service): as in FileCacherBackend.__init__().

        """
        FileCacherBackend.__init__(self, service)
        self.path = path

        # Create the directory if it doesn't exist
        try:
            os.makedirs(self.path)
        except OSError:
            pass

    def get_file(self, digest, dest):
        """See FileCacherBackend.get_file().

        """
        shutil.copyfile(os.path.join(self.path, digest), dest)

    def put_file(self, digest, origin, description=""):
        """See FileCacherBackend.put_file().

        """
        if not os.path.exists(os.path.join(self.path, digest)):
            shutil.copyfile(origin, os.path.join(self.path, digest))

    def describe(self, digest):
        """See FileCacherBackend.describe(). This method returns
        nothing, because FSBackend doesn't store the description.

        """
        return ''

    def get_size(self, digest):
        """See FileCacherBackend.get_size().

        """
        return os.stat(os.path.join(self.path, digest)).st_size

    def delete(self, digest):
        """See FileCacherBackend.delete().

        """
        try:
            os.unlink(os.path.join(self.path, digest))
        except OSError:
            pass

    def list(self, digest):
        """See FileCacherBackend.list().

        """
        return map(lambda x: (x, ''), os.listdir(self.path))


class DBBackend(FileCacherBackend):
    """This class implements an actual backend for FileCacher that
    stores the files as lobjects (encapsuled in a FSObject) into a
    PostgreSQL database.

    """
    CHUNK_SIZE = 2 ** 20

    def get_file(self, digest, dest):
        """See FileCacherBackend.get_file().

        """
        with open(dest, 'wb') as temp_file:
            # hasher = hashlib.sha1()
            with SessionGen() as session:
                fso = FSObject.get_from_digest(digest, session)

                # Copy the file into the lobject
                with fso.get_lobject(mode='rb') as lobject:
                    buf = lobject.read(self.CHUNK_SIZE)
                    while buf != '':
                        # hasher.update(buf)
                        temp_file.write(buf)
                        if self.service is not None:
                            self.service._step()
                        buf = lobject.read(self.CHUNK_SIZE)

    def put_file(self, digest, origin, description=""):
        """See FileCacherBackend.put_file().

        """
        try:
            with SessionGen() as session:

                # Check digest uniqueness
                if FSObject.get_from_digest(digest, session) is not None:
                    logger.debug("File %s already on database, "
                                 "dropping this one." % digest)
                    session.rollback()

                # If it is not already present, copy the file into the
                # lobject
                else:
                    fso = FSObject(description=description)
                    logger.debug("Sending file %s to the database." % digest)
                    with open(origin, 'rb') as temp_file:
                        with fso.get_lobject(session, mode='wb') as lobject:
                            logger.debug("Large object created.")
                            buf = temp_file.read(self.CHUNK_SIZE)
                            while buf != '':
                                while len(buf) > 0:
                                    written = lobject.write(buf)
                                    buf = buf[written:]
                                    if self.service is not None:
                                        self.service._step()
                                buf = temp_file.read(self.CHUNK_SIZE)
                    fso.digest = digest
                    session.add(fso)
                    session.commit()
                    logger.debug("File %s sent to the database." % digest)

        except IntegrityError:
            logger.info("File %s caused an IntegrityError, ignoring..." % digest)


    def describe(self, digest):
        """See FileCacherBackend.describe().

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)
            if fso is not None:
                return fso.description
            else:
                return None

    def get_size(self, digest):
        """See FileCacherBackend.get_size().

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)
            if fso is not None:
                with fso.get_lobject(session, mode='rb') as lobject:
                    return lobject.seek(0, os.SEEK_END)
            else:
                return None

    def delete(self, digest):
        """See FileCacherBackend.delete().

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)
            fso.delete()
            session.commit()

    def list(self, session=None):
        """See FileCacherBackend.list(). This implementation also
        accept an additional session parameter.

        session (Session): if specified, use that session instead of
                           creating a new one.

        """
        def _list(session):
            """Do the work assuming session is valid.

            """
            return map(lambda x: (x.digest, x.description),
                       session.query(FSObject))

        if session is not None:
            return _list(session)
        else:
            with SessionGen() as session:
                return _list(session)


class FileCacher:
    """This class implement a local cache for files stored as FSObject
    in the database.

    """
    CHUNK_SIZE = 2 ** 20

    def __init__(self, service=None, path=None):
        """Initialization.

        service (Service): the service we are running in. If None, we
                           simply avoid caching and allowing the
                           service to step in once in a while.
        path (string): if specified, back the FileCacher with a file
                       system-based storage instead that the default
                       database-based one. The specified directory
                       will be used as root for the storage and it
                       will be created if it doesn't exist.

        """
        self.service = service
        if path is None:
            self.backend = DBBackend(self.service)
        else:
            self.backend = FSBackend(path, self.service)
        if self.service is None:
            self.base_dir = tempfile.mkdtemp(dir=config.temp_dir)
        else:
            self.base_dir = os.path.join(
                config.cache_dir,
                "fs-cache-%s-%d" % (service._my_coord.name,
                                    service._my_coord.shard))
        self.tmp_dir = os.path.join(self.base_dir, "tmp")
        self.obj_dir = os.path.join(self.base_dir, "objects")
        if not mkdir(config.cache_dir) or \
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

        logger.debug("Getting file %s" % (digest))

        if not cache_exists:
            logger.debug("File %s not in cache, downloading "
                         "from database." % digest)

            # Receives the file from the database
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            temp_file = os.fdopen(temp_file, "wb")
            self.backend.get_file(digest, temp_filename)

            # And move it in the cache. Warning: this is not atomic if
            # the temp and the cache dir are on different filesystems.
            shutil.move(temp_filename, cache_path)

            logger.debug("File %s downloaded." % digest)

        # Saving to path
        if path is not None:
            shutil.copy(cache_path, path)

        # Saving to file object
        if file_obj is not None:
            with open(cache_path, "rb") as file_:
                shutil.copyfileobj(file_, file_obj)

        # Returning string?
        if string:
            with open(cache_path, "rb") as cache_file:
                return cache_file.read()

        # Returning temporary file?
        elif temp_path:
            temp_file, temp_filename = tempfile.mkstemp(dir=self.tmp_dir)
            os.close(temp_file)
            shutil.copy(cache_path, temp_filename)
            return temp_filename

        # Returning temporary file object?
        elif temp_file_obj:
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
            error_string = "No content (or too many) specified in put_file."
            logger.error(error_string)
            raise ValueError(error_string)

        logger.debug("Reading input file to store on the database.")

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
        else:  # file_obj is not None.
            with open(temp_path, 'wb') as temp_file:
                shutil.copyfileobj(file_obj, temp_file)

        hasher = hashlib.sha1()

        # Calculate the file SHA1 digest
        with open(temp_path, 'rb') as temp_file:
            buf = temp_file.read(self.CHUNK_SIZE)
            while buf != '':
                hasher.update(buf)
                buf = temp_file.read(self.CHUNK_SIZE)
        digest = hasher.hexdigest()

        logger.debug("File has digest %s." % digest)

        self.backend.put_file(digest, temp_path, description=description)

        # Move the temporary file in the cache
        shutil.move(temp_path,
                    os.path.join(self.obj_dir, digest))

        return digest

    def describe(self, digest):
        """Return the description of a file given its digest.

        digest (string): the digest to describe.

        returns (string): the description associated.

        """
        return self.backend.describe(digest)

    def get_size(self, digest):
        """Return the size of a file given its digest.

        digest (string): the digest of which to calculate the size.

        returns (int): the size of the file.

        """
        return self.backend.get_size(digest)

    def delete(self, digest):
        """Delete from cache and FS the file with that digest.

        digest (string): the file to delete.

        """
        self.delete_from_cache(digest)
        self.backend.delete(digest)

    def delete_from_cache(self, digest):
        """Delete the specified file from the local cache.

        digest (string): the file to delete.

        """
        try:
            os.unlink(os.path.join(self.obj_dir, digest))
        except OSError:
            pass

    def purge_cache(self):
        """Delete all the content of the cache.

        """
        shutil.rmtree(self.base_dir)
        if not mkdir(config.cache_dir) or \
               not mkdir(self.base_dir) or \
               not mkdir(self.tmp_dir) or \
               not mkdir(self.obj_dir):
            logger.error("Cannot create necessary directories.")

    def list(self):
        """List the files available in the storage.

        """
        return self.backend.list()
