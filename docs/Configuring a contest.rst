Configuring a contest
*********************

In the following text "user" and "contestant" are used interchangeably.

Configuration parameters will be referred to using their internal name, but it should always be easy to infer what fields control them in the AWS interface by using their label.


Limitations
===========

Contest administrators can limit the ability of users to submit submissions and user_tests, by setting the following parameters:

- ``max_submission_number`` / ``max_user_test_number``

  These set, respectively, the maximum number of submissions/user_tests that will be accepted for a certain user. Any attempt to send in additional submissions/user_tests after that limit has been reached will fail.

- ``min_submission_interval`` / ``min_user_test_interval``

  These set, respectively, the minimum amount of time the user is required to wait after a submission/user_test has been submitted before he's allowed to send in new ones. Any attempt to submit a submission/user_test before this timeout has expired will fail.

The limits can be set both on individual tasks and on the whole contest. In the latter case they apply to *all* submissions/user_tests of the user. This means that "maximum number" limitations applies to the sum of the number of submissions/user_tests of all tasks and that the "minimum interval" limitation applies to the most recent submission/user_test in any of the tasks.

Each of these fields can be left unset to prevent the corresponding limitation from being enforced.


Tokens
======

Tokens are a metaphor introduced to provide contestants a limited access to the detailed results of their submissions on the private testcases.

For every submission sent in for evaluation, a contestant is always able to see if it succesfully compiled. He/she is also able to see the scores it got on the public testcases of the task, if any. All information about the other so-called private testcases is kept hidden. Yet, a contestant can choose to use one of its tokens to "unlock" a certain submission of his/her choice. After he/she does this, detailed results are available for all testcases, as if they were all public. A token, once used, is consumed and lost forever. Contestants have a set of available tokens at their disposal, where the ones they use are picked from. These sets are managed by CMS according to rules defined by the contest administrators.

Tokens also affect the score computation. That is, all "tokened" submissions will concur, together with the last submitted one, when computing the score for a task. See also :ref:`configuringacontest_score-rounding`.

Actually, there are two types of tokens: contest-tokens and task-tokens. A user has to play two tokens, one of each type, to unlock a submission. As the names suggest, contest-tokens are bound to the contest while task-tokens are bound to a specific task. That means that there's just one set of contest-tokens but there can be many sets of task-tokens (precisely one for every task). These sets are controlled independently by rules defined either on the contest or on the task.

Rules consist of six parameters: ``token_initial``, ``token_gen_number``, ``token_gen_time``, ``token_max``, ``token_total`` and ``token_min_interval``. A token set can be disabled, finite or infinite.

If ``token_initial`` is unset then the token set is disabled: there are no tokens available for use (and there never will be).

Otherwise, if ``token_gen_number`` is set to a positive integer and ``token_gen_time`` is set to zero the token set is infinite: the user will never run out of available tokens.

Otherwise the token set is finite. This means that the token set can be effectively represented by a non-negative integer counter: its cardinality. When the contest starts (or when the user starts its per-user time-frame) the set will be filled with ``token_initial`` tokens (i.e. the counter is set to ``token_initial``). If the set is not empty (i.e. the counter is not zero) the user can use a token. After that, the token is discarded (i.e. the counter is decremented by one). New tokens can be generated during the contest: ``token_gen_number`` new tokens will be given to the user after every ``token_gen_time`` minutes from the start (note that this value can be zero, thus disabling token generation). If ``token_max`` is set to a non-negative integer, the set cannot contain more than ``token_max`` tokens, therefore generation of new tokens will stop at that value.

The use of tokens can be limited with ``token_min_interval`` and ``token_total``: users have to wait at least ``token_min_interval`` seconds after they used a token before they can use another one (this parameter can be zero), and they cannot use more that ``token_total`` tokens in total (this parameter can be unset). Note that ``token_total`` has no effect if the token set is infinite.

If you just want to limit one type of tokens then you need to set the other type to be infinite (e.g. if you want put a limit only on contest-tokens you need to set all task-token sets to be infinite). CWS is aware of this "implementation details" and when one type is infinite it just shows information about the other type, calling it simply "token" (i.e. removing the "contest-" or "task-" prefix).

Note that "token sets" are "intangible": they're just a counter shown to the user, computed dynamically every time. Yet, once a token is used, a Token object will be created, stored in the database and associated with the submission it was used on.

Changing token rules during a contest may lead to inconsistencies. Do it at your own risk!


.. _configuringacontest_score-rounding:

Score rounding
==============

Based on the ScoreTypes in use and on how they're configured, some submissions may be given a floating-point score. Contest administrators will probably want to show only a small number of these decimal places in the scoreboard. This can be achieved with the ``score_precision`` fields on the contest and tasks.

The score of an user on a certain task is the maximum among the scores of the "tokened" submissions for that task, and the last one. This score is rounded to a number of decimal places equal to the ``score_precision`` field of the task. The score of an user on the whole contest is the sum of the *rounded* scores on each task. This score itself is then rounded to a number of decimal places equal to the ``score_precision`` field of the contest.

