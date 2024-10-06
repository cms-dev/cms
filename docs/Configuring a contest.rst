Configuring a contest
*********************

In the following text "user" and "contestant" are used interchangeably. A "participation" is an instance of a user participating in a specific contest. See :doc:`here <Data model>` for more details.

Configuration parameters will be referred to using their internal name, but it should always be easy to infer what fields control them in the AWS interface by using their label.


.. _configuringacontest_limitations:

Limitations
===========

Contest administrators can limit the ability of users to submit submissions and user_tests, by setting the following parameters:

- ``max_submission_number`` / ``max_user_test_number``

  These set, respectively, the maximum number of submissions or user tests that will be accepted for a certain user. Any attempt to send in additional submissions or user tests after that limit has been reached will fail.

- ``min_submission_interval`` / ``min_user_test_interval``

  These set, respectively, the minimum amount of time, in seconds, the user is required to wait after a submission or user test has been submitted before they are allowed to send in new ones. Any attempt to submit a submission or user test before this timeout has expired will fail.

The limits can be set both for individual tasks and for the whole contest. A submission or user test is accepted if it verifies the conditions on both the task *and* the contest. This means that a submission or user test will be accepted if the number of submissions or user tests received so far for that task is strictly less that the task's maximum number *and* the number of submissions or user tests received so far for the whole contest (i.e. in all tasks) is strictly less than the contest's maximum number. The same holds for the minimum interval too: a submission or user test will be accepted if the time passed since the last submission or user test for that task is greater than the task's minimum interval *and* the time passed since the last submission or user test received for the whole contest (i.e. in any of the tasks) is greater than the contest's minimum interval.

Each of these fields can be left unset to prevent the corresponding limitation from being enforced.


Feedback to contestants
=======================

Each testcase can be marked as public or private. After sending a submission, a contestant can always see its results on the public testcases: a brief passed / partial / not passed status for each testcase, and the partial score that is computable from the public testcases only. Note that input and output data are always hidden.

Tokens were introduced to provide contestants with limited access to the detailed results of their submissions on the private testcases as well. If a contestant uses a token on a submission, then they will be able to see its result on all testcases, and the global score.


.. _configuringacontest_tokens:

Tokens rules
------------

Each contestant have a set of available tokens at their disposal; when they use a token it is taken from this set, and cannot be use again. These sets are managed by CMS according to rules defined by the contest administrators, as explained later in this section.

There are two types of tokens: contest-tokens and task-tokens. When a contestant uses a token to unlock a submission, they are really using one token of each type, and therefore needs to have both available. As the names suggest, contest-tokens are bound to the contest while task-tokens are bound to a specific task. That means that there is just one set of contest-tokens but there can be many sets of task-tokens (precisely one for every task). These sets are controlled independently by rules defined either on the contest or on the task.

A token set can be disabled (i.e. there will never be tokens available for use), infinite (i.e. there will always be tokens available for use) or finite. This setting is controlled by the ``token_mode`` parameter.

If the token set is finite it can be effectively represented by a non-negative integer counter: its cardinality. When the contest starts (or when the user starts its per-user time-frame, see :ref:`configuringacontest_usaco-like-contests`) the set will be filled with ``token_gen_initial`` tokens (i.e. the counter is set to ``token_gen_initial``). If the set is not empty (i.e. the counter is not zero) the user can use a token. After that, the token is discarded (i.e. the counter is decremented by one). New tokens can be generated during the contest: ``token_gen_number`` new tokens will be given to the user after every ``token_gen_interval`` minutes from the start (note that ``token_gen_number`` can be zero, thus disabling token generation). If ``token_gen_max`` is set, the set cannot contain more than ``token_gen_max`` tokens (i.e. the counter is capped at that value). Generation will continue but will be ineffective until the contestant uses a token. Unset ``token_gen_max`` to disable this limit.

The use of tokens can be limited with ``token_max_number`` and ``token_min_interval``: users cannot use more that ``token_max_number`` tokens in total (this parameter can be unset), and they have to wait at least ``token_min_interval`` seconds after they used a token before they can use another one (this parameter can be zero). These have no effect in case of infinite tokens.

Having a finite set of both contest- and task-tokens can be very confusing, for the contestants as well as for the contest administrators. Therefore it is common to limit just one type of tokens, setting the other type to be infinite, in order to make the general token availability depend only on the availability of that type (e.g. if you just want to enforce a contest-wide limit on tokens set the contest-token set to be finite and set all task-token sets to be infinite). CWS is aware of this "implementation details" and when one type is infinite it just shows information about the other type, calling it simply "token" (i.e. removing the "contest-" or "task-" prefix).

