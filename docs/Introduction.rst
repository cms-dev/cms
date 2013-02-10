Introduction
************

CMS is composed of several services, that can be run on a single or on many servers. The core services are:

- LogService: collects all log messages in a single place;

- ResourceService: collects data about the services running on the same server, and takes care of starting all of them with a single command;

- Checker: simple heartbeat monitor for all services;

- EvaluationService: organizes the queue of the submissions to compile or evaluate on the testcases, and dispatches these jobs to the workers;

- Worker: actually runs the jobs in a sandboxed environment;

- ScoringService: collects the outcomes of the submissions and compute the score; also sends these scores to the rankings;

- ContestWebServer: the webserver that the contestants will be interacting with;

- AdminWebServer: the webserver to control and modify the parameters of the contests.

Finally, RankingWebServer, whose duty is of course to show the ranking. This webserver is - on purpose - separated from the inner core of CMS in order to ease the creation of mirrors and restrict the number of people that can access services that are directly connected to the database.

There are also other services for testing, importing and exporting contests.

Each of the core services is designed to be able to be killed and reactivated in a way that keeps the consistency of data, and does not block the functionalities provided by the other services.

Some of the services can be replicated on several machine: these are ResourceService (designed to be run on every machine), ContestWebServer, Worker.
