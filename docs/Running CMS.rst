Running CMS
***********

Configuring the DB
==================

The first thing to do is to create the user and the database. For PostgreSQL, this is obtained with the following commands (note that the user need not to be a superuser, nor to be able to create databases nor roles):

.. sourcecode:: bash

    sudo su postgres
    createuser cmsuser -P
    createdb -O cmsuser cmsdb

If you are going to use CMS services on different hosts from the one where PostgreSQL is running, you also need to instruct it to accept the connections from the services. To do so, you need to change the listening address of PostgreSQL in :file:`postgresql.conf`, for example like this::

    listen_addresses = '127.0.0.1,192.168.0.x'

Moreover, you need to change the HBA (a sort of access control list for PostgreSQL) to accept login requests from outside localhost. Open the file :file:`pg_hba.conf` and add a line like this one::

    host  cmsdb  cmsuser  192.168.0.0/24  md5


Configuring CMS
===============

There are two configuration files, one for CMS itself and one for the rankings. Samples for both files are in the directory :file:`examples/`. You want to copy them to the same file names but without the ``.sample`` suffix (that is, to :file:`examples/cms.conf` and :file:`examples/cms.ranking.conf`) before modifying them.

* :file:`cms.conf` is intended to be the same in all servers; all configurations are explained in the file; of particular importance is the definition of ``core_services``, that specifies where the services are going to be run, and how many of them, and the connecting line for the database, in which you need to specify the name of the user created above and its password.

* :file:`cms.ranking.conf` is intended to be different on each server that will host a ranking. The addresses and log-in information of each ranking must be the same as the ones found in :file:`cms.conf`.

These files are pretty good starting point if you want to try CMS. There are some mandatory changes to do though:

* you must change the connection string given in ``database``; this usually means to change username and password with the one you choose before;

* if you are running low on disk space, you may want to change ``keep_sandbox`` to ``false``;

* if you want to run CMS without installing it, you need to change ``process_cmdline`` to reflect that.

If you are organizing a real contest, you must change ``secret_key`` from the default, and also you are supposed to think about how to distribute your services and change accordingly ``core_services``. Finally, you should change the ranking section of :file:`cms.conf`, and :file:`cms.ranking.conf`, to use a non-trivial username and password.

After having modified :file:`cms.conf` and :file:`cms.ranking.conf` in :file:`examples/`, you can reinstall CMS in order to make these changes effective, with

.. sourcecode:: bash

    sudo ./setup.py install


Running CMS
===========

Here we will assume you installed CMS. If not, you should replace all commands path with the appropriate local versions (for example, ``cmsLogService`` becomes ``./cms/service/LogService.py``).

At this point, you should have CMS installed on all the machines you want run services on, with the same configuration file, and a running PostgreSQL instance. To run CMS, you need a contest in the database. To create a contest, follow :doc:`these instructions <Creating a contest>`.

CMS is composed of a number of services, potentially replicated several times, and running on several machines. You can run all the services by hand, but this is a tedious task. Luckily, there is a service (ResourceService) that takes care of starting all the services in the machine it is running, limiting thus the number of binaries you have to run. Services started by ResourceService do not show their logs to the standard output; so it is expected that you run LogService to inspect the logs as they arrive (logs are also saved to disk). To start LogService, you need to issue, in the machine specified in cms.conf for LogService, this command:

.. sourcecode:: bash

    cmsLogService 0

where ``0`` is the "shard" of LogService you want to run. Since there must be only one instance of LogService, it is safe to let CMS infer that the shard you want is the 0-th, and so an equivalent command is

.. sourcecode:: bash

    cmsLogService

After LogService is running, you can start ResourceService on each machine involved, instructing it to load all the other services:

.. sourcecode:: bash

    cmsResourceService -a

The flag ``-a`` informs ResourceService that it has to start all other services, and we have omitted again the shard number since, even if ResourceService is replicated, there must be only one of it in each machine. If you have a funny network configuration that confuses CMS, just give explicitly the shard number. In any case, ResourceService will ask you the contest to load, and will start all the other services. You should start see logs flowing in the LogService terminal.

Note that it is your duty to keep CMS's configuration synchronized among the machines.

