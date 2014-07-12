Detailed timing configuration
*****************************

This section describes the exact meaning of CMS parameters for
controlling the time window allocated to each contestant. Please see
:doc:`Configuring a contest` for a more gentle introduction and the
intended usage of the various parameters.

When setting up a contest, you will need to decide the time window in
which contestants will be able to interact with the contest (by
reading statements, submit solutions, ...). In CMS there are several
parameters that allow to control this time window, and it is also
possible to personalize it for each single user in case it is needed.

The first decision to chose among these two possibilities:

#. all contestants will start and end the contest at the same time
   (unless otherwise decided by the admins during the contest for
   fairness reasons);
#. each contestant will start the contest at the time they decide.

The first situation is that we will refer to as a fixed-window
contest, whereas we will refer to the second situation as
customized-window contest.

Fixed-window contests
=====================

These are quite simple to configure: you just need to set
``start_time`` and ``end_time``, and by default all users will be able
to interact with the contest between these two instants.

For fairness reasons, during the contest you may want to extend the
time window for all or for particular users. In the first case, you
just need to change the end_time parameter. In the latter case, you
can use one of two slightly different per-contestant parameters:
``extra_time`` and ``delay_time``.

You can use ``extra_time`` to award more time at the end of the
contest for a specific contestant, whereas you can use ``delay_time``
to shift in the future the time window of the contest just for that
user. There are two main practical differences between these two
options.

#. If you set ``extra_time`` to S seconds, the contestant will be able
   to interact with the contest in the first S seconds of it, whereas
   if you use ``delay_time``, they will not, as in the first case the
   time window is extended, in the second is shifted (if S seconds
   have already passed from the start of the contest, then there is no
   difference).

#. If tokens are generated every M minutes, and you set ``extra_time``
   to S seconds, then tokens for that contestants are generated at
   ``start_time`` + k*M (in particular, it might be possible that more
   tokens are generated for contestants with ``extra_time``); if
   instead you set ``delay_time`` to S seconds, tokens for that
   contestants are generated at start_time + S + k*M (i.e., they are
   shifted from the original, and the same amount of tokens as other
   contestants will be generated).

Of course it is possible to use both at the same time, but we do not
see much value in doing so.

Customized-window contests
==========================

In these contests, contestants can use a time window of fixed length
(``per_user_time``), starting from the first time they log in between
``start_time`` and ``end_time``. Moreover, the time window is capped at
``end_time`` (so if ``per_user_time`` is 5 hours and a contestant logs
in for the first time one minute before ``end_time``, they will have
just one minute).

Again, admins can change the time windows of specific contestants for
fairness reasons. In addition to ``extra_time`` and ``delay_time``,
they can also use ``starting_time``, which is automatically set by CMS
when the contestant logs in for the first time.

The meaning of ``extra_time`` is to extend both the contestant
time window (as defined by ``starting_time`` + ``per_user_time``) and
the contest time window (as defined by ``end_time``) by the value of
``extra_time``, but only for that contestant. Therefore, setting
``extra_time`` to S seconds effectively allows a contestant to use S
seconds more than before (regardless of the time they started the
contest).

Again, delay time is similar, but it shifts both contestant and
contest time window by that value. The effect on available time
similar to that achieved by setting ``extra_time``, with the
difference explained before in point 1. Also, there is a difference in
token generation as explained in point 2 above.

Finally, changing ``starting_time`` is very similar to changing
``delay_time``, but it shifts just the contestant time window, hence
if that window was already going over ``end_time``, at all effects
advancing ``starting_time`` would not award more time to the
contestant, because the end would still be capped at ``end_time``. The
effect on token generation is the same.

Again, there is probably no need to fiddle with more than one of these
three parameters, and our suggestion is to just use ``extra_time`` or
``delay_time`` to award more time to a contestant.
