#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import io
import logging
import os
import tempfile

import gevent

from sqlalchemy.exc import IntegrityError

from cms import config, mkdir
from cms.db import SessionGen, FSObject
from cms.io.GeventUtils import copyfileobj, move, rmtree


logger = logging.getLogger(__name__)


class FileCacherBackend(object):
    """Abstract base class for all FileCacher backends.

    """

    def get_file(self, digest):
        """Retrieve a file from the storage.

        digest (unicode): the digest of the file to retrieve.

        return (fileobj): a readable binary file-like object from which
            to read the contents of the file.

        raise (KeyError): if the file cannot be found.

        """
        raise NotImplementedError("Please subclass this class.")

    def put_file(self, digest, desc=""):
        """Store a file to the storage.

        digest (unicode): the digest of the file to store.
        desc (unicode): the optional description of the file to
            store, intended for human beings.

        return (fileobj): a writable binary file-like object on which
            to write the contents of the file, or None if the file is
            already stored.

        """
        raise NotImplementedError("Please subclass this class.")

    def describe(self, digest):
        """Return the description of a file given its digest.

        digest (unicode): the digest of the file to describe.

        return (unicode): the description of the file.

        raise (KeyError): if the file cannot be found.

        """
        raise NotImplementedError("Please subclass this class.")

    def get_size(self, digest):
        """Return the size of a file given its digest.

        digest (unicode): the digest of the file to calculate the size
            of.

        return (int): the size of the file, in bytes.

        raise (KeyError): if the file cannot be found.

        """
        raise NotImplementedError("Please subclass this class.")

    def delete(self, digest):
        """Delete a file from the storage.

        digest (unicode): the digest of the file to delete.

        """
        raise NotImplementedError("Please subclass this class.")

    def list(self):
        """List the files available in the storage.

        return ([(unicode, unicode)]): a list of pairs, each
            representing a file in the form (digest, description).

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

    def __init__(self, path):
        """Initialize the backend.

        path (string): the base path for the storage.

        """
        self.path = path

        # Create the directory if it doesn't exist
        try:
            os.makedirs(self.path)
        except OSError:
            pass

    def get_file(self, digest):
        """See FileCacherBackend.get_file().

        """
        file_path = os.path.join(self.path, digest)

        if not os.path.exists(file_path):
            raise KeyError("File not found.")

        return io.open(file_path, 'rb')

    def put_file(self, digest, desc=""):
        """See FileCacherBackend.put_file().

        """
        file_path = os.path.join(self.path, digest)

        if os.path.exists(file_path):
            return None

        return io.open(file_path, 'wb')

    def describe(self, digest):
        """See FileCacherBackend.describe().

        """
        file_path = os.path.join(self.path, digest)

        if not os.path.exists(file_path):
            raise KeyError("File not found.")

        return ""

    def get_size(self, digest):
        """See FileCacherBackend.get_size().

        """
        file_path = os.path.join(self.path, digest)

        if not os.path.exists(file_path):
            raise KeyError("File not found.")

        return os.stat(file_path).st_size

    def delete(self, digest):
        """See FileCacherBackend.delete().

        """
        file_path = os.path.join(self.path, digest)

        try:
            os.unlink(file_path)
        except OSError:
            pass

    def list(self):
        """See FileCacherBackend.list().

        """
        return list((x, "") for x in os.listdir(self.path))


class DBBackend(FileCacherBackend):
    """This class implements an actual backend for FileCacher that
    stores the files as lobjects (encapsuled in a FSObject) into a
    PostgreSQL database.

    """

    def get_file(self, digest):
        """See FileCacherBackend.get_file().

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)

            if fso is None:
                raise KeyError("File not found.")

            return fso.get_lobject(mode='rb')

    def put_file(self, digest, desc=""):
        """See FileCacherBackend.put_file().

        """
        try:
            with SessionGen() as session:
                fso = FSObject.get_from_digest(digest, session)

                # Check digest uniqueness
                if fso is not None:
                    logger.debug("File %s already stored on database, not "
                                 "sending it again." % digest)
                    session.rollback()
                    return None

                # If it is not already present, copy the file into the
                # lobject
                else:
                    fso = FSObject(description=desc)
                    fso.digest = digest

                    session.add(fso)

                    logger.debug("File %s stored on the database." % digest)

                    # FIXME There is a remote possibility that someone
                    # will try to access this file, believing it has
                    # already been stored (since its FSObject exists),
                    # while we're still sending its content.

                    lobject = fso.get_lobject(mode='wb')

                    session.commit()

                    return lobject

        except IntegrityError:
            logger.warning("File %s caused an IntegrityError, ignoring..." %
                           digest)

    def describe(self, digest):
        """See FileCacherBackend.describe().

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)

            if fso is None:
                raise KeyError("File not found.")

            return fso.description

    def get_size(self, digest):
        """See FileCacherBackend.get_size().

        """
        # TODO - The business logic may be moved in FSObject, for
        # better generality
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)

            if fso is None:
                raise KeyError("File not found.")

            with fso.get_lobject(mode='rb') as lobj:
                return lobj.seek(0, io.SEEK_END)

    def delete(self, digest):
        """See FileCacherBackend.delete().

        """
        with SessionGen() as session:
            fso = FSObject.get_from_digest(digest, session)

            if fso is None:
                session.rollback()
                return

            fso.delete()

            session.commit()

    def list(self, session=None):
        """See FileCacherBackend.list().

        This implementation also accepts an additional (and optional)
        parameter: a SQLAlchemy session to use to query the database.

        session (Session|None): the session to use; if not given a
            temporary one will be created and used.

        """
        def _list(session):
            """Do the work assuming session is valid.

            """
            return list((x.digest, x.description)
                        for x in session.query(FSObject))

        if session is not None:
            return _list(session)
        else:
            with SessionGen() as session:
                return _list(session)


class NullBackend(FileCacherBackend):
    """This backend is always empty, it just drops each file that
    receives. It looks mostly like /dev/null. It is useful when you
    want to just rely on the caching capabilities of FileCacher for
    very short-lived and local storages.

    """

    def get_file(self, digest):
        raise KeyError("File not found.")

    def put_file(self, digest, desc=""):
        return None

    def describe(self, digest):
        raise KeyError("File not found.")

    def get_size(self, digest):
        raise KeyError("File not found.")

    def delete(self, digest):
        pass

    def list(self):
        return list()


class FileCacher(object):
    """This class implement a local cache for files stored as FSObject
    in the database.

    """

    # This value is very arbitrary, and in this case we want it to be a
    # one-size-fits-all, since we use it for many conversions. It has
    # been chosen arbitrarily based on performance tests on my machine.
    # A few consideration on the value it could assume follow:
    # - The page size of large objects is LOBLKSIZE, which is BLCKSZ/4
    #   (BLCKSZ is the block size of the PostgreSQL database, which is
    #   set during pre-build configuration). BLCKSZ is by default 8192,
    #   therefore LOBLKSIZE is 2048. See:
    #   http://www.postgresql.org/docs/9.0/static/catalog-pg-largeobject.html
    # - The `io' module defines a DEFAULT_BUFFER_SIZE constant, whose
    #   value is 8192.
    # CHUNK_SIZE should be a multiple of these values.
    CHUNK_SIZE = 2 ** 14  # 16348

    def __init__(self, service=None, path=None, null=False):
        """Initialize.

        By default the database-powered backend will be used, but this
        can be changed using the parameters.

        service (Service|None): the service we are running for. Only
            used if present to determine the location of the
            file-system cache (and to provide the shard number to the
            Sandbox... sigh!).
        path (string|None): if specified, back the FileCacher with a
            file system-based storage instead of the default
            database-based one. The specified directory will be used
            as root for the storage and it will be created if it
            doesn't exist.
        null (bool): if True, back the FileCacher with a NullBackend,
            that just discards every file it receives. This setting
            takes priority over path.

        """
        self.service = service

        if null:
            self.backend = NullBackend()
        elif path is None:
            self.backend = DBBackend()
        else:
            self.backend = FSBackend(path)

        if service is None:
            self.file_dir = tempfile.mkdtemp(dir=config.temp_dir)
        else:
            self.file_dir = os.path.join(
                config.cache_dir,
                "fs-cache-%s-%d" % (service.name, service.shard))

        self.temp_dir = os.path.join(self.file_dir, "_temp")

        if not mkdir(config.cache_dir) or not mkdir(self.file_dir) \
                or not mkdir(self.temp_dir):
            logger.error("Cannot create necessary directories.")
            raise RuntimeError("Cannot create necessary directories.")

    def load(self, digest):
        """Load the file with the given digest into the cache.

        Ask the backend to provide the file and, if it's available,
        copy its content into the file-system cache.

        digest (unicode): the digest of the file to load.

        raise (KeyError): if the backend cannot find the file.

        """
        ftmp_handle, temp_file_path = tempfile.mkstemp(dir=self.temp_dir,
                                                       text=False)
        ftmp = os.fdopen(ftmp_handle, 'w')
        cache_file_path = os.path.join(self.file_dir, digest)

        fobj = self.backend.get_file(digest)

        # Copy the file to a temporary position
        try:
            copyfileobj(fobj, ftmp, self.CHUNK_SIZE)
        finally:
            ftmp.close()
            fobj.close()

        # Then move it to its real location (this operation is atomic
        # by POSIX requirement)
        os.rename(temp_file_path, cache_file_path)

    def get_file(self, digest):
        """Retrieve a file from the storage.

        If it's available in the cache use that copy, without querying
        the backend. Otherwise ask the backend to provide it, and store
        it in the cache for the benefit of future accesses.

        The file is returned as a file-object. Other interfaces are
        available as `get_file_content', `get_file_to_fobj' and `get_
        file_to_path'.

        digest (unicode): the digest of the file to get.

        return (fileobj): a readable binary file-like object from which
            to read the contents of the file.

        raise (KeyError): if the file cannot be found.

        """
        cache_file_path = os.path.join(self.file_dir, digest)

        logger.debug("Getting file %s." % digest)

        if not os.path.exists(cache_file_path):
            logger.debug("File %s not in cache, downloading "
                         "from database." % digest)

            self.load(digest)

            logger.debug("File %s downloaded." % digest)

        return io.open(cache_file_path, 'rb')

    def get_file_content(self, digest):
        """Retrieve a file from the storage.

        See `get_file'. This method returns the content of the file, as
        a binary string.

        digest (unicode): the digest of the file to get.

        return (bytes): the content of the retrieved file.

        raise (KeyError): if the file cannot be found.

        """
        with self.get_file(digest) as src:
            return src.read()

    def get_file_to_fobj(self, digest, dst):
        """Retrieve a file from the storage.

        See `get_file'. This method will write the content of the file
        to the given file-object.

        digest (unicode): the digest of the file to get.
        dst (fileobj): a writable binary file-like object on which to
            write the contents of the file.

        raise (KeyError): if the file cannot be found.

        """
        with self.get_file(digest) as src:
            copyfileobj(src, dst, self.CHUNK_SIZE)

    def get_file_to_path(self, digest, dst_path):
        """Retrieve a file from the storage.

        See `get_file'. This method will write the content of a file
        to the given file-system location.

        digest (unicode): the digest of the file to get.
        dst_path (string): an accessible location on the file-system on
            which to write the contents of the file.

        raise (KeyError): if the file cannot be found.

        """
        with self.get_file(digest) as src:
            with io.open(dst_path, 'wb') as dst:
                copyfileobj(src, dst, self.CHUNK_SIZE)

    def save(self, digest, desc=""):
        """Save the file with the given digest into the backend.

        Use to local copy, available in the file-system cache, to store
        the file in the backend, if it's not already there.

        digest (unicode): the digest of the file to load.
        desc (unicode): the (optional) description to associate to the
            file.

        """
        cache_file_path = os.path.join(self.file_dir, digest)

        fobj = self.backend.put_file(digest, desc)

        if fobj is None:
            return

        try:
            with io.open(cache_file_path, 'rb') as src:
                copyfileobj(src, fobj, self.CHUNK_SIZE)
        finally:
            fobj.close()

    def put_file_from_fobj(self, src, desc=""):
        """Store a file in the storage.

        If it's already (for some reason...) in the cache send that
        copy to the backend. Otherwise store it in the file-system
        cache first.

        The file is obtained from a file-object. Other interfaces are
        available as `put_file_content', `put_file_from_path'.

        src (fileobj): a readable binary file-like object from which
            to read the contents of the file.
        desc (unicode): the (optional) description to associate to the
            file.

        return (unicode): the digest of the stored file.

        """
        logger.debug("Reading input file to store on the database.")

        # Unfortunately, we have to read the whole file-obj to compute
        # the digest but we take that chance to save it to a temporary
        # path so that we then just need to move it. Hoping that both
        # locations will be on the same filesystem, that should be way
        # faster than reading the whole file-obj again (as it could be
        # compressed or require network communication).
        # XXX We're *almost* reimplementing copyfileobj.
        with tempfile.NamedTemporaryFile('wb', delete=False,
                                         dir=config.temp_dir) as dst:
            hasher = hashlib.sha1()
            buf = src.read(self.CHUNK_SIZE)
            while len(buf) > 0:
                hasher.update(buf)
                while len(buf) > 0:
                    written = dst.write(buf)
                    # Cooperative yield.
                    gevent.sleep(0)
                    if written is None:
                        break
                    buf = buf[written:]
                buf = src.read(self.CHUNK_SIZE)
            digest = hasher.hexdigest().decode("ascii")
            dst.flush()

            logger.debug("File has digest %s." % digest)

            cache_file_path = os.path.join(self.file_dir, digest)

            if not os.path.exists(cache_file_path):
                move(dst.name, cache_file_path)
            else:
                os.unlink(dst.name)

        # Store the file in the backend. We do that even if the file
        # was already in the cache (that is, we ignore the check above)
        # because there's a (small) chance that the file got removed
        # from the backend but somehow remained in the cache.
        self.save(digest, desc)

        return digest

    def put_file_content(self, content, desc=""):
        """Store a file in the storage.

        See `put_file_from_fobj'. This method will read the content of
        the file from the given binary string.

        content (bytes): the content of the file to store.
        desc (unicode): the (optional) description to associate to the
            file.

        return (unicode): the digest of the stored file.

        """
        with io.BytesIO(content) as src:
            return self.put_file_from_fobj(src, desc)

    def put_file_from_path(self, src_path, desc=""):
        """Store a file in the storage.

        See `put_file_from_fobj'. This method will read the content of
        the file from the given file-system location.

        src_path (string): an accessible location on the file-system
            from which to read the contents of the file.
        desc (unicode): the (optional) description to associate to the
            file.

        return (unicode): the digest of the stored file.

        """
        with io.open(src_path, 'rb') as src:
            return self.put_file_from_fobj(src, desc)

    def describe(self, digest):
        """Return the description of a file given its digest.

        digest (unicode): the digest of the file to describe.

        return (unicode): the description of the file.

        raise (KeyError): if the file cannot be found.

        """
        return self.backend.describe(digest)

    def get_size(self, digest):
        """Return the size of a file given its digest.

        digest (unicode): the digest of the file to calculate the size
            of.

        return (int): the size of the file, in bytes.

        raise (KeyError): if the file cannot be found.

        """
        return self.backend.get_size(digest)

    def delete(self, digest):
        """Delete a file from the backend and the local cache.

        digest (unicode): the digest of the file to delete.

        """
        self.drop(digest)
        self.backend.delete(digest)

    def drop(self, digest):
        """Delete a file only from the local cache.

        digest (unicode): the file to delete.

        """
        cache_file_path = os.path.join(self.file_dir, digest)

        try:
            os.unlink(cache_file_path)
        except OSError:
            pass

    def purge_cache(self):
        """Empty the local cache.

        """
        self.destroy_cache()
        if not mkdir(config.cache_dir) or not mkdir(self.file_dir):
            logger.error("Cannot create necessary directories.")
            raise RuntimeError("Cannot create necessary directories.")

    def destroy_cache(self):
        """Completely remove and destroy the cache.

        Nothing that could have been created by this object will be
        left on disk. After that, this instance isn't usable anymore.

        """
        rmtree(self.file_dir)

    def list(self):
        """List the files available in the storage.

        return ([(unicode, unicode)]): a list of pairs, each
            representing a file in the form (digest, description).

        """
        return self.backend.list()

    def check_backend_integrity(self, delete=False):
        """Check the integrity of the backend.

        Request all the files from the backend. For each of them the
        digest is recomputed and checked against the one recorded in
        the backend.

        If mismatches are found, they are reported with ERROR
        severity. The method returns False if at least a mismatch is
        found, True otherwise.

        delete (bool): if True, files with wrong digest are deleted.

        """
        clean = True
        for digest, description in self.list():
            fobj = self.backend.get_file(digest)
            hasher = hashlib.sha1()
            try:
                buf = fobj.read(self.CHUNK_SIZE)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = fobj.read(self.CHUNK_SIZE)
            finally:
                fobj.close()
            computed_digest = hasher.hexdigest().decode("ascii")
            if digest != computed_digest:
                logger.error("File with hash %s actually has hash %s" %
                             (digest, computed_digest))
                if delete:
                    self.delete(digest)
                clean = False

        return clean
