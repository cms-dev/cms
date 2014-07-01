Configuring a contest
*********************

In the following text "user" and "contestant" are used interchangeably.

Configuration parameters will be referred to using their internal name, but it should always be easy to infer what fields control them in the AWS interface by using their label.


.. _configuringacontest_limitations:

Limitations
===========

Contest administrators can limit the ability of users to submit submissions and user_tests, by setting the following parameters:

- ``max_submission_number`` / ``max_user_test_number``

  These set, respectively, the maximum number of submissions or user tests that will be accepted for a certain user. Any attempt to send in additional submissions or user tests after that limit has been reached will fail.

- ``min_submission_interval`` / ``min_user_test_interval``

  These set, respectively, the minimum amount of time the user is required to wait after a submission or user test has been submitted before they are allowed to send in new ones. Any attempt to submit a submission or user test before this timeout has expired will fail.

The limits can be set both for individual tasks and for the whole contest. A submission or user test is accepted if it verifies the conditions on both the task *and* the contest. This means that a submission or user test will be accepted if the number of submissions or user tests received so far for that task is strictly less that the task's maximum number *and* the number of submissions or user tests received so far for the whole contest (i.e. in all tasks) is strictly less than the contest's maximum number. The same holds for the minimum interval too: a submission or user test will be accepted if the time passed since the last submission or user test for that task is greater than the task's minimum interval *and* the time passed since the last submission or user test received for the whole contest (i.e. in any of the tasks) is greater than the contest's minimum interval.

Each of these fields can be left unset to prevent the corresponding limitation from being enforced.


.. _configuringacontest_tokens:

Feedback and tokens
===================

Each testcase can be marked as public or private. During the contest, contestants can see the result of their submissions on the public testcases (the content of the input and output data themselves remain hidden, though). Tokens are a concept introduced to provide contestants with limited access to the detailed results of their submissions on the private testcases as well.

For every submission sent in for evaluation, a contestant is always able to see if it succesfully compiled. They are also able to see its scores on the public testcases of the task, if any. All information about the other so-called private testcases is kept hidden. Yet, a contestant can choose to use one of its tokens to "unlock" a certain submission of their choice. After they do so, detailed results are available for all testcases, as if they were all public. A token, once used, is consumed and lost forever. Contestants have a set of available tokens at their disposal, where the ones they use are picked from. These sets are managed by CMS according to rules defined by the contest administrators, as explained later in this section. For all official :doc:`score types <Score types>`, the public score is the score on public testcases, whereas the detailed score is the score on all testcases. This is not necessarily true for custom score types, as they can implement arbitrary logics to compute those values.

Tokens also affect the score computation. That is, all "tokened" submissions will be considered, together with the last submitted one, when computing the score for a task. See also :ref:`configuringacontest_score-rounding`.

There are two types of tokens: contest-tokens and task-tokens. When a contestant uses a token to unlock a submission, they are really using one token of each type, and therefore needs to have both available. As the names suggest, contest-tokens are bound to the contest while task-tokens are bound to a specific task. That means that there is just one set of contest-tokens but there can be many sets of task-tokens (precisely one for every task). These sets are controlled independently by rules defined either on the contest or on the task.

A token set can be disabled (i.e. there will never be tokens available for use), infinite (i.e. there will always be tokens available for use) or finite. This setting is controlled by the ``token_mode`` parameter.

If the token set is finite it can be effectively represented by a non-negative integer counter: its cardinality. When the contest starts (or when the user starts its per-user time-frame, see :ref:`configuringacontest_usaco-like-contests`) the set will be filled with ``token_gen_initial`` tokens (i.e. the counter is set to ``token_gen_initial``). If the set is not empty (i.e. the counter is not zero) the user can use a token. After that, the token is discarded (i.e. the counter is decremented by one). New tokens can be generated during the contest: ``token_gen_number`` new tokens will be given to the user after every ``token_gen_interval`` minutes from the start (note that ``token_gen_number`` can be zero, thus disabling token generation). If ``token_gen_max`` is set, the set cannot contain more than ``token_gen_max`` tokens (i.e. the counter is capped at that value). Generation will continue but will be ineffective until the contestant uses a token. Unset ``token_gen_max`` to disable this limit.

The use of tokens can be limited with ``token_max_number`` and ``token_min_interval``: users cannot use more that ``token_max_number`` tokens in total (this parameter can be unset), and they have to wait at least ``token_min_interval`` seconds after they used a token before they can use another one (this parameter can be zero). These have no effect in case of infinite tokens.

