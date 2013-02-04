CMS - Contest Management System
=================================


Introduction
------------

CMS, or Contest Management System, is a distributed system for running
and (to some extent) organizing a programming contest.

CMS has been designed to be general and to handle many different types
of contests, tasks, scorings, etc. Nonetheless, CMS has been
explicitly build to be used in the 2012 International Olympiad in
Informatics, held in September 2012 in Italy.


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

- build environment for the programming languages allowed in the competition;

- [PostgreSQL](http://www.postgresql.org/>) >= 8.4;

- [gettext](http://www.gnu.org/software/gettext/>) >= 0.18;

- [Python](http://www.python.org/>) >= 2.7, < 3.0;

- [setuptools](http://pypi.python.org/pypi/setuptools>) >= 0.6;

- [Tornado](http://www.tornadoweb.org/>) >= 2.0;

- [Psycopg](http://initd.org/psycopg/>) >= 2.4;

- [simplejson](https://github.com/simplejson/simplejson>) >= 2.1;

- [SQLAlchemy](http://www.sqlalchemy.org/>) >= 0.7;

- [psutil](https://code.google.com/p/psutil/>) >= 0.2;

- [netifaces](http://alastairs-place.net/projects/netifaces/>) >= 0.5;

- [PyCrypto](https://www.dlitz.net/software/pycrypto/>) >= 2.3;

- [pytz](http://pytz.sourceforge.net/>);

- [iso-codes](http://pkg-isocodes.alioth.debian.org/>);

- [shared-mime-info](http://freedesktop.org/wiki/Software/shared-mime-info>);

- [PyYAML](http://pyyaml.org/wiki/PyYAML>) >= 3.10 (only for YamlImporter);

- [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/>) >= 3.2 (only for running tests);

- [mechanize](http://wwwsearch.sourceforge.net/mechanize/>) >= 0.2 (only for running tests);

- [coverage](http://nedbatchelder.com/code/coverage/>) >= 3.4 (only for running tests);

- [Sphinx](http://sphinx-doc.org/>) (only for building documentation).

On Ubuntu 12.04, one will need to run the following script to satisfy
all dependencies:

```bash
sudo apt-get install build-essential fpc postgresql postgresql-client \
     gettext python2.7 python-setuptools python-tornado python-psycopg2 \
     python-simplejson python-sqlalchemy python-psutil python-netifaces \
     python-crypto python-tz iso-codes shared-mime-info stl-manual \
     python-beautifulsoup python-mechanize python-coverage

# Optional.
# sudo apt-get install phppgadmin python-yaml python-sphinx
```

On Arch Linux, the following command will install almost all
dependencies (two of them can be found in the AUR):

```bash
sudo pacman -S base-devel fpc postgresql postgresql-client python2 \
     setuptools python2-tornado python2-psycopg2 python2-simplejson \
     python2-sqlalchemy python2-psutil python2-netifaces python2-crypto \
     python2-pytz iso-codes shared-mime-info python2-beautifulsoup3 \
     python2-mechanize

# Install the following from AUR.
# https://aur.archlinux.org/packages/sgi-stl-doc/
# https://aur.archlinux.org/packages/python2-coverage/

# Optional.
# sudo pacman -S phppgadmin python2-yaml python-sphinx
```

If you prefer using Python Package Index, you can retrieve all Python
dependencies with this line (see below for the meaning of $REPO):

```bash
sudo pip install -r $REPO/REQUIREMENTS.txt
```


Obtaining CMS
-------------

The best way to obtain CMS is to download and unpack the last version
from <https://github.com/cms-dev/cms/tags>. This is going to be a
fairly tested version that may miss the last features but should work
as intended. If you are a developer, or if you are interested in some
feature yet to be released, or if you want help testing the next
version, you can use instead the git repository:

```bash
sudo apt-get install git
git clone git://github.com/cms-dev/cms.git
```

Either way, you will obtain a directory called cms/ with the source
code, that we will refer to as $REPO in the following.


Configuring and installing CMS
------------------------------

The first thing to do is to create the user and the database. For
PostgreSQL, this is obtained with the following commands (note that
the user need not to be a superuser, nor to be able to create
databases nor roles):

```bash
sudo su postgres
createuser cmsuser -P
createdb -O cmsuser cmsdb
```

There are two configuration files, one for CMS itself and one for the
rankings. Samples for both files are in $REPO/examples. You want to
copy them to the same file names but without the ".sample" suffix
(that is, to $REPO/examples/cms.conf and
$REPO/examples/cms.ranking.conf) before modifying them.

- cms.conf is intended to be the same in all servers; all
  configurations are explained in the file; of particular importance
  is the definition of core_services, that specifies where the
  services are going to be run, and how many of them, and the
  connecting line for the database, in which you need to specify the
  name of the user created above and its password.

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

When the services are running, log messages are streamed to the log
service. This is the meaning of the log levels:

- debug: you can ignore them (in the default configuration, the log
  service does not show them);

- info: they inform you on what is going on in the system and that
  everything is fine;

- warning: something went wrong or was slightly unexpected, but CMS
  knew how to handle it, or someone fed inappropriate data to CMS (by
  error or on purpose); you may want to check these as they may evolve
  into errors or unexpected behaviors, or hint that a contestant is
  trying to cheat;

- error: an unexpected condition that should not have happened; you
  are really encouraged to take actions to fix them, but the service
  will continue to work (most of the time, ignoring the error and the
  data connected to it);

- critical: a condition so unexpected that the service is really
  startled and refuses to continue working; you are forced to take
  action because with high probability the service will continue
  having the same problem upon restarting.

Warning, error, and critical logs are also displayed in the main page
of AdminWebServer.


Testimonials
------------

CMS has been used in several official and unofficial contests. In
particular we are aware of the following:

- IOI 2012 (International Olympiad in Informatics), September 2012;

- OII 2011 (Italian Olympiad in Informatics), September 2011 and OII
  2012, October 2012;

- AIIO 2012 (Australian Invitational Informatics Olympiad), February
  2012;

- FARIO 2012 (French-Australian Regional Informatics Olympiad), March
  2012;

- Taipei High School Programming Contest, Taiwan, October 2012;

- training camps for the selections of the national teams of Australia,
  Italy and Latvia.

- laboratory exercises and exams of the course "Algorithms and data
  structures" at University of Trento (year 2011-2012).


Support
-------

There is a mailing list, for announcements, discussion about
development and user support. The address is
<contestms@freelists.org>. You can subscribe at
<http://www.freelists.org/list/contestms>.

So far, it is an extremely low traffic mailing list. In the future, we
may consider splitting it in different lists for more specific usage
cases (user support, development, ...).

To help with the troubleshooting, you can collect the complete log
files that are placed in /var/local/log/cms/ (if CMS was running
installed) or in ./log (if it was running from the local copy).
