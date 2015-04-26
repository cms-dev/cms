Running CMS
***********

Configuring the DB
==================

The first thing to do is to create the user and the database. For PostgreSQL, this is obtained with the following commands (note that the user doesn't need to be a superuser, nor be able to create databases nor roles):

.. sourcecode:: bash

    sudo su - postgres
    createuser cmsuser -P
    createdb -O cmsuser database
    psql database -c 'ALTER SCHEMA public OWNER TO cmsuser'
    psql database -c 'GRANT SELECT ON pg_largeobject TO cmsuser'

The last two lines are required to give the PostgreSQL user some privileges which it doesn't have by default, despite being the database owner.

Then you may need to adjust the CMS configuration to contain the correct database parameters. See :ref:`running-cms_configuring-cms`.

Finally you have to create the database schema for CMS, by running:

.. sourcecode:: bash

    cmsInitDB

.. note::

    If you are going to use CMS services on different hosts from the one where PostgreSQL is running, you also need to instruct it to accept the connections from the services. To do so, you need to change the listening address of PostgreSQL in :file:`postgresql.conf`, for example like this::

        listen_addresses = '127.0.0.1,192.168.0.x'

    Moreover, you need to change the HBA (a sort of access control list for PostgreSQL) to accept login requests from outside localhost. Open the file :file:`pg_hba.conf` and add a line like this one::

        host  database  cmsuser  192.168.0.0/24  md5


.. _running-cms_configuring-cms:

Configuring CMS
===============

There are two configuration files, one for CMS itself and one for the rankings. Samples for both files are in the directory :gh_tree:`config/`. You want to copy them to the same file names but without the ``.sample`` suffix (that is, to :file:`config/cms.conf` and :file:`config/cms.ranking.conf`) before modifying them.

* :file:`cms.conf` is intended to be the same on all servers; all configurations are explained in the file; of particular importance is the definition of ``core_services``, that specifies where the services are going to be run, and how many of them, and the connecting line for the database, in which you need to specify the name of the user created above and its password.

* :file:`cms.ranking.conf` is not necessarily meant to be the same on each server that will host a ranking, since it just controls settings relevant for one single server. The addresses and log-in information of each ranking must be the same as the ones found in :file:`cms.conf`.

These files are a pretty good starting point if you want to try CMS. There are some mandatory changes to do though:

* you must change the connection string given in ``database``; this usually means to change username, password and database with the ones you chose before;

* if you are running low on disk space, you may want to change ``keep_sandbox`` to ``false``;

* if you want to run CMS without installing it, you need to change ``process_cmdline`` to reflect that.

If you are organizing a real contest, you must change ``secret_key`` from the default, and also you will need to think about how to distribute your services and change accordingly ``core_services``. Finally, you should change the ranking section of :file:`cms.conf`, and :file:`cms.ranking.conf`, to use a non-trivial username and password.

.. warning::

   As the name implies, the value of ``secret_key`` must be kept confidential. If a contestant knows it (for example because you are using the default value), they may be easily able to log in as another contestant.

After having modified :file:`cms.conf` and :file:`cms.ranking.conf` in :gh_tree:`config/`, you can reinstall CMS in order to make these changes effective, with

.. sourcecode:: bash

    sudo ./setup.py install


Running CMS
===========

Here we will assume you installed CMS. If not, you should replace all commands path with the appropriate local versions (for example, ``cmsLogService`` becomes :gh_blob:`./scripts/cmsLogService`).

At this point, you should have CMS installed on all the machines you want run services on, with the same configuration file, and a running PostgreSQL instance. To run CMS, you need a contest in the database. To create a contest, follow :doc:`these instructions <Creating a contest>`.

CMS is composed of a number of services, potentially replicated several times, and running on several machines. You can run all the services by hand, but this is a tedious task. Luckily, there is a service (ResourceService) that takes care of starting all the services on the machine it is running, limiting thus the number of binaries you have to run. Services started by ResourceService do not show their logs to the standard output; so it is expected that you run LogService to inspect the logs as they arrive (logs are also saved to disk). To start LogService, you need to issue, in the machine specified in cms.conf for LogService, this command:

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


.. _running-cms_recommended-setup:

Recommended setup
=================

Of course, the number of servers one needs to run a contest depends on many factors (number of participants, length of the contest, economical issues, more technical matters...). We recommend that, for fairness, each Worker runs an a dedicated machine (i.e., without other CMS services beyond ResourceService).

As for the distribution of services, usually there is one ResourceService for each machine, one instance for each of LogService, ScoringService, Checker, EvaluationService, AdminWebServer, and one or more instances of ContestWebServer and Worker. Again, if there are more than one Worker, we recommend to run them on different machines.

We suggest and support out-of-the-box using CMS over Ubuntu 14.04. Yet, CMS can be successfully run on different Linux distributions. Non-Linux operating systems are not supported.

You can replicate the service handling the contestant-facing web server, :file:`cmsContestWebServer`; in this case, you need to configure a load balancer in front of them. We suggest to use nginx for that, and provide a sample configuration for it at :gh_blob:`config/nginx.conf.sample` (this file also configures nginx to act as a HTTPS endpoint and to force secure connections, by redirecting HTTP to HTTPS). This file probably needs to be adapted to your distribution if it's not Ubuntu: try to merge it with the file you find installed by default. For additional information see the official nginx `documentation <http://wiki.nginx.org/HttpUpstreamModule>`_ and `examples <http://wiki.nginx.org/LoadBalanceExample>`_. Note that without the ``ip_hash`` option some features might not always work as expected.


Logs
====

When the services are running, log messages are streamed to the log
service. This is the meaning of the log levels:

- debug: you can ignore them (in the default configuration, the log service does not show them);

- info: they inform you on what is going on in the system and that everything is fine;

- warning: something went wrong or was slightly unexpected, but CMS knew how to handle it, or someone fed inappropriate data to CMS (by error or on purpose); you may want to check these as they may evolve into errors or unexpected behaviors, or hint that a contestant is trying to cheat;

- error: an unexpected condition that should not have happened; you are really encouraged to take actions to fix them, but the service will continue to work (most of the time, ignoring the error and the data connected to it);

- critical: a condition so unexpected that the service is really startled and refuses to continue working; you are forced to take action because with high probability the service will continue having the same problem upon restarting.

Warning, error, and critical log messages are also displayed in the main page of AdminWebServer.