Having a finite set of both contest- and task-tokens can be very confusing, for the contestants as well as for the contest administrators. Therefore it is common to limit just one type of tokens, setting the other type to be infinite, in order to make the general token availability depend only on the availability of that type (e.g. if you just want to enforce a contest-wide limit on tokens set the contest-token set to be finite and set all task-token sets to be infinite). CWS is aware of this "implementation details" and when one type is infinite it just shows information about the other type, calling it simply "token" (i.e. removing the "contest-" or "task-" prefix).

Note that "token sets" are "intangible": they're just a counter shown to the user, computed dynamically every time. Yet, once a token is used, a Token object will be created, stored in the database and associated with the submission it was used on.

.. note::
   The full-feedback mode introduced in IOI 2013 has not been ported upstream yet (see :gh_issue:`246`). Note that although disabling tokens and making all testcases public would give full feedback, the final scores would be computed differently: the one of the latest submission would be used instead of the maximum among all submissions. To achieve the correct scoring behavior, get in touch with the developers or check `the ML archives <http://www.freelists.org/post/contestms/applying-tokens-automatically,1>`_.

Changing token rules during a contest may lead to inconsistencies. Do so at your own risk!


.. _configuringacontest_score-rounding:

Score rounding
==============

Based on the ScoreTypes in use and on how they are configured, some submissions may be given a floating-point score. Contest administrators will probably want to show only a small number of these decimal places in the scoreboard. This can be achieved with the ``score_precision`` fields on the contest and tasks.

The score of a user on a certain task is the maximum among the scores of the "tokened" submissions for that task, and the last one. This score is rounded to a number of decimal places equal to the ``score_precision`` field of the task. The score of a user on the whole contest is the sum of the *rounded* scores on each task. This score itself is then rounded to a number of decimal places equal to the ``score_precision`` field of the contest.

Note that some "internal" scores used by ScoreTypes (for example the subtask score) are not rounded using this procedure. At the moment the subtask scores are always rounded at two decimal places and there's no way to configure that (note that the score of the submission is the sum of the *unrounded* scores of the subtasks). That will be changed soon. See :gh_issue:`33`.

