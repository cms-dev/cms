RankingWebServer
****************

Description
===========

The **RankingWebServer** (RWS for short) is the web server used to show a live scoreboard to the public.

RWS is designed to be completely separated from the rest of CMS: it has its own configuration file, it doesn't use the PostgreSQL database to store its data and it doesn't communicate with other services using the internal RPC protocol (its code is also in a different package: ``cmsranking`` instead of ``cms``). This has been done to allow contest administrators to run RWS in a different location (on a different network) than the core of CMS, if they don't want to expose a public access to their core network on the internet (for security reasons) or if the on-site internet connection isn't good enough to serve a public website.

To start RWS you have to execute ``cmsRankingWebServer``.

Configuring it
--------------

The configuration file is named :file:`cms.ranking.conf` and RWS will search for it in :file:`/usr/local/etc` and in :file:`/etc` (in this order!). In case it's not found in any of these, RWS will use a hard-coded default configuration that can be found in :gh_blob:`cmsranking/Config.py`. If RWS is not installed then the :gh_tree:`examples` directory will also be checked for configuration files (note that for this to work your working directory needs to be root of the repository). In any case, as soon as you start it, RWS will tell you which configuration file it's using.

The configuration file is a JSON object. The most important parameters are:

* ``bind_address``

  It specifies the address this server will listen on. It can be either an IP address or a hostname (in the latter case the server will listen on all IP addresses associated with that name). Leave it blank or set it to ``null`` to listen on all available interfaces.

* ``http_port``

  It specifies which port to bind the HTTP server to. If set to ``null`` it will be disabled. We suggest to use a high port number (like 8080, or the default 8890) to avoid the need to start RWS as root, and then use a reverse proxy to map port 80 to it (see :ref:`rankingwebserver_using-a-proxy` for additional information).

* ``https_port``

  It specifies which port to bind the HTTPS server to. If set to ``null`` it will be disabled, otherwise you need to set ``https_certfile`` and ``https_keyfile`` too. See :ref:`rankingwebserver_securing-the-connection-between-ss-and-rws` for additional information.

* ``username`` and ``password``

  They specify the credentials needed to alter the data of RWS. We suggest to set them to long random strings, for maximum security, since you won't need to remember them. ``username`` cannot contain a colon.

  .. warning::

    Remember to change the ``username`` and ``password`` every time you set up a RWS. Keeping the default ones will leave your scoreboard open to illegitimate access.

To connect the rest of CMS to your new RWS you need to add its connection parameters to the configuration file of CMS (i.e. :file:`cms.conf`). Note that you can connect CMS to multiple RWSs, each on a different server and/or port. The parameter you need to change is ``rankings``, a list of URLs in the form::

    <scheme>://<username>:<password>@<hostname>:<port>/<prefix>

where ``scheme`` can be either ``http`` or ``https``, ``username``, ``password`` and ``port`` are the values specified in the configuration file of the RWS and ``prefix`` is explained in :ref:`rankingwebserver_using-a-proxy` (it will generally be blank, otherwise it needs to end with a slash). If any of your RWSs uses the HTTPS protocol you also need to specify the ``https_certfile`` configuration parameter. More details on this in :ref:`rankingwebserver_securing-the-connection-between-ss-and-rws`.

You also need to make sure that RWS is able to keep enough simultaneously active connections by checking that the maximum number of open file descriptors is larger than the expected number of clients. You can see the current value with ``ulimit -Sn`` (or ``-Sa`` to see all limitations) and change it with ``ulimit -Sn <value>``. This value will be reset when you open a new shell, so remember to run the command again. Note that there may be a hard limit that you cannot overcome (use ``-H`` instead of ``-S`` to see it). If that's still too low you can start multiple RWSs and use a proxy to distribute clients among them (see :ref:`rankingwebserver_using-a-proxy`).

Managing it
===========

RWS doesn't use the PostgreSQL database. Instead, it stores its data in :file:`/var/local/lib/cms/ranking` (or whatever directory is given as ``lib_dir`` in the configuration file) as a collection of JSON files. Thus, if you want to backup the RWS data, just make a copy of that directory. RWS modifies this data in response to specific (authenticated) HTTP requests it receives.

