Task types
**********

Introduction
============

In the CMS nomenclature, the task type of a task describes how to compile and evaluate the submissions for that task. In particular, they may require additional files called managers, provided by the admins.

A submission goes through two steps involving the task type (that might also be empty): the compilation, that usually compute from the submitted files an executable, and the evaluation, that runs this executable against the set of testcases and produce for each of them an outcome.

Note that the outcome need not to be obviously tied to the score for the submission: typically, the outcome is computed by a grader (which is an executable or a program stub passed to CMS) or a comparator (a program that decide if the output of the contestant's program is correct) and not by the task type. Hence, the task type need not to know the meaning of the outcome, which is instead known by the grader and by the :doc:`score type <Score types>`.


Standard task types
===================

CMS ships with four task types: Batch, OutputOnly, Communication, TwoSteps. The first two are well tested and reasonably strong against cheating attempts and stable with respect to the evaluation times. Communication should be usable but it is less tested than the first two. The last one, TwoSteps, is probably not ready for usage in a public competition. The first two task types cover all but three of the IOI tasks up to IOI 2012.

You can configure, for each task, the behavior of these task types going on the task's page in AdminWebServer.


Batch
-----

In a Batch task, the contestant submits a single source file, in one of the three supported languages: C, C++, or Pascal.

The source file is either stand alone or to be compiled with a grader provided by the contest admins. The resulting executable does I/O either on standard input and output or on two files with a specified name. The output produced by the contestant's program is then compared to the correct output either using a simple diff algorithm (that ignores whitespaces) or using a comparator, provided by the admins.

The three choices (stand alone or with a grader, standard input and output or files, diff or comparator) are specified through parameters.

If the admins wants to provide a grader that takes care of reading the input and writing the output (so that the contestants only need to write one or more functions), they must provide three managers, called grader.c, grader.cpp and grader.pas. If header files are needed, they can be provided with names <basename>.h or <basename>lib.pas.

If the output is compared with a diff, the outcome will be a float, 0.0 if the output is not correct, 1.0 if it is. If the output is validate by a comparator, you need to provide a manager called checker that is an executable taking three arguments: input, correct output and contestant's output and that must write on standard output the outcome (that is going to be used by the score type, usually a float between 0.0 and 1.0), and on standard error a message to forward to the contestant.