Note that some "internal" scores used by ScoreTypes (for example the subtask score) are not rounded using this procedure. At the moment the subtask scores are always rounded at two decimal places and there's no way to configure that (note that the score of the submission is the sum of the *unrounded* scores of the subtasks). That will be changed soon. See `issue #33 <https://github.com/cms-dev/cms/issues/33>`_.

(We store the unrounded score in the DB so you can change the ``score_precision`` at any time without having to reevaluate any submission)


Primary statements
==================

When there are many statements for a certain task (which are often different translations of the same statement) contest administrators may want to highlight some of them to the users. These may include, for example, the "official" version of the statement (the one that'll considered as reference in case of questions or appeals) or the translations for the languages understood by that particular user. To do that the ``primary_statements`` field of the tasks and the users has to be used.

The ``primary_statements`` field for the tasks is a JSON-encoded list of strings: it specifies the language codes of the statements that will be highlighted to all users. A valid example is ``["en_US", "it"]``. The ``primary_statements`` field for the users is a JSON-encoded object of lists of strings. Each item in this object specifies a task by its name and provides a list of language codes of the statements to highlight. For example ``{"task1": ["de"], "task2": ["de_CH"]}``.

Note that users will always be able to access all statements, regardless of the ones that are highlit. Note also that language codes in the form ``xx`` or ``xx_YY`` (where ``xx`` is an `ISO 639-1 code <http://www.iso.org/iso/language_codes.htm>`_ and ``YY`` is an `ISO 3166-1 code <http://www.iso.org/iso/country_codes.htm>`_) will be recognized and presented accordingly. For example ``en_AU`` will be shown as "English (Australia)".


Timezone
========

CMS stores all times as UTC timestamps and converts them to an appropriate timezone when displaying them. This timezone can be specified on a per-user and per-contest basis with the ``timezone`` field. It needs to contain a string in the format ``Europe/Rome`` (actually, any string recognized by `pytz <http://pytz.sourceforge.net/>`_ will work).

When CWS needs to show a timestamp to the user it first tries to show it according to the user's timezone. If the string defining the timezone is unrecognized (for example it's the empty string), CWS will fallback to the contest's timezone. If it's again unable to interpret that string it'll use the local time of the server.


User login
==========

Users log into CWS using a username and a password. These have to be specified, respectively, in the ``username`` and ``password`` fields (in cleartext!). These credentials need to be inserted (i.e. there's no way to have an automatic login, a "guest" session, etc.) and, if they match, the login (usually) succeeds. The user needs to login again if he/she doesn't navigate the site for ``cookie_duration`` seconds (specified in the :file:`cms.conf` file).

In fact, there are other reasons that can cause the login to fail. If the ``ip_lock`` option (in :file:`cms.conf`) is set to ``true`` then the login will fail if the IP address that attempted it is different from the ``ip`` field of the specified user. If ``ip`` is ``0.0.0.0`` then this check will be skipped, even if ``ip_lock`` is ``true``. Note that if a reverse-proxy (like nginx) is in use then it's necessary to set ``is_proxy_used`` (in :file:`cms.conf`) to ``true``.

The login also fails if ``block_hidden_users`` (in :file:`cms.conf`) is ``true`` and the user one wants to login as has the ``hidden`` field set.


USACO-like contests
===================

The most peculiar trait of the `USACO <http://usaco.org/>`_ contests is that the contests themselves are many days long but each user is only able to compete for a few hours after its first login (after that he/she is not able to send any more submissions). This can be done in CMS too, using the ``per_user_time`` fields of contests. If it's unset the contest will behave "normally", that is all users will be able to submit solutions from the contest's ``start`` until the contest's ``stop``. If, instead, ``per_user_time`` is set to a positive integer value then an use will only have a limited amount of time. In particular, after he/she logs in, he/she will be presented with an interface similar to the pre-contest one, with an addition: a "start" button. Clicking on this button starts the time-frame in which the user can compete (i.e. read statements, download attachments, submit solutions, use tokens, send user_tests, etc.). This time-frame ends after ``per_user_time`` seconds or when the contest ``stop`` time is reached, whatever comes first. After that the interface will be identical to the post-contest one: the user won't be able to do anything. See `issue #61 <https://github.com/cms-dev/cms/issues/61>`_.

The time at which the user click the "start" button is recorded in the ``starting_time`` field of the user. You can change that to shift the user's time-frame (but we suggest to use ``extra_time`` for that, explained in :ref:`configuringacontest_extra-time`) or unset it to make the user able to start its time-frame again. Do it at your own risk!


.. _configuringacontest_extra-time:

Extra time
==========

Contest administrators may want to give some users a short additional amount of time in which they can compete to compensate for an incident (e.g. a hardware failure) that made them unable to compete for a while during the "intended" time-frame. That's what the ``extra_time`` field of the users is for. The time-frame in which the user is allowed to submit solutions is expanded by its ``extra_time``, even if this would lead the user to be able to submit after the end of the contest.

Note that in its extra time the user will continue to receive newly generated tokens. If you don't want him/her to have more tokens that other contestants set the ``token_total`` parameter described above to the number of tokens you expect a user to have at his/her disposal during the whole contest (if it doesn't already have a value less than or equal to this). See also `issue #29 <https://github.com/cms-dev/cms/issues/29>`_.
