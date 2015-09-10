Score types
***********

Introduction
============

For every submission, the score type of a task comes into play after the :doc:`task type <Task types>` produced an outcome for each testcase. Indeed, the most important duty of the score type is to describe how to translate the list of outcomes into a single number: the score of the submission. The score type also produces a more informative output for the contestants, and the same information (score and detail) for contestants that did not use a token on the submission. In CMS, these latter set of information is called public, since the contestant can see them without using any tokens.


Standard score types
====================

Like task types, CMS has the most common score types built in. They are Sum, GroupMin, GroupMul, GroupThreshold.

The first of the four well-tested score types, Sum, is the simplest you can imagine, just assigning a certain amount of points for each correct testcases. The other three are useful for grouping together testcases and assigning points for that group only if some conditions held. Groups are also known as subtasks in some contests. The group score types also allow test cases to be weighted, even for groups of size 1.

Also like task types, the behavior of score types is configurable from the task's page in AdminWebServer.


.. _scoretypes_sum:

Sum
---

This score type interprets the outcome for each testcase as a floating-point number measuring how good the submission was in solving that testcase, where 0.0 means that the submission failed, and 1.0 that it solved the testcase correctly. The score of that submission will be the sum of all the outcomes for each testcase, multiplied by an integer parameter given in the Score type parameter field in AdminWebServer. The parameter field must contain only this integer. The public score is given by the same computation over the public testcases instead of over all testcases.

For example, if there are 20 testcases, 2 of which are public, and the parameter string is ``5``, a correct solution will score 100 points (20 times 5) out of 100, and its public score will be 10 points (2 times 5) out of 10.


.. _scoretypes_groupmin:

GroupMin
--------

With the GroupMin score type, outcomes are again treated as a measure of correctness, from 0.0 (incorrect) to 1.0 (correct); testcases are split into groups, and each group has an integral multiplier. The score is the sum, over all groups, of the minimum outcome for that group times the multiplier. The public score is computed over all groups in which all testcases within are public.

More precisely, the parameters string for GroupMin is of the form :samp:`[[{m1}, {t1}], [{m2}, {t2}], ...]`, meaning that the first group comprises the first :samp:`{t1}` testcases and has multiplier :samp:`{m1}`; the second group comprises the testcases from the :samp:`{t1}` + 1 to the :samp:`{t1}` + :samp:`{t2}` and has multiplier :samp:`{m2}`; and so on.


GroupMul
--------

GroupMul is almost the same as GroupMin; the only difference is that instead of taking the minimum outcome among the testcases in the group, it takes the product of all outcomes. It has the same behavior as GroupMin when all outcomes are either 0.0 or 1.0.


GroupThreshold
--------------

GroupThreshold thinks of the outcomes not as a measure of success, but as an amount of resources used by the submission to solve the testcase. The testcase is then successfully solved if the outcome is between 0.0 and a certain number, the threshold, specified separately for each group.

The parameter string is of the form :samp:`[[{m1}, {t1}, {T1}], [{m2}, {t2}, {T2}], ...]` where the additional parameter :samp:`{T}` for each group is the threshold.
