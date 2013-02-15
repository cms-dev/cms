RankingWebServer
****************

Description
===========

The **RankingWebServer** (RWS for short) is the web server used to show a live scoreboard to the public.

RWS is designed to be completely separated from the rest of CMS: it has its own configuration file, it doesn't use the PostgreSQL database to store its data and it doesn't communicate with other services using the internal RPC protocol (its code is also in a different package: ``cmsranking`` instead of ``cms``). This has been done to allow contest administrators to run RWS in a different location (on a different network) than the core of CMS, if they don't want to expose a public access to their core network on the internet (for security reasons) or if the on-site internet connection isn't good enough to serve a public website.

Running it
==========

To start RWS you have to execute ``cmsRankingWebServer`` if you have installed CMS (by running ``./setup.py install``), and execute ``$REPO/cmsranking/RankingWebServer.py`` otherwise (where ``$REPO`` has the same meaning as in the README).

Configuring it
--------------

The configuration file is named :file:`cms.ranking.conf` and RWS will search for it in :file:`/usr/local/etc` and in :file:`/etc` (in this order!). In case it's not found in any of these, RWS will use a hard-coded default configuration that can be found in :file:`$REPO/cmsranking/Config.py`. If RWS is not installed then the ``./examples`` directory will also be checked for configuration files (note that for this to work your working directory needs to be ``$REPO``). In any case, as soon as you start it, RWS will tell you which configuration file it's using.

The configuration file is a JSON object. The most important parameters are:

* ``bind_address``

  It specifies the address this server will listen on. It can be either an IP address or a hostname (in the latter case the server will listen on all IP addresses associated with that name). Leave it blank or set it to ``null`` to listen on all available interfaces.

* ``http_port``

  It specifies which port to bind the HTTP server to. If set to ``null`` it will be disabled. We suggest to use a high port number (like 8080, or the default 8890) to avoid the need to start RWS as root, and then use a reverse proxy to map port 80 to it (see :ref:`rankingwebserver_using-a-proxy` for additional information).

* ``https_port``

  It specifies which port to bind the HTTPS server to. If set to ``null`` it will be disabled, otherwise you need to set ``https_certfile`` and ``https_keyfile`` too. See :ref:`rankingwebserver_securing-the-connection-between-ss-and-rws` for additional information.

* ``username`` and ``password``

  They specify the credentials needed to alter the data of RWS. We suggest to set them to long random strings, for maximum security, since you won't need to remember them. ``username`` cannot contain a colon.

To connect the rest of CMS to your new RWS you need to add its connection parameters to the configuration file of CMS (i.e. :file:`cms.conf`). Note that you can connect CMS to multiple RWSs, each on a different server and/or port. There are three parameters to do it, three lists of the same length: ``ranking_address``, ``ranking_username`` and ``ranking_password``. The elements in ``ranking_address`` are lists of three elements: the protocol (either "http" or "https"), the address (IP address or hostname) and the port. If any of your RWSs uses the HTTPS protocol you also need to specify the ``https_certfile`` configuration parameter. More details on this in :ref:`rankingwebserver_securing-the-connection-between-ss-and-rws`.

You also need to make sure that RWS is able to keep enough simultaneously active connections by checking that the maximum number of open file descriptors is larger than the expected number of clients. You can see the current value with ``ulimit -Sn`` (or ``-Sa`` to see all limitations) and change it with ``ulimit -Sn <value>``. This value will be reset when you open a new shell, so remember to run the command again. Note that there may be a hard limit that you cannot overcome (use ``-H`` instead of ``-S`` to see it).

Managing it
===========

RWS doesn't use the PostgreSQL database. Instead, it stores its data in :file:`/var/local/lib/cms/ranking` (or whatever directory is given as ``lib_dir`` in the configuration file) as a collection of JSON files. Thus, if you want to backup the RWS data, just make a copy of that directory. RWS modifies this data in response to specific (authenticated) HTTP requests it receives.