The intended way to get data to RWS is to have the rest of CMS send it. The service responsible for that is ProxyService (PS for short). When PS is started for a certain contest, it will send the data for that contest to all RWSs it knows about (i.e. those in its configuration). This data includes the contest itself (its name, its begin and end times, etc.), its tasks, its users and the submissions received so far. Then it will continue to send new submissions as soon as they are scored and it will update them as needed (for example when a user uses a token). Note that hidden users (and their submissions) will not be sent to RWS.

There are also other ways to insert data into RWS: send custom HTTP requests or directly write JSON files. They are both discouraged but, at the moment, they are the only way to add team information to RWS (see :gh_issue:`65`).

Logo, flags and faces
---------------------

RWS can also display a custom global logo, a flag for each team and a photo ("face") for each user. Again, the only way to add these is to put them directly in the data directory of RWS:

* the logo has to be saved right in the data directory, named "logo" with an appropriate extension (e.g. :file:`logo.png`), with a recommended resolution of 200x160;
* the flag for a team has to be saved in the "flags" subdirectory, named as the team's name with an appropriate extension (e.g. :file:`ITA.png`);
* the face for a user has to be saved in the "faces" subdirectory, named as the user's username with an appropriate extension (e.g. :file:`ITA1.png`).

We support the following extensions: .png, .jpg, .gif and .bmp.

.. _rankingwebserver_removing-data:

Removing data
-------------

PS is only able to create or update data on RWS, but not to delete it. This means that, for example, when a user or a task is removed from CMS it will continue to be shown on RWS. To fix this you will have to intervene manually. The ``cmsRWSHelper`` script is designed to make this operation straightforward. For example, calling :samp:`cmsRWSHelper delete user {username}` will cause the user *username* to be removed from all the RWSs that are specified in :file:`cms.conf`. See ``cmsRWSHelper --help`` and :samp:`cmsRWSHelper {action} --help` for more usage details.

In case using ``cmsRWSHelper`` is impossible (for example because no :file:`cms.conf` is available) there are alternative ways to achieve the same result, presented in decreasing order of difficulty and increasing order of downtime needed.

* You can send a hand-crafted HTTP request to RWS (a ``DELETE`` method on the :samp:`/{entity_type}/{entity_id}` resource, giving credentials by Basic Auth) and it will, all by itself, delete that object and all the ones that depend on it, recursively (that is, when deleting a task or a user it will delete its submissions and, for each of them, its subchanges).

* You can stop RWS, delete only the JSON files of the data you want to remove and start RWS again. In this case you have to *manually* determine the depending objects and delete them as well.

* You can stop RWS, remove *all* its data (either by deleting its data directory or by starting RWS with the ``--drop`` option), start RWS again and restart PS for the contest you're interested in, to have it send the data again.

.. note::

    When you change the username of an user, the name of a task or the name of a contest in CMS and then restart PS, that user, task or contest will be duplicated in RWS and you will need to delete the old copy using this procedure.

Multiple contests
-----------------

Since the data in RWS will persist even after the PS that sent it has been stopped it's possible to have many PS serve the same RWS, one after the other (or even simultaneously). This allows to have many contests inside the same RWS. The users of the contests will be merged by their username: that is, two users of two different contests will be shown as the same user if they have the same username. To show one contest at a time it's necessary to delete the previous one before adding the next one (the procedure to delete an object is the one described in :ref:`rankingwebserver_removing-data`).

Keeping the previous contests may seem annoying to contest administrators who want to run many different and independent contests one after the other, but it's indispensable for many-day contests like the IOI.

.. _rankingwebserver_securing-the-connection-between-ss-and-rws:

Securing the connection between PS and RWS
==========================================

