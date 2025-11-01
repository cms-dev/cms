Task versioning
***************

Introduction
============

Task versioning allows admins to store several sets of parameters for each task at the same time, to decide which are graded and among these the one that is shown to the contestants. This is useful before the contest, to test different possibilities, but especially during the contest to investigate the impact of an error in the task preparation.

For example, it is quite common to realize that one input file is wrong. With task versioning, admins can clone the original dataset (the set of parameters describing the behavior of the task), change the wrong input file with another one, or delete it, launch the evaluation on the new dataset, see which contestants have been affected by the problem, and finally swap the two datasets to make the new one live and visible by the contestants.

The advantages over the situation without task versioning are several:

- there is no need to take down scores during the re-evaluation with the new input;
- it is possible to make sure that the new input works well without showing anything to the contestants;
- if the problem affects just a few contestants, it is possible to notify just them, and the others will be completely unaffected.

Datasets
========

A dataset is a version of the sets of parameters of a task that can be changed and tested in background. These parameters are:

- time and memory limits;
- input and output files;
- libraries and graders;
- task type and score type.

Datasets can be viewed and edited in the task page. They can be created from scratch or cloned from existing ones. Of course, during a contest cloning the live dataset is the most used way of creating a new one.

Submissions are evaluated as they arrive against the live dataset and all other datasets with background judging enabled, or on demand when the admins require it.

Each task has exactly one live dataset, whose evaluations and scores are shown to the contestants. To change the live dataset, just click on "Make live" on the desired dataset. Admins will then be prompted with a summary of what changed between the new dataset and the previously active, and can decide to cancel or go ahead, possibly notifying the contestants with a message.

.. note::
   Remember that the summary looks at the scores currently stored for each submission. This means that if you cloned a dataset and changed an input, the scores will still be the old ones: you need to launch a recompilation, reevaluation, or rescoring, depending on what you changed, before seeing the new scores.

After switching live dataset, scores will be resent to RankingWebServer automatically.


