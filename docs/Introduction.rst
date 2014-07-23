Introduction
************

CMS (Contest Management System) is a software for organizing programming contests similar to well-known international contests like the IOI (International Olympiad in Informatics). It was written and it received contributions by people involved in the organization of similar contests on a local, national and international level, and it is regularly used for such contests in many different countries. It is meant to be secure, extendable, adaptable to different situations and easy to use.

CMS is a complete, tested and well proved solution for managing a contest. It does not, however, provide tools for the development of the task data belonging to the contest (task statements, solutions, testcases, etc.) or for configuring machines and network resources that host the contest itself. These are responsibility of the contest administrators, although there are tools that help to automate them.


General structure
=================
The system is organized in a modular way, with different services running (potentially) on different machines, and providing extendability via service replications on several machines.

The state of the contest is wholly kept on a PostgreSQL database. At the moment, there is no way to use other SQL databases, because the Large Object (LO) feature of PostgreSQL is used. It is unlikely that in the future we will target different databases.

As long as the database is operating correctly, all other services can be started and stopped independently without problems. This means that if a machine goes down, then the administrator can quickly replace it with an identical one, which will take its roles (without having to move information from the broken machine). Of course, this also means that if the database goes down, the system is unable to work. In critical contexts, it is the necessary to configure the database redundantly and be prepared to rapidly do a fail-over in case something bad happens. The choice of PostgreSQL as the database to use should ease this part, since there are many different, mature and well-known solutions to provide such redundance and fail-over procedures.


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

- PrintingService: processes files submitted for printing and sends them to a printer;

- ContestWebServer: the webserver that the contestants will be interacting with;

- AdminWebServer: the webserver to control and modify the parameters of the contests.

Finally, RankingWebServer, whose duty is of course to show the ranking. This webserver is - on purpose - separated from the inner core of CMS in order to ease the creation of mirrors and restrict the number of people that can access services that are directly connected to the database.

There are also other services for testing, importing and exporting contests.

Each of the core services is designed to be able to be killed and reactivated in a way that keeps the consistency of data, and does not block the functionalities provided by the other services.

Some of the services can be replicated on several machine: these are ResourceService (designed to be run on every machine), ContestWebServer and Worker.

Security considerations
=======================

With the exception of RWS, there are no cryptographic or authentication schemes between the various services or between the services and the database. Thus, it is mandatory to keep the services on a dedicated network, properly isolating it via firewalls from contestants or other people's computers. This sort of operations, like also preventing contestants from communicating and cheating, is responsibility of the administrator and is not managed by CMS itself.