The intended way to get data to RWS is to have the rest of CMS send it. The service responsible for that is ScoringService (SS for short). When SS is started for a certain contest, it'll send the data for that contest to all RWSs it knows about (i.e. those in its configuration). This data includes the contest itself (its name, its begin and end times, etc.), its tasks, its users and the submissions received so far. Then it'll continue to send new submissions as soon as they're scored and it'll update them as needed (for example when a users uses a token). Note that hidden users (and their submissions) won't be sent to RWS.

There are also other ways to insert data into RWS: send custom HTTP requests or directly write JSON files. They're both discouraged but, at the moment, they're the only way to add team information to RWS (see :gh_issue:`65`).

Logo, flags and faces
---------------------

RWS can also display a custom global logo, a flag for each team and a photo ("face") for each user. Again, the only way to add these is to put them directly in the data directory of RWS:

* the logo has to be saved in the top-level directory, named "logo" with an appropriate extension;
* the flag for a team has to be saved in the "flags" directory, named as the team's name with an appropriate extension;
* the face for a user has to be saved in the "faces" directory, named as the user's username with an appropriate extension.

We support the following extensions: .png, .jpg, .gif and .bmp.

.. _rankingwebserver_removing-data:

Removing data
-------------

SS is only able to create or update data on RWS, but not to delete it. This means that, for example, when a user or a task is removed from CMS it'll continue to be shown on RWS. There are several ways to fix that (presented in increasing order of difficulty and decreasing order of downtime needed).

* You can stop RWS, remove all its data (either by deleting its data directory or by starting RWS with the ``--drop`` option), start RWS again and restart SS for the contest you're interested in, to have it send the data again.

* You can stop RWS, delete only the JSON files of the data you want to remove and start RWS again. Note that if you remove an object (e.g. a user) you have to remove all objects (e.g. the submissions) that depend on it, that is you have to simulate the "on delete cascade" behavior of SQL by hand. (When you delete a submission remember to delete also the related subchanges).

* You can keep RWS running and send a hand-crafted HTTP request to it and it'll, all by itself, delete the objects you want to remove and all the ones that depend on it.

Note that when you change the username of an user, the name of a task or the name of a contest in CMS and then restart SS, that user, task or contest will be duplicated in RWS and you will need to delete the old copy using this procedure.

Multiple contests
-----------------

Since the data in RWS will persist even after the SS that sent it has been stopped it's possible to have many SS serve the same RWS, one after the other (or even simultaneously). This allows to have many contests inside the same RWS. The users of the contests will be merged by their username: that is, two users of two different contests will be shown as the same user if they have the same username. To show one contest at a time it's necessary to delete the previous one before adding the next one (the procedure to delete an object is the one described in :ref:`rankingwebserver_removing-data`).

Keeping the previous contests may seem annoying to contest administrators who want to run many different and independent contests one after the other, but it's indispensable for many-day contests like the IOI.

.. _rankingwebserver_securing-the-connection-between-ss-and-rws:

Securing the connection between SS and RWS
==========================================

RWS accepts data only from clients that successfully authenticate themselves using the HTTP Basic Access Authentication. Thus an attacker that wants to alter the data on RWS needs the username and the password to authenticate its request. If they are random (and long) enough he/she can't guess them but, since they're sent as plaintext in the HTTP request, he/she could read them if he/she can eavesdrop the communication channel between SS and RWS. Therefore we suggest to use HTTPS, that encrypts the transmission with TLS/SSL, when the communication channel between SS and RWS isn't secure.
HTTPS doesn't only protect against eavesdropping attacks but also against more active attacks, like a man-in-the-middle. To do all of this it uses public-key cryptography based on so-called certificates. In our setting RWS has a certificate (and its private key) that is given to SS, that verifies its authenticity before sending any data (in particular before sending the username and the password!). The same certificate is then used to establish a secure communication channel.