Note that "token sets" are "intangible": they're just a counter shown to the user, computed dynamically every time. Yet, once a token is used, a Token object will be created, stored in the database and associated with the submission it was used on.

Changing token rules during a contest may lead to inconsistencies. Do so at your own risk!


.. _configuringacontest_score:

Computation of the score
========================


The score of a contestant on the contest is always the sum of the score over all tasks. The score on a task depends on the score on each submission via the "score mode" (a setting that can be changed in AdminWebServer for each task).


Score modes
-----------

The score mode determines how to compute the score of a contestant in a task from their submissions on that task. There are three score modes, corresponding to the rules of IOI in different years.

"Use best among tokened and last submissions" is the score mode that follows the rules of IOI 2010-2012. It is intended to be used with tasks having some private testcases, and that allow the use of tokens. The score on the task is the best score among "released" submissions. A submission is said to be released if the contestant used a token on it, or if it is the latest one submitted. The idea is that the contestants have to "choose" which submissions they want to use for grading.

"Use best among all submissions" is the score mode that follows the rules of IOI 2013-2016. The score on the task is simply the best score among all submissions.

"Use the sum over each subtask of the best result for that subtask across all submissions" is the score mode that follows the rules of IOI since 2017. It is intended to be used with tasks that have a group score type, like "GroupMin" (note that "group" and "subtask" are synonyms). The score on the task is the sum of the best score for each subtask, over all submissions. The difference with the previous score mode is that here a contestant can achieve the maximum score on the task even when no submission gets the maximum score (for example if each subtask is solved by exactly one submission).

.. note::

    OutputOnly tasks have a similar behavior to the score mode for IOI 2017-; namely, if a contestant doesn't submit the output of a testcase, CMS automatically fills in the latest submitted output for that testcase, if present. There is a difference, though: the IOI 2017- score mode would be as if CMS filled the missing output with the one obtaining the highest score, instead of the latest one. Therefore, it might still make sense to use this score mode, even with OutputOnly tasks.


Score rounding
--------------

Based on the ScoreTypes in use and on how they are configured, some submissions may be given a floating-point score. Contest administrators will probably want to show only a small number of these decimal places in the scoreboard. This can be achieved with the ``score_precision`` fields on the contest and tasks.

The score of a user on a certain task is the maximum among the scores of the "tokened" submissions for that task, and the last one. This score is rounded to a number of decimal places equal to the ``score_precision`` field of the task. The score of a user on the whole contest is the sum of the *rounded* scores on each task. This score itself is then rounded to a number of decimal places equal to the ``score_precision`` field of the contest.

Note that some "internal" scores used by ScoreTypes (for example the subtask score) are not rounded using this procedure. At the moment the subtask scores are always rounded at two decimal places and there's no way to configure that (note that the score of the submission is the sum of the *unrounded* scores of the subtasks).

