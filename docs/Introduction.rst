Introduction
************

CMS (Contest Management System) is a software for organizing programming contests similar to well-known international contests like the IOI (International Olympiad in Informatics). It was written by and it received contributions from people involved in the organization of similar contests on a local, national and international level, and it is regularly used for such contests in many different countries. It is meant to be secure, extendable, adaptable to different situations and easy to use.

CMS is a complete, tested and well proved solution for managing a contest. However, it only provides limited tools for the development of the task data belonging to the contest (task statements, solutions, testcases, etc.). Also, the configuration of machines and network resources that host the contest is a responsibility of the contest administrators.


General structure
=================
The system is organized in a modular way, with different services running (potentially) on different machines, and providing extendability via service replications on several machines.

The state of the contest is wholly kept on a PostgreSQL database (other DBMSs are not supported, as CMS relies on the Large Object (LO) feature of PostgreSQL). It is unlikely that in the future we will target different databases.

As long as the database is operating correctly, all other services can be started and stopped independently. For example, the administrator can quickly replace a broken machine with an identical one, which will take its roles (without having to move information from the broken machine). Of course, this also means that CMS is completely dependent on the database to run. In critical contexts, it is necessary to configure the database redundantly and be prepared to rapidly do a fail-over in case something bad happens. The choice of PostgreSQL as the database to use should ease this part, since there are many different, mature and well-known solutions to provide such redundance and fail-over procedures.


Services
========

CMS is composed of several services, that can be run on a single or on many servers. The core services are:

- LogService: collects all log messages in a single place;

- ResourceService: collects data about the services running on the same server, and takes care of starting all of them with a single command;

- Checker: simple heartbeat monitor for all services;

- EvaluationService: organizes the queue of the submissions to compile or evaluate on the testcases, and dispatches these jobs to the workers;

- Worker: actually runs the jobs in a sandboxed environment;

- ScoringService: collects the outcomes of the submissions and computes the score;

- ProxyService: sends the computed scores to the rankings;

- ContestWebServer: the webserver that the contestants will be interacting with;

- AdminWebServer: the webserver to control and modify the parameters of the contests.

Finally, RankingWebServer, whose duty is of course to show the ranking. This webserver is - on purpose - separated from the inner core of CMS in order to ease the creation of mirrors and restrict the number of people that can access services that are directly connected to the database.

Each of the core services is designed to be able to be killed and reactivated in a way that keeps the consistency of data, and does not block the functionalities provided by the other services.

Some of the services can be replicated on several machine: these are ResourceService (designed to be run on every machine), ContestWebServer and Worker.

In addition to services, CMS includes many command line tools. They help with importing, exporting and managing of contest data, and with testing.

.. _introduction_security-considerations:

Security considerations
=======================

Network
-------

With the exception of RWS, there are no cryptographic or authentication schemes between the various services or between the services and the database.
Thus, it is mandatory to keep the services on a dedicated network, properly isolating it via firewalls from contestants or other people's computers.

It is recommended to not make AdminWebServer publicly accessible
(instead, either restrict it to only be accessed from a VPN or add authentication in a reverse proxy).
While AWS does have its own authentication, there have been bugs in it, and restricting access also prevents possible DoS attacks.

Default credentials
-------------------

To ease testing, the configuration file contains default values for ``web_server.secret_key`` and for RWS credentials
(``proxy_service.rankings`` in ``cms.toml``, and ``username``/``password`` in ``cms_ranking.toml``).
These must be changed in real deployments, ideally to long random values.
Failure to do so (for ``secret_key``) may allow attackers to log in as arbitrary users in CWS or get access to AWS.
Weak or default RWS credentials may allow attackers to deface the leaderboard.

Sandbox
-------

The sandbox that submissions are evaluated in is quite conservative.
However, it does allow access to the following directories on the host file system:

- ``/bin``
- ``/dev`` (except for ``/dev/shm``)
- ``/etc`` (during compilation)
- ``/etc/alternatives``, ``/etc/mono``
- ``/opt/pypy3``
- ``/lib`` and ``/lib64``
- ``/usr``
- ``/var/lib/ghc`` (during compilation)

The most notable of these is ``/etc``.

Thus, you should make sure that these directories do not contain any world-readable sensitive information.

Passwords
---------

CMS can use both plaintext and bcrypt-hashed passwords. bcrypt is recommended in all cases.

The browser cookie that is generated upon logging in via CWS contains the authentication data (plaintext password or bcrypt hash, depending on method) in an unencrypted form.
Thus it is recommended to use randomly-generated passwords if possible.

Denial of service
-----------------

CWS is written in pure Python and cannot handle many simultaneous connections.
Thus, it is quite vulnerable to denial of service attacks.
For on-site contests, it is recommended to limit CWS to only be accessed from the site using a reverse proxy.
Otherwise, one should be prepared to deploy DoS mitigation techniques (IP banning, etc) if availability is a concern.