The unrounded score is stored in the database (and it's rounded only at presentation level) so you can change the ``score_precision`` at any time without having to rescore any submissions. Yet, you have to make sure that these values are also updated on the RankingWebServers. To do that you can either restart ScoringService or update the data manually (see :doc:`RankingWebServer` for further information).


Primary statements
==================

When there are many statements for a certain task (which are often different translations of the same statement) contest administrators may want to highlight some of them to the users. These may include, for example, the "official" version of the statement (the one that is considered the reference version in case of questions or appeals) or the translations for the languages understood by that particular user. To do that the ``primary_statements`` field of the tasks and the users has to be used.

The ``primary_statements`` field for the tasks is a JSON-encoded list of strings: it specifies the language codes of the statements that will be highlighted to all users. A valid example is ``["en_US", "it"]``. The ``primary_statements`` field for the users is a JSON-encoded object of lists of strings. Each item in this object specifies a task by its name and provides a list of language codes of the statements to highlight. For example ``{"task1": ["de"], "task2": ["de_CH"]}``.

Note that users will always be able to access all statements, regardless of the ones that are highlighted. Note also that language codes in the form ``xx`` or ``xx_YY`` (where ``xx`` is an `ISO 639-1 code <http://www.iso.org/iso/language_codes.htm>`_ and ``YY`` is an `ISO 3166-1 code <http://www.iso.org/iso/country_codes.htm>`_) will be recognized and presented accordingly. For example ``en_AU`` will be shown as "English (Australia)".


Timezone
========

CMS stores all times as UTC timestamps and converts them to an appropriate timezone when displaying them. This timezone can be specified on a per-user and per-contest basis with the ``timezone`` field. It needs to contain a string in the format ``Europe/Rome`` (actually, any string recognized by `pytz <http://pytz.sourceforge.net/>`_ will work).

When CWS needs to show a timestamp to the user it first tries to show it according to the user's timezone. If the string defining the timezone is unrecognized (for example it is the empty string), CWS will fallback to the contest's timezone. If it is again unable to interpret that string it will use the local time of the server.


.. _configuringacontest_login:

User login
==========

Users log into CWS using a username and a password. These have to be specified, respectively, in the ``username`` and ``password`` fields (in cleartext!). These credentials need to be inserted (i.e. there's no way to have an automatic login, a "guest" session, etc.) and, if they match, the login (usually) succeeds. The user needs to login again if they do not navigate the site for ``cookie_duration`` seconds (specified in the :file:`cms.conf` file).

In fact, there are other reasons that can cause the login to fail. If the ``ip_lock`` option (in :file:`cms.conf`) is set to ``true`` then the login will fail if the IP address that attempted it doesn't match the address or subnet in the ``ip`` field of the specified user. If ``ip`` is not set then this check is skipped, even if ``ip_lock`` is ``true``. Note that if a reverse-proxy (like nginx) is in use then it is necessary to set ``is_proxy_used`` (in :file:`cms.conf`) to ``true`` and configure the proxy in order to properly pass the ``X-Forwarded-For``-style headers (see :ref:`running-cms_recommended-setup`).

The login can also fail if ``block_hidden_users`` (in :file:`cms.conf`) is ``true`` and the user trying to login as has the ``hidden`` field set.


.. _configuringacontest_usaco-like-contests:

USACO-like contests
===================

One trait of the `USACO <http://usaco.org/>`_ contests is that the contests themselves are many days long but each user is only able to compete for a few hours after their first login (after that they are not able to send any more submissions). This can be done in CMS too, using the ``per_user_time`` field of contests. If it is unset the contest will behave "normally", that is all users will be able to submit solutions from the contest's beginning until the contest's end. If, instead, ``per_user_time`` is set to a positive integer value, then a user will only have a limited amount of time. In particular, after they log in, they will be presented with an interface similar to the pre-contest one, with one additional "start" button. Clicking on this button starts the time frame in which the user can compete (i.e. read statements, download attachments, submit solutions, use tokens, send user tests, etc.). This time frame ends after ``per_user_time`` seconds or when the contest ``stop`` time is reached, whichever comes first. After that the interface will be identical to the post-contest one: the user won't be able to do anything. See :gh_issue:`61`.

The time at which the user clicks the "start" button is recorded in the ``starting_time`` field of the user. You can change that to shift the user's time frame (but we suggest to use ``extra_time`` for that, explained in :ref:`configuringacontest_extra-time`) or unset it to make the user able to start its time frame again. Do so at your own risk!


.. _configuringacontest_extra-time:

Extra time and delay time
=========================

Contest administrators may want to give some users a short additional amount of time in which they can compete to compensate for an incident (e.g. a hardware failure) that made them unable to compete for a while during the "intended" time frame. That's what the ``extra_time`` field of the users is for. The time frame in which the user is allowed to compete is expanded by its ``extra_time``, even if this would lead the user to be able to submit after the end of the contest.

During extra time the user will continue to receive newly generated tokens. If you don't want them to have more tokens that other contestants, set the ``token_max_number`` parameter described above to the number of tokens you expect a user to have at their disposal during the whole contest (if it doesn't already have a value less than or equal to this). See also :gh_issue:`29`.

Contest administrators can also alter the competition time of a contestant setting ``delay_time``, which has the effect of translating the competition time window for that contestant of the specified numer of seconds in the future. Thus, while setting ``extra_time`` *adds* some times at the end of the contest, setting ``delay_time`` *moves* the whole time window. As for ``extra_time``, setting ``delay_time`` may extend the contestant time window beyond the end of the contest itself.

Both options have to be set to a non negative number. They can be used together, producing both their effects. Please read :doc:`Detailed timing configuration` for a more in-depth discussion of their exact effect.

Note also that submissions sent during the extra time will continue to be considered when computing the score, even if the ``extra_time`` field of the user is later reset to zero (for example in case the user loses the appeal): you need to completely delete them from the database.


.. _configuringacontest_programming-languages:

Programming languages
=====================

It is possible to limit the set of programming languages available to contestants by setting the appropriate configuration in the contest page in AWS. By default, the historical set of IOI programming languages is allowed (C, C++, and Pascal). These languages have been used in several contests and with many different types of tasks, and are thus fully tested and safe.

Contestants may be also allowed to use Java, Python and PHP, but these languages have only been tested for Batch tasks, and have not been thoroughly analyzed for potential security and usability issues. Being run under the sandbox, they should be reasonably safe, but, for example, the libraries available to contestants might be hard to control.

Java programs are first compiled using ``gcj``, and then run as normal executables. For Python, the contestants' programs are interpreted using Python 2 (you need to have ``/usr/bin/python2``). To use Python 3, you need to modify the CMS code following the instructions in :file:`cms/grading/__init__.py`. For PHP, you need to have ``/usr/bin/php5``.
