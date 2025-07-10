External contest formats
************************

There are two different sets of needs that external contest formats strive to satisfy.

- The first is that of contest admins, that for several reasons (storage of old contests, backup, distribution of data) want to export the contest original data (tasks, contestants, ...) together with all data generated during the contest (from the contestants, submissions, user tests, ... and from the system, evaluations, scores, ...). Once a contest has been exported in this format, CMS must be able to reimport it in such a way that the new instance is indistinguishable from the original.

- The second is that of contest creators, that want an environment that helps them design tasks, testcases, and insert the contest data (contestant names and so on). The format needs to be easy to write, understand and modify, and should provide tools to help developing and testing the tasks (automatic generation of testcases, testing of solutions, ...). CMS must be able to import it as a new contest, but also to import it over an already created contest (after updating some data).

CMS provides an exporter :file:`cmsDumpExporter` and an importer :file:`cmsDumpImporter` working with a format suitable for the first set of needs. This format comprises a dump of all serializable data regarding the contest in a JSON file, together with the files needed by the contest (testcases, statements, submissions, user tests, ...). The exporter and importer understand also compressed versions of this format (i.e., in a zip or tar file). For more information run

.. sourcecode:: bash

    cmsDumpExporter -h
    cmsDumpImporter -h

As for the second set of needs, the philosophy is that CMS should not force upon contest creators a particular environment to write contests and tasks. Therefore, CMS provides general-purpose commands, :file:`cmsAddUser`, :file:`cmsAddTask` and :file:`cmsAddContest`. These programs have no knowledge of any specific on-disk format, so they must be complemented with a set of "loaders", which actually interpret your files and directories. You can tell the importer or the reimported wich loader to use with the ``-L`` flag, or just rely and their autodetection capabilities. Running with ``-h`` flag will list the available loaders.

At the moment, CMS comes with two loaders pre-installed:

* :file:`italy_yaml`, for tasks/users stored in the "Italian Olympiad" format.
* :file:`polygon_xml`, for tasks made with `Polygon <https://polygon.codeforces.com/>`__.

The first one is not particularly suited for general use (see below for more details), so, if you don't want to migrate to one of the aforementioned formats then we encourage you to **write a loader** for your favorite format and then get in touch with CMS authors to have it accepted in CMS. See the file :gh_blob:`cmscontrib/loaders/base_loader.py` for some hints.


Italian import format
=====================

You can follow this description looking at `this example <https://github.com/cms-dev/con_test>`_. A contest is represented in one directory, containing:

- a YAML file named :file:`contest.yaml`, that describes the general contest properties;

- for each task :samp:`{task_name}`, a directory :file:`{task_name}` that contains the description of the task and all the files needed to build the statement of the problem, the input and output cases, the reference solution and (when used) the solution checker.

The exact structure of these files and directories is detailed below. Note that this loader is not particularly reliable and providing confusing input to it may lead to create inconsistent or strange data on the database. For confusing input we mean parameters and/or files from which it can infer no or multiple task types or score types.

