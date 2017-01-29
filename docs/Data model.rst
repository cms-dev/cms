Data model
**********

CMS is used in many different settings: single onsite contests, with remote participations, short training camps, always-on training websites, university assignments... Its data model needs to support all of these, and therefore might be a bit surprising if you only think of the first use case.

In the following, we explain the main objects in CMS's data model.

Users
=====

Users are the accounts for contestants; a user represents a person, which can participate to zero, one or many contests.

Participations
==============

Participations contain the interactions of users and a contest. In particular all of the following are associated to a participation: the submissions sent, their results, questions asked, communications from contest admins.

Contests
========

A contest is a collection of tasks to be solved, and participations of users trying to solve them.

It is :doc:`very configurable <Configuring a contest>` with respect of timing (start and end times, how much time each contestant has), logistic (how contestants login), permissions (what contestants can or cannot do, and how often), scoring, and more.

They are mainly thought as limited in duration to a few hours, but this is not a requirement: contests can be very long running.

Tasks and datasets
==================

A task is one of the problems to solve within a contest. A task cannot be associated to more than one contest, but you can have tasks temporarily not associated to any.

Tasks store additional configurations that might override or alter the configurations at the contest level.

A task can have one or more datasets. The complete task data is shared between these two objects: task contains more contest-visible data, such as name, statement, constraints on the submissions; datasets instead contain instruction on how to compile, evaluate and score the submissions. The information in the task object should not change, as they are visible to the contestants and influence their interaction during the contest, whereas those in the dataset object could change without the contestants noticing.

The dataset used to display information to contestants is said to be active. For example, a second, inactive dataset can be created to fix an incorrect testcase; evaluation could progress in parallel until the inactive dataset is deemed correct, and eventually the switch to make it active could happen at once.

See the section on :doc:`task versioning <Task versioning>` for more details on how to use datasets.

Submissions, results and tokens
===============================

Submissions are associated to a participation and a task. In addition to these, the judging of a submission depends on the dataset used in the compilation, evaluation and scoring phases. Therefore, a submission result is associated also to a specific dataset.

Similarly to submissions and submission results, we have user tests and user tests results. User tests are a way to allow contestants to run their source on the sandboxed environment, for example to diagnose errors or test timings.

Tokens are requests from a contestant to see additional details about the result of a submission they are associated to the submission (not to the submission result, so if the admins change dataset, the contestant can still see the detailed results).

Announcements, questions and messages
=====================================

Announcements are contest-level communications sent by the admins and visible to all contestants.

Questions and messages instead are communication between a specific contestant and the admins. The difference is that questions are initiated by the contestants and expect an answer from the admins, whereas messages are initiated by the admins and contestants cannot reply.

Admins
======

CMS stores administrative accounts to use AdminWebServer. Accounts can be useful to offer different permissions to different sets of people. There are three levels of permissions: read-only, full permissions, and communication only (that is, these admins can only answer questions, send announcements and messages).
