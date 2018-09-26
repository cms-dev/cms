Troubleshooting
***************

Subtle issues with CMS can arise from old versions of libraries or supporting software. Please ensure you are running the minimum versions of each dependency (described in :ref:`installation_dependencies`).

In the next sections we list some known symptoms and their possible causes.

Database
========

- *Symptom.* Error message "Cannot determine OID of function lo_create"

  *Possible cause.* Your database must be at least PostgreSQL 8.x to support large objects used by CMS.

- *Symptom.* Exceptions regarding missing database fields or with the wrong type.

  *Possible cause.* The version of CMS that created the schema in your database is different from the one you are using now. If the schema is older than the current version, you can update the schema as in :ref:`installation_updatingcms`.

- *Symptom.* Some components of CMS fail randomly and PostgreSQL complains about having too many connections.

  *Possible cause.* The default configuration of PostgreSQL may allow insufficiently many incoming connections on the database engine. You can raise this limit by tweaking the ```max_connections``` parameter in ```postgresql.conf``` (`see docs <http://www.postgresql.org/docs/9.1/static/runtime-config-connection.html>`_). This, in turn, requires more shared memory for the PostgreSQL process (see ```shared_buffers``` parameter in `docs <http://www.postgresql.org/docs/9.1/static/runtime-config-resource.html>`_), which may overflow the maximum limit allowed by the operating system. In such case see the suggestions in http://www.postgresql.org/docs/9.1/static/kernel-resources.html#SYSVIPC. Users reported that another way to go is to use a connection pooler like `PgBouncer <https://wiki.postgresql.org/wiki/PgBouncer>`_.

Services
========

- *Symptom.* Some services log error messages like :samp:`Response is missing some fields, ignoring` then disconnect from other services.

  *Possible cause.* It is possible that a service that was trying to establish a connection to another service residing on the same host was assigned by the kernel an outgoing port that is equal to the port it was trying to reach. This can be verified by looking for logs that resemble the following: :samp:`Established connection with 192.168.1.1:43210 (LogService,0) (local address: 192.168.1.1:43210)` (observe the same address repeated twice).

  A workaround for this issue is to first look at what range of ports is reserved by the kernel to "ephemeral" ports (the ones dynamically assigned to outgoing connections). This can be found out with ``cat /proc/sys/net/ipv4/ip_local_port_range``. Then the configuration file of CMS should be updated so that all services are assigned ports outside that range.

Servers
=======

- *Symptom.* Some HTTP requests to ContestWebServer take a long time and fail with 500 Internal Server Error. ContestWebServer logs contain entries such as :samp:`TimeoutError('QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 60',)`.

  *Possible cause.* The server may be overloaded with user requests. You can try to increase the ```pool_timeout``` argument in :gh_blob:`cms/db/__init__.py` or, preferably, spread your users over more instances of ContestWebServer.

- *Symptom.* Message from ContestWebServer such as: :samp:`WARNING:root:Invalid cookie signature KFZzdW5kdWRlCnAwCkkxMzI5MzQzNzIwCnRw...`

  *Possible cause.* The contest secret key (defined in cms.conf) may have been changed and users' browsers are still attempting to use cookies signed with the old key. If this is the case, the problem should correct itself and won't be seen by users.

- *Symptom.* Ranking Web Server displays wrong data, or too much data.

  *Possible cause.* RWS is designed to handle groups of contests, so it retains data about past contests. If you want to delete previous data, run RWS with the ```-d``` option. See :doc:`RankingWebServer` for more details

- *Symptom.* Ranking Web Server prints an "Inconsistent data" exception.

  *Possible cause.* RWS has its own local storage of the score data; this exception usually means that it got corrupted in some way (e.g., some of the data was deleted). If all the scores are still present in the core CMS, the easiest way to fix this is to stop RWS and ProxyService, run ``cmsRankingWebServer -d`` to delete the local storage, then start again RWS and PS.

Sandbox
=======

- *Symptom.* The Worker fails to evaluate a submission logging about an invalid (empty) output from the manager.

  *Possible cause.* You might have been used a non-statically linked checker. The sandbox prevent dynamically linked executables to work. Try compiling the checker with ```-static```. Also, make sure that the checker was compiled for the architecture of the workers (e.g., 32 or 64 bits).

- *Symptom.* The Worker fails to evaluate a submission with a generic failure.

  *Possible cause.* Make sure that the isolate binary that CMS is using has the correct permissions (in particular, its owner is root and it has the suid bit set). Be careful of having multiple isolate binaries in your path. Another reason could be that you are using an old version of isolate.

- *Symptom.* Contestants' solutions fail when trying to write large outputs.

  *Possible cause.* CMS limits the maximum output size from programs being evaluated for security reasons. Currently the limit is 1 GB and can be configured by changing the parameter ``max_file_size`` in :file:`cms.conf`.

Evaluations
===========

- *Symptom.* Submissions that should  exceed memory limit actually pass or exceed the time limits.

  *Possible cause.* You have an active swap partition on the workers; isolate only limit physical memory, not swap usage. Disable the swap with ``sudo swapoff -a``.

- *Symptom.* Re-running evaluations gives very different time or memory usage.

  *Possible cause.* Make sure the workers are configured in a way to minimize resource usage variability, by following isolate's `guidelines <https://github.com/ioi/isolate/blob/c679ae936d8e8d64e5dab553bdf1b22261324315/isolate.1.txt#L292>`_ for reproducible results.
