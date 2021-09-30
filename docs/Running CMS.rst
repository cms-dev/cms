Running CMS
***********

Configuring the DB
==================

The first thing to do is to create the user and the database. If you're on Ubuntu, you need to login as the postgres user first:

.. sourcecode:: bash

    sudo su - postgres

Then, to create the user (which does not need to be a superuser, nor be able to create databases nor roles) and the database, you need the following commands:

.. sourcecode:: bash

    createuser --username=postgres --pwprompt cmsuser
    createdb --username=postgres --owner=cmsuser cmsdb
    psql --username=postgres --dbname=cmsdb --command='ALTER SCHEMA public OWNER TO cmsuser'
    psql --username=postgres --dbname=cmsdb --command='GRANT SELECT ON pg_largeobject TO cmsuser'

The last two lines are required to give the PostgreSQL user some privileges which it does not have by default, despite being the database owner.

After running these commands, log out to the initial shell:

.. sourcecode:: bash

    logout

Then you may need to adjust the CMS configuration to contain the correct database parameters. See :ref:`running-cms_configuring-cms`.

Finally you have to create the database schema for CMS, by running:

.. sourcecode:: bash

    cmsInitDB

.. note::

    If you are going to use CMS services on different hosts from the one where PostgreSQL is running, you also need to instruct it to accept the connections from the services. To do so, you need to change the listening address of PostgreSQL in :file:`postgresql.conf`, for example like this::

        listen_addresses = '127.0.0.1,192.168.0.x'

    Moreover, you need to change the HBA (a sort of access control list for PostgreSQL) to accept login requests from outside localhost. Open the file :file:`pg_hba.conf` and add a line like this one::

        host  cmsdb  cmsuser  192.168.0.0/24  md5


.. _running-cms_configuring-cms:

Configuring CMS
===============

There are two configuration files, one for CMS itself and one for the rankings. Samples for both files are in the directory :gh_tree:`config/`. You want to copy them to the same file names but without the ``.sample`` suffix (that is, to :file:`config/cms.conf` and :file:`config/cms.ranking.conf`) before modifying them.

* :file:`cms.conf` is intended to be the same on all machines; all configurations options are explained in the file; of particular importance is the definition of ``core_services``, that specifies where and how many services are going to be run, and the connecting line for the database, in which you need to specify the name of the user created above and its password.

* :file:`cms.ranking.conf` is not necessarily meant to be the same on each server that will host a ranking, since it just controls settings relevant for one single server. The addresses and log-in information of each ranking must be the same as the ones found in :file:`cms.conf`.

These files are a pretty good starting point if you want to try CMS. There are some mandatory changes to do though:

* you must change the connection string given in ``database``; this usually means to change username, password and database with the ones you chose before;

* if you are running low on disk space, you may want to make sure ``keep_sandbox`` is set to ``false``;

If you are organizing a real contest, you must also change ``secret_key`` to a random key (the admin interface will suggest one if you visit it when ``secret_key`` is the default). You will also need to think about how to distribute your services and change ``core_services`` accordingly. Finally, you should change the ranking section of :file:`cms.conf`, and :file:`cms.ranking.conf`, using non-trivial username and password.

.. warning::

   As the name implies, the value of ``secret_key`` must be kept confidential. If a contestant knows it (for example because you are using the default value), they may be easily able to log in as another contestant.

The configuration files get copied automatically by the ``prerequisites.py`` script, so you can either run ``sudo ./prerequisites.py install`` again (answering "Y" when questioned about overwriting old configuration files) or you could simply edit the previously installed configuration files (which are usually found in ``/usr/local/etc/`` or ``/etc/``), if you do not plan on running that command ever again.

Running CMS
===========

Here we will assume you installed CMS. If not, you should replace all commands path with the appropriate local versions (for example, ``cmsLogService`` becomes :gh_blob:`./scripts/cmsLogService`).

At this point, you should have CMS installed on all the machines you want run services on, with the same configuration file, and a running PostgreSQL instance. To run CMS, you need a contest in the database. To create a contest, follow :doc:`these instructions <Creating a contest>`.

CMS is composed of a number of services, potentially replicated several times, and running on several machines. You can start all the services by hand, but this is a tedious task. Luckily, there is a service (ResourceService) that takes care of starting all the services on the machine it is running, limiting thus the number of binaries you have to run. Services started by ResourceService do not show their logs to the standard output; so it is expected that you run LogService to inspect the logs as they arrive (logs are also saved to disk). To start LogService, you need to issue, in the machine specified in cms.conf for LogService, this command:

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

You should now be able to start exploring the admin interface, by default at http://localhost:8889/. The interface is accessible with an admin account, which you need to create first using the AddAdmin command, for example:

.. sourcecode:: bash

    cmsAddAdmin name

CMS will create an admin account with username "name" and a random password that will be printed by the command. You can log in with this credentials, and then use the admin interface to modify the account or add other accounts.

.. _running-cms_recommended-setup:

Recommended setup
=================

Of course, the number of servers one needs to run a contest depends on many factors (number of participants, length of the contest, economical issues, more technical matters...). We recommend that, for fairness, each Worker runs an a dedicated machine (i.e., without other CMS services beyond ResourceService).

As for the distribution of services, usually there is one ResourceService for each machine, one instance for each of LogService, ScoringService, Checker, EvaluationService, AdminWebServer, and one or more instances of ContestWebServer and Worker. Again, if there are more than one Worker, we recommend to run them on different machines.

The developers of isolate (the sandbox CMS uses) provide a script, :file:`isolate-check-environment` that verifies your system is able to produce evaluations as fair and reproducible as possible. We recommend to run it and follow its suggestions on all machines where a Worker is running. You can download it `here <https://github.com/ioi/isolate/blob/master/isolate-check-environment>`_.

We suggest using CMS over Ubuntu. Yet, CMS can be successfully run on different Linux distributions. Non-Linux operating systems are not supported.

We recommend using nginx in front of the (one or more) :file:`cmsContestWebServer` instances serving the contestant interface. Using a load balancer is required when having multiple instances of :file:`cmsContestWebServer`, but even in case of a single instance, we suggest using nginx to secure the connection, providing an HTTPS endpoint and redirecting it to :file:`cmsContestWebServer`'s HTTP interface.

See :gh_blob:`config/nginx.conf.sample` for a sample nginx configuration. This file probably needs to be adapted to your distribution if it is not Ubuntu: try to merge it with the file you find installed by default. For additional information see the official nginx `documentation <http://wiki.nginx.org/HttpUpstreamModule>`_ and `examples <http://wiki.nginx.org/LoadBalanceExample>`_. Note that without the ``ip_hash`` option some CMS features might not always work as expected.


Logs
====

When the services are running, log messages are streamed to the log
service. This is the meaning of the log levels:

- debug: they are just for development; in the default configuration, they are not printed;

- info: they inform you on what is going on in the system and that everything is fine;

- warning: something went wrong or was slightly unexpected, but CMS knew how to handle it, or someone fed inappropriate data to CMS (by error or on purpose); you may want to check these as they may evolve into errors or unexpected behaviors, or hint that a contestant is trying to cheat;

- error: an unexpected condition that should not have happened; you are encouraged to take actions to fix them, but the service will continue to work (most of the time, ignoring the error and the data connected to it);

- critical: a condition so unexpected that the service is really startled and refuses to continue working; you are forced to take action because with high probability the service will continue having the same problem upon restarting.

Warning, error, and critical log messages are also displayed in the main page of AdminWebServer.