The unrounded score is stored in the database (and it's rounded only at presentation level) so you can change the ``score_precision`` at any time without having to rescore any submissions. Yet, you have to make sure that these values are also updated on the RankingWebServers. To do that you can either restart ScoringService or update the data manually (see :doc:`RankingWebServer` for further information).


Languages
=========

Statements
----------

When there are many statements for a certain task (which are often different translations of the same statement) contest administrators may want to highlight some of them to the users. These may include, for example, the "official" version of the statement (the one that is considered the reference version in case of questions or appeals) or the translations for the languages understood by that particular user. To do that the ``primary_statements`` field of the tasks and the ``preferred_languages`` field of the users has to be used.

The ``primary_statements`` field for the tasks is a list of strings: it specifies the language codes of the statements that will be highlighted to all users. A valid example is ``en_US, it``. The ``preferred_languages`` field for the users is a list of strings: it specifies the language codes of the statements to highlight. For example ``de, de_CH``.

Note that users will always be able to access all statements, regardless of the ones that are highlighted. Note also that language codes in the form ``xx`` or ``xx_YY`` (where ``xx`` is an `ISO 639-1 code <http://www.iso.org/iso/language_codes.htm>`_ and ``YY`` is an `ISO 3166-1 code <http://www.iso.org/iso/country_codes.htm>`_) will be recognized and presented accordingly. For example ``en_AU`` will be shown as "English (Australia)".

Interface
---------

The interface for contestants can be localized (see :ref:`localization` for how to add new languages), and by default all languages will be available to all contestants. To limit the languages available to the contestants, the field "Allowed localizations" in the contest configuration can be set to the list of allowed language codes. The first of this language codes determines the fallback language in case the preferred language is not available.


Timezone
========

CMS stores all times as UTC timestamps and converts them to an appropriate timezone when displaying them. This timezone can be specified on a per-user and per-contest basis with the ``timezone`` field. It needs to contain a string recognized by `pytz <http://pytz.sourceforge.net/>`_, for example ``Europe/Rome``.

When CWS needs to show a timestamp to the user it first tries to show it according to the user's timezone. If the string defining the timezone is unrecognized (for example it is the empty string), CWS will fallback to the contest's timezone. If it is again unable to interpret that string it will use the local time of the server.


.. _configuringacontest_login:

User login
==========

Users can log into CWS manually, using their credentials (username and a password), or they can get logged in automatically by CMS based on the IP address their requests are coming from.

Logging in with IP-based autologin
----------------------------------

If the "IP-based autologin" option in the contest configuration is set, CWS tries to find a user that matches the IP address the request is coming from. If it finds exactly one user, the requester is automatically logged in as that user. If zero or more than one user match, CWS does not let the user in (and the incident is logged to allow troubleshooting).

In general, each user can have multiple ranges of IP addresses associated to it. These are defined as a list of subnets in CIDR format (e.g., `192.168.1.0/24`). Only the subnets whose mask is maximal (i.e., `/32` for IPv4 or `/128` for IPv6) are considered for autologin purposes (subnets with non-maximal mask are still useful for IP-based restrictions, see below). The autologin will kick in if *any* of the subnets matches the IP of the request.

.. warning::

  If a reverse-proxy (like nginx) is in use then it is necessary to set ``num_proxies_used`` (in :file:`cms.conf`) to ``1`` and configure the proxy in order to properly pass the ``X-Forwarded-For``-style headers (see :ref:`running-cms_recommended-setup`). That configuration option can be set to a higher number if there are more proxies between the origin and the server.

Logging in with credentials
---------------------------

If the autologin is not enabled, users can log in with username and password, which have to be specified in the user configuration (in cleartext, for the moment). The password can also be overridden for a specific contest in the participation configuration. These credentials need to be inserted by the admins (i.e. there's no way to sign up, of log in as a "guest", etc.).

A successfully logged in user needs to reauthenticate after ``cookie_duration`` seconds (specified in the :file:`cms.conf` file) from when they last visited a page.

Even without autologin, it is possible to restrict the IP address or subnet that the user is using for accessing CWS, using the "IP-based login restriction" option in the contest configuration (in which case, admins need to set ``num_proxies_used`` as before). If this is set, then the login will fail if the IP address that attempted it does not match at least one of the addresses or subnets specified in the participation settings. If the participation IP address is not set, then no restriction applies.

Failure to login
----------------

The following are some common reasons for login failures, all of them coming with some useful log message from CWS.

- IP address mismatch (with IP-based autologin): if the IP address doesn't match any subnet of any participation or if it matches some subnets of more than one participation, then the login fails. Note that if the user is using the IP address of a different user, CWS will happily log them in without noticing anything.

- IP address mismatch (using IP-based login restrictions): the login fails if the request comes from an IP address that doesn't match any of the participation's IP subnets (non-maximal masks are taken into consideration here).

- Blocked hidden participations: users whose participation is hidden cannot log in if "Block hidden participations" is set in the contest configuration.


.. _configuringacontest_usaco-like-contests:

USACO-like contests
===================

One trait of the `USACO <http://usaco.org/>`_ contests is that the contests themselves are many days long but each user is only able to compete for a few hours after their first login (after that they are not able to send any more submissions). This can be done in CMS too, using the ``per_user_time`` field of contests. If it is unset the contest will behave "normally", that is all users will be able to submit solutions from the contest's beginning until the contest's end. If, instead, ``per_user_time`` is set to a positive integer value, then a user will only have a limited amount of time. In particular, after they log in, they will be presented with an interface similar to the pre-contest one, with one additional "start" button. Clicking on this button starts the time frame in which the user can compete (i.e. read statements, download attachments, submit solutions, use tokens, send user tests, etc.). This time frame ends after ``per_user_time`` seconds or when the contest ``stop`` time is reached, whichever comes first. After that the interface will be identical to the post-contest one: the user won't be able to do anything. See :gh_issue:`61`.

The time at which the user clicks the "start" button is recorded in the ``starting_time`` field of the user. You can change that to shift the user's time frame (but we suggest to use ``extra_time`` for that, explained in :ref:`configuringacontest_extra-time`) or unset it to make the user able to start its time frame again. Do so at your own risk!


.. _configuringacontest_extra-time:

Extra time and delay time
=========================

Contest administrators may want to give some users a short additional amount of time in which they can compete to compensate for an incident (e.g. a hardware failure) that made them unable to compete for a while during the "intended" time frame. That's what the ``extra_time`` field of the users is for. The time frame in which the user is allowed to compete is expanded by its ``extra_time``, even if this would lead the user to be able to submit after the end of the contest.

During extra time the user will continue to receive newly generated tokens. If you don't want them to have more tokens that other contestants, set the ``token_max_number`` parameter described above to the number of tokens you expect a user to have at their disposal during the whole contest (if it doesn't already have a value less than or equal to this).

Contest administrators can also alter the competition time of a contestant setting ``delay_time``, which has the effect of translating the competition time window for that contestant of the specified numer of seconds in the future. Thus, while setting ``extra_time`` *adds* some times at the end of the contest, setting ``delay_time`` *moves* the whole time window. As for ``extra_time``, setting ``delay_time`` may extend the contestant time window beyond the end of the contest itself.

Both options have to be set to a non negative number. They can be used together, producing both their effects. Please read :doc:`Detailed timing configuration` for a more in-depth discussion of their exact effect.

Note also that submissions sent during the extra time will continue to be considered when computing the score, even if the ``extra_time`` field of the user is later reset to zero (for example in case the user loses the appeal): you need to completely delete them from the database or make them unofficial, and make sure the score in all rankings reflects the new state.


Analysis mode
=============

After the contest it is often customary to allow contestants to see the results of all their submissions and use the grading system to try different solutions. CMS offers an analysis mode to do this. Solutions submitted during the analysis are evaluated as usual, but are marked as not official, and thus do not contribute to the rankings. Users will also be prevented from using tokens.

The admins can enable the analysis mode in the contest configuration page in AWS; they also must set start end stop time (which must be after the contest end).

By awarding extra time or adding delay to a contestant, it is possible to extend the contest time for a user over the start of the analysis. In this case, the start of the analysis will be postponed for this user. If the contest rules contemplate extra time or delay, we suggest to avoid starting the analysis right after the end of the contest.


.. _configuringacontest_programming-languages:

Programming languages
=====================

CMS allows to restrict the set of programming languages available to contestants in a certain contest; the configuration is in the contest page in AWS.

If necessary, it is possible to apply language restrictions to individual tasks. This might be useful for tasks that utilize custom graders. Task level restrictions can be enabled in the task page in AWS.

CMS offers out of the box the following combination of languages: C, C++, Pascal, Java (using a JDK), Python 2 and 3, PHP, Haskell, Rust, C#.

C, C++ and Pascal are the default languages, and have been tested thoroughly in many contests.

PHP and Python have only been tested with Batch task types, and have not thoroughly analyzed for potential security and usability issues. Being run under the sandbox, they should be reasonably safe, but, for example, the libraries available to contestants might be hard to control.

Java works with Batch and Communication task types. Under usual conditions (default submission format) contestants must name their class as the short name of the task.

.. warning::

   Java uses multithreading even for simple programs. Therefore, if this language is allowed in the contest, multithreading and multiprocessing will be allowed in the sandbox for *all* evaluations (even with other languages).

   If a solution uses multithreading or multiprocessing, the time limit is checked against the sum of the user times of all threads and processes.


Language details
----------------

* C and C++ are supported through the GNU Compiler Collection. Submissions are optimized with ``-O2``. Multiple C and C++ language revisions are supported.

* Java uses the system version of the Java compiler and JVM.

* Pascal support is provided by ``fpc``, and submissions are optimized with ``-O2``.

* Python submissions are executed using the system Python interpreter (you need to have ``/usr/bin/python2`` or ``/usr/bin/python3``, respectively).

* PHP submissions are interpreted by ``/usr/bin/php``.

* Haskell support is provided by ``ghc``, and submissions are optimized with ``-O2``.

* Rust support is provided by ``rustc``, and submissions are optimized with ``-O``.

* C# uses the system version of the Mono compiler ``mcs`` and the runtime ``mono``. Submissions are optimized with ``-optimize+``.


Custom languages
----------------

Additional languages can be defined if necessary. This works in the same way :ref:`as with task types <tasktypes_custom>`: the classes need to extend :py:class:`cms.grading.language.Language` and the entry point group is called `cms.grading.languages`.