The general public doesn't need to use HTTPS since it's not sending nor receiving any sensitive information. We think the best solution is, for RWS, to listen on both HTTP and HTTPS ports, but to use HTTPS only for private internal use.
Not having final users use HTTPS also allows you to use home-made (i.e. self-signed) certificates without causing apocalyptic warnings in the users' browsers.
Note that users will still be able to connect to the HTTPS port if they discover its number, but that's of no harm. Note also that RWS will continue to accept incoming data even on the HTTP port, it's just that SS won't send it.

To use HTTPS we suggest you to create a self-signed certificate, use that as both RWS's and SS's ``https_certfile`` and use its private key as RWS's ``https_keyfile``. If your SS manages multiple RWSs we suggest you to use a different certificate for each of those and to create a new file, obtained by joining all certificates, as the ``https_certfile`` of SS. Alternatively you may want to use a Certificate Authority to sign the certificates of RWSs and just give its certificate to SS. Details on how to do this follow.

Creating certificates
---------------------

A quick-and-dirty way to create a self-signed certificate, ready to be used with SS and RWS, is:

.. sourcecode:: bash

    openssl req -newkey rsa:1024 -nodes -keyform PEM -keyout key.pem \
                -new -x509 -days 365 -outform PEM -out cert.pem -utf8

You will be prompted to enter some information to be included in the certificate. After you do this you'll have two files, :file:`key.pem` and :file:`cert.pem`, to be used respectively as the ``https_keyfile`` and ``https_certfile`` for SS and RWS.

Once you have a self-signed certificate you can use it as a :abbr:`CA (Certificate Authority)` to sign other certificates. If you have a ``ca_key.pem``/``ca_cert.pem`` pair that you want to use to create a ``key.pem``/``cert.pem`` pair signed by it, do:

.. sourcecode:: bash

    openssl req -newkey rsa:1024 -nodes -keyform PEM -keyout key.pem \
                -new -outform PEM -out cert_req.pem -utf8
    openssl x509 -req -in cert_req.pem -out cert.pem -days 365 \
                 -CA ca_cert.pem -CAkey ca_key.pem -set_serial <serial>
    rm cert_req.pem

Where ``<serial>`` is a number that has to be unique among all certificates signed by a certain CA.

For additional information on certificates see `the official Python documentation on SSL <http://docs.python.org/library/ssl.html#ssl-certificates>`_.

.. _rankingwebserver_using-a-proxy:

Using a proxy
=============

As a security measure, we recommend not to run RWS as root but to run it as an unprivileged user instead. This means that RWS cannot listen on port 80 and 443 (the default HTTP and HTTPS ports) but it needs to listen on ports whose number is higher than or equal to 1024. This isn't a big issue, since we can use a reverse proxy to map the default HTTP and HTTPS ports to the ones used by RWS. We suggest you to use nginx, since it has been already successfully used for this purpose (some users have reported that other software, like Apache, has some issues, probably due to the use of long-polling HTTP requests by RWS).

A reverse proxy is most commonly used to map RWS from a high port number (say 8080) to the default HTTP port (i.e. 80), hence we will assume this scenario throughout this section.

With nginx it's also extremely easy to do some URL mapping. That is, you can make RWS "share" the URL space of port 80 with other servers by making it "live" inside a prefix. This means that you will access RWS using an URL like "http://myserver/prefix/".
Note that, however, an "unprefixed" port has to be publicly available and that is the port that has to be written in the ``cms.conf`` file since it's needed by SS (because it's currently unable to use a prefixed RWS, see :gh_issue:`36`).

We'll provide here an example configuration file for nginx. This is just the "core" of the file, but other options need to be added in order for it to be complete and usable by nginx. These bits are different on each distribution, so the best is for you to take the default configuration file provided by your distribution and adapt it to contain the following code:

.. sourcecode:: none

    http {
      server {
        listen 80;
        location ^~ /prefix/ {
          proxy_pass http://127.0.0.1:8080/;
          proxy_buffering off;
        }
      }
    }