RWS accepts data only from clients that successfully authenticate themselves using the HTTP Basic Access Authentication. Thus an attacker that wants to alter the data on RWS needs the username and the password to authenticate its request. If they are random (and long) enough the attacker cannot guess them but may eavesdrop the plaintext HTTP request between PS and RWS. Therefore we suggest to use HTTPS, that encrypts the transmission with TLS/SSL, when the communication channel between PS and RWS is not secure.

HTTPS does not only protect against eavesdropping attacks but also against active attacks, like a man-in-the-middle. To do all of this it uses public-key cryptography based on so-called certificates. In our setting RWS has a public certificate (and its private key). PS has access to a copy to the same certificate and can use it to verify the identity of the receiver before sending any data (in particular before sending the username and the password!). The same certificate is then used to establish a secure communication channel.

The general public does not need to use HTTPS, since it is not sending nor receiving any sensitive information. We think the best solution is, for RWS, to listen on both HTTP and HTTPS ports, but to use HTTPS only for private internal use. Not having final users use HTTPS also allows you to use home-made (i.e. self-signed) certificates without causing apocalyptic warnings in the users' browsers.

Note that users will still be able to connect to the HTTPS port if they discover its number, but that is of no harm. Note also that RWS will continue to accept incoming data even on the HTTP port; simply, PS will not send it.

To use HTTPS we suggest you to create a self-signed certificate, use that as both RWS's and PS's ``https_certfile`` and use its private key as RWS's ``https_keyfile``. If your PS manages multiple RWSs we suggest you to use a different certificate for each of those and to create a new file, obtained by joining all certificates, as the ``https_certfile`` of PS. Alternatively you may want to use a Certificate Authority to sign the certificates of RWSs and just give its certificate to PS. Details on how to do this follow.

.. note::
   Please note that, while the indications here are enough to make RWS work, computer security is a delicate subject; we urge you to be sure of what you are doing when setting up a contest in which "failure is not an option".

Creating certificates
---------------------

A quick-and-dirty way to create a self-signed certificate, ready to be used with PS and RWS, is:

.. sourcecode:: bash

    openssl req -newkey rsa:1024 -nodes -keyform PEM -keyout key.pem \
                -new -x509 -days 365 -outform PEM -out cert.pem -utf8

You will be prompted to enter some information to be included in the certificate. After you do this you'll have two files, :file:`key.pem` and :file:`cert.pem`, to be used respectively as the ``https_keyfile`` and ``https_certfile`` for PS and RWS.

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

As a security measure, we recommend not to run RWS as root but to run it as an unprivileged user instead. This means that RWS cannot listen on port 80 and 443 (the default HTTP and HTTPS ports) but it needs to listen on ports whose number is higher than or equal to 1024. This is not a big issue, since we can use a reverse proxy to map the default HTTP and HTTPS ports to the ones used by RWS. We suggest you to use nginx, since it has been already proved successfully  for this purpose (some users have reported that other software, like Apache, has some issues, probably due to the use of long-polling HTTP requests by RWS).

A reverse proxy is most commonly used to map RWS from a high port number (say 8080) to the default HTTP port (i.e. 80), hence we will assume this scenario throughout this section.

With nginx it's also extremely easy to do some URL mapping. That is, you can make RWS "share" the URL space of port 80 with other servers by making it "live" inside a prefix. This means that you will access RWS using an URL like "http://myserver/prefix/".

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

The example configuration file provided in :ref:`running-cms_recommended-setup` already contains sections for RWS.

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

The suggested setup (the one that we also used at the IOI 2012) is to make RWS listen on both HTTP and HTTPS ports (we used 8080 and 8443), to use nginx to map port 80 to port 8080, to make all three ports (80, 8080 and 8443) accessible from the internet, to make PS connect to RWS via HTTPS on port 8443 and to use a Certificate Authority to generate certificates (the last one is probably an overkill).

At the IOI we had only one server, running on a 2 GHz machine, and we were able to serve about 1500 clients simultaneously (and, probably, we were limited to this value by a misconfiguration of nginx). This is to say that you'll likely need only one public RWS server.

If you're starting RWS on your server remotely, for example via SSH, make sure the ``screen`` command is your friend :-).

