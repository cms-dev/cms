Creating a contest
******************

Creating a contest from scratch
===============================

The most immediate (but often less practical) way to create a contest in CMS is using the admin interface. You can start the AdminWebServer using the command ``cmsAdminWebServer`` (or using the ResourceService).

After that, you can connect to the server using the address and port specified in :file:`cms.conf`; typically, http://localhost:8889/.

Here, you can create a contest clicking the "+" next to the drop down on the left. After that, you must add the tasks and the users. Up to now, each of these operations is manual; plus, it is usually more practical to work, for example, on a file specifying the contestants' details instead of using the web interface.

Luckily, there is another way to create a contest.


Creating a contest from the filesystem
======================================

Our idea is that CMS does not get in the way of how you create your contest and your tasks (unless you want to). We think that every national IOI selection team and every contest administrator has a preferred way of developing the tasks, and of storing their data in the filesystem, and we do not want to change the way you work.

Instead, we provided CMS with tools to import a contest from a custom filesystem description. The command ``cmsImporter`` reads a filesystem description and creates a new contest from it. The command ``cmsReimporter`` reads a filesystem description and updates an existing contest. Thus, with reimporting you can update, add or remove users or tasks to a contest without losing the existing submissions (unless, of course, they belong to a task or a user that is being deleted).

In order to make these tools compatible with your filesystem format, you have to write a simple Python module that converts your filesystem description to the internal CMS representation of the contest. This is not a hard task: you just have to write an extension of the class ``Loader`` in :gh_blob:`cmscontrib/BaseLoader.py`, implementing missing methods as required by the docstrings. You can use the loader for the Italian format at :gh_blob:`cmscontrib/YamlLoader.py` as a template.

You can also use one of the two formats for which CMS have already a loader.

- The Italian filesystem format supports all the features of CMS, but evolved in a rather messy way and is now full of legacy behaviors and shortcomings. No compatibility in time is guaranteed with this format. If you want to use it anyway, an example of a contest written in this format is in `this GitHub repository <https://github.com/cms-dev/con_test>`_, while its explanation is :doc:`here <External contest formats>`.

- The `Polygon format <https://polygon.codeforces.com/>`_, which is the format used in several contests and by Codeforces. Polygon does not support all of CMS features, but having this importer is especially useful if you have a big repository of tasks in this format.


Creating a contest from an exported contest
===========================================

This option is not really suited for creating new contests but to store and move contest already used in CMS. If you have the dump of a contest exported from CMS, you can import it with ``cmsContestImporter <source>``, where ``<source>`` is the archive filename or directory of the contest.
