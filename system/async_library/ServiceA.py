#!/usr/bin/python

"""Simple service that ask for echo from all ServiceB, and request a
file from ServiceB,0.

"""

import time

from FileStorage import FileCacher
from AsyncLibrary import Service, rpc_callback, logger
from Utils import ServiceCoord


class ServiceA(Service):
    """Simple service that ask for echo from all ServiceB, and request
    a file from ServiceB,0.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("ServiceA", shard))
        logger.debug("ServiceA.__init__")
        Service.__init__(self, shard)
        self.ServiceB = []
        self.ServiceB.append(self.connect_to(
                ServiceCoord("ServiceB", 0)))
        self.ServiceB.append(self.connect_to(
                ServiceCoord("ServiceB", 1)))

        self.add_timeout(self.ask_for_echo, None, 10,
                         immediately=True)
        self.add_timeout(self.ask_for_file, None, 2,
                         immediately=True)

        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        self.add_timeout(self.test_file_storage, None, 2,
                         immediately=True)

        self.FC = FileCacher(self, self.FS)
        self.digest = None
        self.add_timeout(self.test_file_cacher, None, 5)

    def ask_for_echo(self):
        """Ask all ServiceB for a echo.

        """
        logger.debug("ServiceA.ask_for_echo")
        for i in xrange(0, 2):
            remote_service = self.ServiceB[i]
            if remote_service.connected:
                logger.info("Asking %s for echo..."
                            % str(remote_service.remote_service_coord))
                remote_service.echo(string=str(time.time()),
                                    callback=ServiceA.echo_callback,
                                    plus=i)
            else:
                logger.info("%s not connected, not asking!"
                            % str(remote_service.remote_service_coord))
        return True

    @rpc_callback
    def echo_callback(self, data, plus, error=None):
        """Callback for ask_for_echo.

        """
        logger.debug("ServiceA.echo_callback")
        if error != None:
            return
        logger.info("ServiceB,%d answered %s" % (plus, data))

    def ask_for_file(self):
        """Ask ServiceB,0 for file aaa.

        """
        logger.debug("ServiceA.ask_for_file")
        if not self.ServiceB[0].connected:
            logger.info("Not asking ServiceB's aaa because not connected!")
            return True
        logger.info("Asking ServiceB's aaa.")
        self.ServiceB[0].binary_cat(filename="./aaa",
                                    callback=ServiceA.file_callback,
                                    plus=time.time())
        return False

    @rpc_callback
    def file_callback(self, data, plus, error=None):
        """Callback for ask_for_file. It writes the file to bbb.

        """
        logger.debug("ServiceA.file_callback")
        if error != None:
            logger.error(error)
            return
        seconds = time.time() - plus
        megabytes = len(data) / 1024.0 / 1024.0
        logger.info(("ServiceB's gave us aaa: %5.3lf MB in %5.3lf seconds " + \
                     "(%5.3lf MB/s)")
                    % (megabytes, seconds, megabytes / seconds))
        with open("bbb", "wb") as bbb:
            bbb.write(data)

        # Now giving back the file
        logger.info("Sending back bbb to ServiceB.")
        with open("bbb", "rb") as bbb:
            self.ServiceB[0].binary_write(filename="ccc",
                                          binary_data=bbb.read())

    def test_file_storage(self):
        """Ask FS for file aaa.

        """
        logger.debug("ServiceA.test_file_storage")
        if not self.FS.connected:
            logger.info("Not putting aaa in FileStorage because not connected!")
            return True
        logger.info("Putting aaa into FileStorage.")
        with open("aaa", "rb") as aaa:
            data = aaa.read()
        self.FS.put_file(binary_data=data,
                         callback=ServiceA.test_file_storage_callback,
                         plus=(len(data), time.time()))
        return False

    @rpc_callback
    def test_file_storage_callback(self, data, plus, error=None):
        """Callback for test_file_storage. It get the file again.

        """
        logger.debug("ServiceA.test_file_storage_callback")
        if error != None:
            logger.error(error)
            return
        seconds = time.time() - plus[1]
        megabytes = plus[0] / 1024.0 / 1024.0
        logger.info(("FileStorage stored aaa. Digest: %s\m  %5.3lf MB in " + \
                     "%5.3lf seconds (%5.3lf MB/s)")
                    % (data, megabytes, seconds, megabytes / seconds))
        self.digest = data

        # Now getting back the file
        logger.info("Getting back aaa from FileStorage.")
        self.FS.get_file(digest=data,
                         callback=ServiceA.test_file_storage_callback_2,
                         plus=time.time())

    @rpc_callback
    def test_file_storage_callback_2(self, data, plus, error=None):
        """Callback for test_file_storage. It writes the file to bbb.

        """
        logger.debug("ServiceA.test_file_storage_callback_2")
        if error != None:
            logger.error(error)
            return
        seconds = time.time() - plus
        megabytes = len(data) / 1024.0 / 1024.0
        logger.info(("Got aaa from FileStorage: %5.3lf MB in %5.3lf " + \
                     "seconds (%5.3lf MB/s)")
                    % (megabytes, seconds, megabytes / seconds))

        with open("ddd", "wb") as ddd:
            ddd.write(data)

    def test_file_cacher(self):
        """Ask FC for file aaa.

        """
        logger.debug("ServiceA.test_file_cacher")
        if self.digest == None:
            logger.info("Not testing FC because not ready.")
            return True
        logger.info("Asking FC to get file aaa and move it to eee.")
        self.FC.get_file(self.digest, filename="eee",
                         callback=self.test_file_cacher_callback,
                         plus="Plus object.")
        return False

    def test_file_cacher_callback(self, data, plus, error=None):
        """Getting the file and writing it to fff.

        """
        logger.debug("ServiceA.test_file_cacher_callback")
        if error != None:
            logger.error(error)
            return
        with open("fff", "wb") as fff:
            fff.write(data)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        ServiceA(int(sys.argv[1])).run()