The trailing slash is needed in the argument of both the ``location`` and the ``proxy_pass`` option. The ``proxy_buffering`` option is needed for the live-update feature to work correctly (this option can be moved into ``server`` or ``http`` to give it a larger scope). To better configure how the proxy connects to RWS you can add an ``upstream`` section inside the ``http`` module, named for example ``rws``, and then use ``proxy_pass http://rws/``. This also allows you to use nginx as a load balancer in case you have many RWSs.

.. upstream rws {
     server 127.0.0.1:8080;
   }

.. TODO
   The proxy_read_timeout option causes the long-polling requests to be interrupted by nginx if they don't send data for 60s (default value). We may want to increase that and check if other timeout options apply too. We could also check if it makes sense to set the proxy_http_version option to 1.1 and if we want to set some header-related options (like proxy_set_header) as we do in the nginx.conf.sample for CWS.
   It would also be nice if we could apply the options needed for long-polling (i.e. buffering and timeouts) only to requests for that URL (i.e. /events), perhaps by using a nested location or an if block? Consider also the use of the X-Accel-Buffering header.

If you decide to have HTTPS for private internal use only, as suggested above (that is, you want your users to use only HTTP), then it's perfectly fine to keep using a high port number for HTTPS and not map it to port 443, the standard HTTPS port.
Note also that you could use nginx as an HTTPS endpoint, i.e. make nginx decrypt the HTTPS trasmission and redirect it, as cleartext, into RWS's HTTP port. This allows to use two different certificates (one by nginx, one by RWS directly), although we don't see any real need for this.

Tuning nginx
------------

If you're setting up a private RWS, for internal use only, and you expect just a handful of clients then you don't need to follow the advices given in this section. Otherwise please read on to see how to optimize nginx to handle many simultaneous connections, as required by RWS.

First, set the ``worker_processes`` option [#nginx_worker_processes]_ of the core module to the number of CPU or cores on your machine.
Next you need to tweak the ``events`` module: set the ``worker_connections`` option [#nginx_worker_connections]_ to a large value, at least the double of the expected number of clients divided by ``worker_processes``. You could also set the ``use`` option [#nginx_use]_ to an efficient event-model for your platform (like epoll on linux), but having nginx automatically decide it for you is probably better.
Then you also have to raise the maximum number of open file descriptors. Do this by setting the ``worker_rlimit_nofile`` option [#nginx_worker_rlimit_nofile]_ of the core module to the same value of ``worker_connections`` (or greater).
You could also consider setting the ``keepalive_timeout`` option [#nginx_keepalive_timeout]_ to a value like ``30s``. This option can be placed inside the ``http`` module or inside the ``server`` or ``location`` sections, based on the scope you want to give it.

For more information see the official nginx documentation:

.. [#nginx_worker_processes] http://wiki.nginx.org/CoreModule#worker_processes
.. [#nginx_worker_connections] http://wiki.nginx.org/EventsModule#worker_connections
.. [#nginx_use] http://wiki.nginx.org/EventsModule#use
.. [#nginx_worker_rlimit_nofile] http://wiki.nginx.org/CoreModule#worker_rlimit_nofile
.. [#nginx_keepalive_timeout] http://wiki.nginx.org/HttpCoreModule#keepalive_timeout

Some final suggestions
======================

The suggested setup (the one that we also used at the IOI 2012) is to make RWS listen on both HTTP and HTTPS ports (we used 8080 and 8443), to use nginx to map port 80 to port 8080, to make all three ports (80, 8080 and 8443) accessible from the internet, to make SS connect to RWS via HTTPS on port 8443 and to use a Certificate Authority to generate certificates (the last one is probably an overkill).

At the IOI we had only one server, running on a 2 GHz machine, and we were able to serve about 1500 clients simultaneously (and, probably, we were limited to this value by a misconfiguration of nginx). This is to say that you'll likely need only one public RWS server.

If you're starting RWS on your server remotely, for example via SSH, make sure the ``screen`` command is your friend :-).

