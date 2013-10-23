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


Servers
=======

- *Symptom.* Message from ContestWebServer such as: :samp:`WARNING:root:Invalid cookie signature KFZzdW5kdWRlCnAwCkkxMzI5MzQzNzIwCnRw...`

  *Possible cause.* The contest secret key (defined in cms.conf) may have been changed and users' browsers are still attempting to use cookies signed with the old key. If this is the case, the problem should correct itself and won't be seen by users.

- *Symptom.* Ranking Web Server displays wrong data, or too much data.

  *Possible cause.* RWS is designed to handle groups of contests. If you want to delete the previous data, run it with the ```-d``` option. See :doc:`RankingWebServer` for more details

- *Symptom.* Ranking Web Server misbehaving

  *Possible cause.* Ensure you are running Tornado 2.0 or higher. (see :gh_issue:`2`)


Sandbox
=======

- *Symptom.* The Worker fails to evaluate a submission logging about an invalid (empty) output from the manager.

  *Possible cause.* You might have been used a non-statically linked checker. The sandbox prevent dynamically linked executables to work. Try compiling the checker with ```-static```.


Importers
=========

- *Symptom.* Importing a contest with ContestImporter fails.

  *Possible cause.* The contest was imported with a previous version of CMS. Wait for us to provide update scripts for exports, or contact us for the fast solution.


Configuration
=============

- *Symptom.* ResourceService keeps restarting its services.

  *Possible cause.* As stated in the README, a reason for this could be that the "process_cmdline" in the configuration isn't suited to your system. To find the one that suits you, you can run a service by hand (for example *cmsLogService*), then run :samp:`ps aux` and search for a process that looks like :samp:`/usr/bin/python2 /usr/local/bin/cmsLogService`. The "process_cmdline" corresponding to this would be :samp:`["/usr/bin/python2", "/usr/local/bin/cms%s", "%d"]`. This value is the default one and should work well on most Ubuntu systems, but for example on some Gentoo systems you may need to use :samp:`["/usr/bin/python2.7", "/usr/bin/cms%s", "%d"]`.
