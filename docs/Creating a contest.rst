Creating a contest
******************

Creating a contest from scratch
===============================

The most immediate (and less practical) way to create a contest in CMS is using the admin interface. You can start the AdminWebServer using the command ``cmsAdminWebServer``.

After that, you can connect to the server using the address and port specified in :file:`cms.conf`; typically, http://localhost:8889/.

Here, you can create a contest clicking the "+" next to the drop down on the left. After that, you must add the tasks and the users. Up to now, each of these operations is manual; plus, it is usually more practical to work, for example, on a file specifying the contestants' details instead of using the web interface.

Luckily, there is another way to create a contest.


Creating a contest from the filesystem
======================================

The idea we wanted to implement is that CMS does not get in the way of how you create your contest and your tasks (unless you want to). We think that every national IOI selection team and every contest administrator has a preferred way of developing the tasks, and of storing their data in the filesystem, and we do not want to change the way you work.

Instead, you are encouraged to write an "importer", that is a piece of software that reads data from your filesystem structure and creates the contest in the database. You can also write a "reimporter" if you want to change the contest details without losing the data (submissions, user tests, ...) already uploaded.

We provide examples of both importer and reimporter that target the format used by the Italian IOI selection team. You can either adapt them to the format you use, or decide to use the Italian format. An example of a contest written in this format is in `this GitHub repository <https://github.com/cms-dev/con_test>`_, while its explanation is :doc:`here <External contest formats>`.


Creating a contest from an exported contest
===========================================

This option is not really suited for creating new contests but to store and move contest already used in CMS. If you have the dump of a contest exported from CMS, you can import it with ``cmsContestImporter <source>``, where ``<source>`` is the archive filename or directory of the contest.

