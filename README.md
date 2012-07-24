CMS - A Contest Management System
=================================


Introduction
------------

CMS, or Contest Management System, is a distributed system for running
and (to some extent) organizing a programming contest.

CMS has been designed to be general and to handle many different types
of contests, tasks, scorings, etc. Nonetheless, CMS has been
explicitly build to be used in the 2012 International Olympiad in
Informatics, to be held in September 2012 in Italy.


Description
-----------

CMS is composed of several services, that can be run on a single or on
many servers. The core services are:

- LogService: collects all log messages in a single place;

- ResourceService: collects data about the services running on the
  same server, and takes care of starting all of them with a single
  command;

- Checker: simple heartbeat monitor for all services;

- EvaluationService: organizes the queue of the submissions to compile
  or evaluate on the testcases, and dispatches these jobs to the
  workers;

- Worker: actually runs the jobs in a sandboxed environment;

- ScoringService: collects the outcomes of the submissions and compute
  the score; also sends these scores to the rankings;

- ContestWebServer: the webserver that the contestants will be
  interacting with;

- AdminWebServer: the webserver to control and modify the parameters
  of the contests.

Finally, RankingWebServer, whose duty is of course to show the
ranking. This webserver is - on purpose - separated from the inner
core of CMS in order to ease the creation of mirrors and restrict the
number of people that can access services that are directly connected
to the database.

Files and configurations are stored in a PostgreSQL database.

There are also other services for testing, importing and exporting
contests.

Each of the core services is designed to be able to be killed and
reactivated in a way that keeps the consistency of data.


Recommended setup
-----------------

Of course, the number of servers one needs to run a contest depends on
many factors (number of participants, length of the contest,
economical issues, more technical matters...). We recommend that, for
fairness, there is at least one server associated only to a worker.

As for the distribution of services, usually there is one
ResourceService for each server, one copy each of LogService,
ScoringService, Checker, EvaluationService, AdminWebServer, and one or
more of ContestWebServer and Worker. Again, if there are more than one
worker, we recommend to run them on different servers.

Our preferred distribution is Ubuntu >= 12.04 LTS.  We will hopefully
support Ubuntu 12.04.x out of the box for the length of Ubuntu's
support duration, that is five years.

Very important note: up to now, we support only 32 bit distributions.

Saying that, one is not forced to follow the previous rules, and it
should not be very hard to successfully run CMS on different
distributions or even on 64 bit installations (see the howto about
setting up a 32 bits chroot for more information on this).


Dependencies
------------

These are our requirements (in particular we highlight those that are
not usually installed by default) - previous versions may or may not
work:

- build environment for the programming languages allowed in the
  competition;

- postgreSQL >= 8.4;

- gettext >= 0.18;

- python >= 2.7 (and < 3.0);

- python-setuptools >= 0.6;

- python-tornado >= 2.0;

- python-psycopg2 >= 2.4;

- python-simplejson >= 2.1;

- python-sqlalchemy >= 0.7;

- python-psutil >= 0.2;

- python-netifaces >= 0.5;

- python-crypto >= 2.3;

- python-yaml >= 3.10 (only for YamlImporter);

- python-beautifulsoup >= 3.2 (only for running tests);

- python-coverage >= 3.4 (only for running tests).


On Ubuntu 12.04, one will need to run the following script to satisfy
all dependencies:

```bash
sudo apt-get install postgresql postgresql-client python-setuptools \
     python-tornado python-psycopg2 python-sqlalchemy \
     python-psutil gettext build-essential fpc stl-manual \
     python-simplejson python-netifaces python-beautifulsoup \
     python-coverage python-crypto python-tz

# Optional.
# sudo apt-get install phppgadmin python-yaml
```

If you prefer using Python Package Index, you can retrieve all Python
dependencies with this line (see below for the meaning of $REPO):

```bash
sudo pip install -r $REPO/REQUIREMENTS.txt
```


Obtaining CMS
-------------

For every server, one needs to retrieve CMS. Since CMS does not yet
have a release schedule, the fastest way to obtain it is via its git
repository:

```bash
sudo apt-get install git
git clone git://github.com/cms-dev/cms.git
```

This will create a directory ./cms/ with the source code, that we will
refer to as $REPO in the following.


Configuring and installing CMS
------------------------------

There are two configuration files, one for CMS itself and one for the
rankings. Samples for both files are in $REPO/examples. You want
to copy them to the same file names but without the ".sample" suffix
(that is, to $REPO/examples/cms.conf and
$REPO/examples/cms.ranking.conf) before modifying them.

- cms.conf is intended to be the same in all servers; all
  configurations are explained in the file; of particular importance is
  the definition of core_services, that specifies where the services
  are going to be run, and how many of them.

- cms.ranking.conf is intended to be different on each server that
  will host a ranking. The addresses and log-in information of each
  ranking must be the same as the ones found in cms.conf.

Once configured, we can proceed to install it using the commands:

```bash
cd $REPO
./setup.py build
sudo ./setup.py install
```

These will create a user and a group named "cmsuser". If you want to
run CMS from your account, just add yourself to the cmsuser group and
log-in again before continuing:

```bash
sudo usermod -a -G cmsuser
```

You can verify to actually be in the group issuing the command
```bash
groups
```


Updating CMS
------------

To update CMS, run the following:

```bash
cd $REPO
git pull
./setup.py build
sudo ./setup.py install
```

Since CMS is still in heavy development, we are introducing many
changes in the database structure. If you created a database with a
previous version, you may need to run UpdateDB.py to organize the data
in the new structure:

```bash
cd $REPO/cms/db
python UpdateDB.py -l # To see which updating scripts are available.
python UpdateDB.py -s YYYYMMDD # To update the DB, where YYYYMMDD is
                               # the last date in which you created or
                               # updated the DB.
```


Running CMS
-----------

Before running CMS, you need to create in some way a contest. There
are two main facilities: cmsContestImporter and cmsYamlImporter. The
former load into the system a contest exported from CMS with
cmsContestExporter. The latter imports a contest from a directory with
the structure of the Italian Olympiad repository.

Once a contest is loaded, the first thing to run is the logger
(from the correct server!):

```bash
cmsLogService 0
```

After that, for each server you can run (and keep alive) all services
associated to the server with:

```bash
cmsResourceService <shard-number> -a
```

where shard-number is the shard associated to the ResourceService on
that server. This will ask for which contest to load. The "--help"
switch is enabled for every program for additional information.

If a service keeps restarting you may need to change
"process_cmdline" in the configuration to one more suited to your
system.

In particular if there are more than one ContestWebServer, one may
want to use a load balancer. We recommend to use nginx; a sample
configuration is provided in $REPO/cms/example.


Testimonials
------------

CMS has been used in several official and unofficial contests. In
particular we are aware of the following:

- OII 2011 (Italian Olympiad in Informatics), September 2011;

- AIIO 2012 (Australian Invitational Informatics Olympiad), February
  2012;

- FARIO 2012 (French-Australian Regional Informatics Olympiad), March
  2012;

- training camps for the selections of the national teams of Australia
  and Italy;

- laboratory exercises and exams of the course "Algorithms and data
  structures" at University of Trento (year 2011-2012).
