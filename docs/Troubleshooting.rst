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

  Slightly different, but related, is another issue: CMS may be unable to create new connections to the database because its pool is exhausted. In this case you probably want to modify the ```pool_size``` argument in :gh_blob:`cms/db/__init__.py` or try to spread your users over more instances of ContestWebServer.

Servers
=======

- *Symptom.* Message from ContestWebServer such as: :samp:`WARNING:root:Invalid cookie signature KFZzdW5kdWRlCnAwCkkxMzI5MzQzNzIwCnRw...`

  *Possible cause.* The contest secret key (defined in cms.conf) may have been changed and users' browsers are still attempting to use cookies signed with the old key. If this is the case, the problem should correct itself and won't be seen by users.

- *Symptom.* Ranking Web Server displays wrong data, or too much data.

  *Possible cause.* RWS is designed to handle groups of contests, so it retains data about past contests. If you want to delete previous data, run RWS with the ```-d``` option. See :doc:`RankingWebServer` for more details


Sandbox
=======

- *Symptom.* The Worker fails to evaluate a submission logging about an invalid (empty) output from the manager.

  *Possible cause.* You might have been used a non-statically linked checker. The sandbox prevent dynamically linked executables to work. Try compiling the checker with ```-static```.