As the name suggest, this format was born among the Italian trainers group, thus many of the keywords detailed below used to be in Italian. Now they have been translated to English, but Italian keys are still recognized for backward compatibility and are detailed below. Please note that, although so far this is the only format natively supported by CMS, it is far from ideal: in particular, it has grown in a rather untidy manner in the last few years (CMS authors are planning to develop a new, more general and more organic, format, but unfortunately it doesn't exist yet).

For the reasons above, instead of converting your tasks to the Italian format for importing into CMS, it is suggested to write a loader for the format you already have. Please get in touch with CMS authors to have support.

.. warning::

   The authors offer no guarantee for future compatibility for this format. Again, if you use it, you do so at your own risk!


General contest description
---------------------------

The :file:`contest.yaml` file is a plain YAML file, with at least the following keys.

- ``name`` (string; also accepted: ``nome_breve``): the contest's short name, used for internal reference (and exposed in the URLs); it has to match the name of the directory that serves as contest root.

- ``description`` (string; also accepted: ``nome``): the contest's name (description), shown to contestants in the web interface.

- ``tasks`` (list of strings; also accepted: ``problemi``): a list of the tasks belonging to this contest; for each of these strings, say :samp:`{task_name}`, there must be a directory called :file:`{task_name}` in the contest directory, with content as described :ref:`below <externalcontestformats_task-directory>`; the order in this list will be the order of the tasks in the web interface.

- ``users`` (list of associative arrays; also accepted: ``utenti``): each of the elements of the list describes one user of the contest; the exact structure of the record is described :ref:`below <externalcontestformats_user-description>`.

- ``token_mode``: the token mode for the contest, as in :ref:`configuringacontest_tokens`; it can be ``disabled``, ``infinite`` or ``finite``; if this is not specified, the loader will try to infer it from the remaining token parameters (in order to retain compatibility with the past), but you are not advised to rely on this behavior.

The following are optional keys.

- ``start`` (integer; also accepted: ``inizio``): the UNIX timestamp of the beginning of the contest (copied in the ``start`` field); defaults to zero, meaning that contest times haven't yet been decided.

- ``stop`` (integer; also accepted: ``fine``): the UNIX timestamp of the end of the contest (copied in the ``stop`` field); defaults to zero, meaning that contest times haven't yet been decided.

- ``timezone`` (string): the timezone for the contest (e.g., "Europe/Rome").

- ``per_user_time`` (integer): if set, the contest will be USACO-like (as explained in :ref:`configuringacontest_usaco-like-contests`); if unset, the contest will be traditional (not USACO-like).

- ``token_*``: additional token parameters for the contest, see :ref:`configuringacontest_tokens` (the names of the parameters are the same as the internal names described there).

- ``max_*_number`` and ``min_*_interval`` (integers): limitations for the whole contest, see :ref:`configuringacontest_limitations` (the names of the parameters are the same as the internal names described there); by default they're all unset.


.. _externalcontestformats_user-description:

User description
----------------

Each contest user (contestant) is described in one element of the ``utenti`` key in the :file:`contest.yaml` file. Each record has to contains the following keys.

- ``username`` (string): obviously, the username.

- ``password`` (string): obviously as before, the user's password.

The following are optional keys.

- ``first_name`` (string; also accepted: ``nome``): the user real first name; defaults to the empty string.

- ``last_name`` (string; also accepted: ``cognome``): the user real last name; defaults to the value of ``username``.

- ``ip`` (string): the IP address or subnet from which incoming connections for this user are accepted, see :ref:`configuringacontest_login`.

- ``hidden`` (boolean; also accepted: ``fake``): when set to true set the ``hidden`` flag in the user, see :ref:`configuringacontest_login`; defaults to false (the case-sensitive *string* ``True`` is also accepted).


.. _externalcontestformats_task-directory:

Task directory
--------------

The content of the task directory is used both to retrieve the task data and to infer the type of the task.

These are the required files.

- :file:`task.yaml`: this file contains the name of the task and describes some of its properties; its content is detailed :ref:`below <externalcontestformats_task-description>`; in order to retain backward compatibility, this file can also be provided in the file :file:`{task_name.yaml}` in the root directory of the *contest*.

- :file:`statement/statement.pdf` (also accepted: :file:`testo/testo.pdf`): the main statement of the problem. It is not yet possible to import several statement associated to different languages: this (only) statement will be imported according to the language specified under the key ``primary_language``.

- :file:`input/input{%d}.txt` and :file:`output/output{%d}.txt` for all integers :samp:`{%d}` between 0 (included) and ``n_input`` (excluded): these are of course the input and reference output files.

The following are optional files, that must be present for certain task types or score types.

- :file:`gen/GEN`: in the Italian environment, this file describes the parameters for the input generator: each line not composed entirely by white spaces or comments (comments start with ``#`` and end with the end of the line) represents an input file. Here, it is used, in case it contains specially formatted comments, to signal that the score type is :ref:`scoretypes_groupmin`. If a line contains only a comment of the form :samp:`# ST: {score}` then it marks the beginning of a new group assigning at most :samp:`{score}` points, containing all subsequent testcases until the next special comment. If the file does not exists, or does not contain any special comments, the task is given the :ref:`scoretypes_sum` score type.

- :file:`sol/grader.{%l}` (where :samp:`{%l}` here and after means a supported language extension): for tasks of type :ref:`tasktypes_batch`, it is the piece of code that gets compiled together with the submitted solution, and usually takes care of reading the input and writing the output. If one grader is present, the graders for all supported languages must be provided.

- :file:`sol/*.h` and :file:`sol/*lib.pas`: if a grader is present, all other files in the :file:`sol` directory that end with ``.h`` or ``lib.pas`` are treated as auxiliary files needed by the compilation of the grader with the submitted solution.

- :file:`check/checker` (also accepted: :file:`cor/correttore`): for tasks of types :ref:`tasktypes_batch` or :ref:`tasktypes_outputonly`, if this file is present, it must be the executable that examines the input and both the correct and the contestant's output files and assigns the outcome. It must be a statically linked executable (for example, if compiled from a C or C++ source, the :samp:`-static` option must be used) because otherwise the sandbox will prevent it from accessing its dependencies. It is going to be executed on the workers, so it must be compiled for their architecture. If instead the file is not present, a simple diff is used to compare the correct and the contestant's output files.

- :file:`check/manager`: (also accepted: :file:`cor/manager`) for tasks of type :ref:`tasktypes_communication`, this executable is the program that reads the input and communicates with the user solution.

- :file:`sol/stub.%l`: for tasks of type :ref:`tasktypes_communication`, this is the piece of code that is compiled together with the user submitted code, and is usually used to manage the communication with :file:`manager`. Again, all supported languages must be present.

- :file:`att/*`: each file in this folder is added as an attachment to the task, named as the file's filename.


.. _externalcontestformats_task-description:

Task description
----------------

The task YAML files require the following keys.

- ``name`` (string; also accepted: ``nome_breve``): the name used to reference internally to this task; it is exposed in the URLs.

- ``title`` (string; also accepted: ``nome``): the long name (title) used in the web interface.

- ``n_input`` (integer): number of test cases to be evaluated for this task; the actual test cases are retrieved from the :ref:`task directory <externalcontestformats_task-directory>`.

- ``score_mode``: the score mode for the task, as in :ref:`configuringacontest_score`; it can be ``max_tokened_last``, ``max``, or ``max_subtask``.

- ``token_mode``: the token mode for the task, as in :ref:`configuringacontest_tokens`; it can be ``disabled``, ``infinite`` or ``finite``; if this is not specified, the loader will try to infer it from the remaining token parameters (in order to retain compatibility with the past), but you are not advised to relay on this behavior.

The following are optional keys.

- ``time_limit`` (float; also accepted: ``timeout``): the timeout limit for this task in seconds; defaults to no limitations.

- ``memory_limit`` (integer; also accepted: ``memlimit``): the memory limit for this task in mibibytes; defaults to no limitations.

- ``public_testcases`` (string; also accepted: ``risultati``): a comma-separated list of test cases (identified by their numbers, starting from 0) that are marked as public, hence their results are available to contestants even without using tokens. If the given string is equal to ``all``, then the importer will mark all testcases as public.

- ``token_*``: additional token parameters for the task, see :ref:`configuringacontest_tokens` (the names of the parameters are the same as the internal names described there).

- ``max_*_number`` and ``min_*_interval`` (integers): limitations for the task, see :ref:`configuringacontest_limitations` (the names of the parameters are the same as the internal names described there); by default they're all unset.

- ``output_only`` (boolean): if set to True, the task is created with the :ref:`tasktypes_outputonly` type; defaults to False.

The following are optional keys that must be present for some task type or score type.

- ``total_value`` (float): for tasks using the :ref:`scoretypes_sum` score type, this is the maximum score for the task and defaults to 100.0; for other score types, the maximum score is computed from the :ref:`task directory <externalcontestformats_task-directory>`.

- ``infile`` and ``outfile`` (strings): for :ref:`tasktypes_batch` tasks, these are the file names for the input and output files; default to :file:`input.txt` and :file:`output.txt`; if left empty, :file:`stdin` and :file:`stdout` are used.

- ``primary_language`` (string): the statement will be imported with this language code; defaults to ``it`` (Italian), in order to ensure backward compatibility.


Polygon format
==============

`Polygon <https://polygon.codeforces.com>`__ is a popular platform for the creation of tasks, and a task format, used among others by Codeforces.

Since Polygon doesn't support CMS directly, some task parameters cannot be set using the standard Polygon configuration. The importer reads from an optional file :file:`cms_conf.py` additional configuration specifics to CMS. Additionally, user can add file named contestants.txt to allow importing some set of users.

By default, all tasks are batch files, with custom checker and score type is Sum. Loaders assumes that checker is check.cpp and written with usage of testlib.h. It provides customized version of testlib.h which allows using Polygon checkers with CMS. Checkers will be compiled during importing the contest. This is important in case the architecture where the loading happens is different from the architecture of the workers.

Polygon (by now) doesn't allow custom contest-wide files, so general contest options should be hard-coded in the loader.
