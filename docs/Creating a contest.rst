Creating a contest
******************

Creating a contest from scratch
===============================

The most immediate (but often less practical) way to create a contest in CMS is using the admin interface. You can start the AdminWebServer using the command ``cmsAdminWebServer`` (or using the ResourceService).

After that, you can connect to the server using the address and port specified in :file:`cms.conf`; by default, http://localhost:8889/. Here, you can create a contest clicking on the link in the left column. After this, you must similarly add tasks and users.

Since the details of contests, tasks and users usually live somewhere in the filesystem, it is more practical to use an importer to create them in CMS automatically.


Creating a contest from the filesystem
======================================

CMS philosophy is that, unless you want, it should not change how you develop tasks, or how you store contests, tasks and user information.

To achieve this goal, CMS has tools to import a contest from a custom filesystem description. There are commands which read a filesystem description and use it to create contests, tasks, or users. Specifically: the ``cmsImportContest``, ``cmsImportTasl``, ``cmsImportUser`` commands (by default) will analyze the directory given as first argument and detect if it can be loaded (respectively) as a new contest, task, user. Run the commands with a ``-h`` or ``--help`` flag in order to better understand how they can be used.

In order to make these tools compatible with your filesystem format, you have to write a Python module that converts your filesystem description to the internal CMS representation of the contest. You have to extend the classes ``ContestLoader``, ``TaskLoader``, ``UserLoader`` defined in :gh_blob:`cmscontrib/loaders/base_loader.py`, implementing missing methods as required by the docstrings (or use one of the existing loaders in :file:`cmscontrib/loaders/` as a template). If you do not use complex task types, or many different configurations, loaders can be very simple.

Out of the box, CMS offers loaders for two formats:

- The Italian filesystem format supports all the features of CMS. No compatibility in time is guaranteed with this format. If you want to use it, an example of a contest written in this format is in `this GitHub repository <https://github.com/cms-dev/con_test>`_, while its explanation is :doc:`here <External contest formats>`.

- The `Polygon format <https://polygon.codeforces.com/>`_, which is the format used in several contests and by Codeforces. Polygon does not support all of CMS features, but having this importer is especially useful if you have a big repository of tasks in this format.

CMS also has several convenience scripts to add data to the database specifying it on the command line, or to remove data from the database. Look in :file:`cmscontrib` or at commands starting with ``cmsAdd`` or ``cmsRemove``.

Creating a contest from an exported contest
===========================================

This option is not really suited for creating new contests but to store and move contest already used in CMS. If you have the dump of a contest exported from CMS, you can import it with ``cmsDumpImporter <source>``, where ``<source>`` is the archive filename or directory of the contest.
