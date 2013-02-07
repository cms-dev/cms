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


.. _tasktypes_batch:

Batch
-----

In a Batch task, the contestant submits a single source file, in one of the three supported languages: C, C++, or Pascal.

The source file is either stand alone or to be compiled with a grader provided by the contest admins. The resulting executable does I/O either on standard input and output or on two files with a specified name. The output produced by the contestant's program is then compared to the correct output either using a simple diff algorithm (that ignores whitespaces) or using a comparator, provided by the admins.

The three choices (stand alone or with a grader, standard input and output or files, diff or comparator) are specified through parameters.

If the admins wants to provide a grader that takes care of reading the input and writing the output (so that the contestants only need to write one or more functions), they must provide three managers, called grader.c, grader.cpp and grader.pas. If header files are needed, they can be provided with names <basename>.h or <basename>lib.pas.

If the output is compared with a diff, the outcome will be a float, 0.0 if the output is not correct, 1.0 if it is. If the output is validate by a comparator, you need to provide a manager called checker that is an executable taking three arguments: input, correct output and contestant's output and that must write on standard output the outcome (that is going to be used by the score type, usually a float between 0.0 and 1.0), and on standard error a message to forward to the contestant.

The submission format must contain one filename ending with .%l. If there are additional files, the contestants are forced to submit them, the admins can inspect them, but they are not used towards the evaluation.


.. _tasktypes_outputonly:

OutputOnly
----------

In an OutputOnly task, the contestant submit an file for each testcase. Usually, the semantic is that the task specify a task to be performed on an input file, and the admins provide a set of testcases composed of an input and an output file (as it is for a Batch task). The difference is that, instead of requiring a program that solves the task without knowing the input files, the contestant are required, given the input files, to provide the output files.

There is only one parameter for OutputOnly tasks, namely the way of checking the correctness of the outputs given by the contestants. Similarly to the Batch task type, these can be checked using a diff or using a comparator, that is an executable manager named checker, with the same properties of the one for Batch tasks.

OutputOnly tasks usually have many uncorrelated files to be submitted. Contestants may submit the first output in a submission, and the second in another submission, but it is easy to forget  the first output in the other submission; it is also tedious to add every output every time. Hence, OutputOnly tasks have a feature that, if a submission lacks the output for a certain testcases, the current submission is completed with the last output submitted for that testcase (it it exists). This has the effect that contestants can work on a testcase at a time, submitting only what they did from the last submission.

The submission format must contain all the filenames of the form output_XXX.txt where XXX is a three digit decimal number (padded with zeroes, and goes from 0 to the number of testcases minus one. Again, you can add other files that are stored but ignored. For example, a valid submission format for an OutputOnly task with three testcases is ["output_000.txt", "output_001.txt", "output_002.txt"].


.. _tasktypes_communication:

Communication
-------------

In a Communication task, a contestant must submit a source file implementing a function, similarly to what happens for a Batch task. The difference is that the admins must provide both a stub, that is a source file that is compiled together with the contestant's source, and a manager, that is an executable.

The two programs communicate through two fifo files. The manager receives the name of the two fifo as its arguments. It is supposed to read from standard input the input of the testcase, and to start communicating some data to the other program through the fifo. The two program than exchange data through the fifo, until the manager is able to assign an outcome to the evaluation. The manager then writes to standard output the outcome and to standard error the message to the user.

If the program linked to the user-provided file fails (for a timeout, or for a non-allowed syscall), the outcome is 0.0 and the message describes the problem to the user.

The submission format must contain one filename ending with .%l. If there are additional files, the contestants are forced to submit them, the admins can inspect them, but they are not used towards the evaluation.


TwoSteps
--------

Warning: use this task type only if you know what are you doing.

In a TwoSteps task, contestants submit two source files implementing a function each (the idea is that the first function gets the input and compute some data from it with some restriction, and the second tries to retrieve the original data).

The admins must provide a manager compiled together with both files. The resulting executable is run twice (one acting as the computer, one acting as the retriever. The manager in the computer executable must take care of reading the input from standard input; the one in the retriever executable of writing the outcome and the explanation message to standard output and error respectively. Both must take responsibility of the communication between them through a pipe.

More precisely, the executable are called with two arguments: the first is an integer which is 0 if the executable is the computer, and 1 if it is the retriever; the second is the name of the pipe to be used for communication between the processes.


