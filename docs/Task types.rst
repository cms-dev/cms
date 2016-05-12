Task types
**********

Introduction
============

In the CMS terminology, the task type of a task describes how to compile and evaluate the submissions for that task. In particular, they may require additional files called managers, provided by the admins.

A submission goes through two steps involving the task type: the compilation, that usually creates an executable from the submitted files, and the evaluation, that runs this executable against the set of testcases and produces an outcome for each of them.

Note that the outcome doesn't need to be obviously tied to the score for the submission: typically, the outcome is computed by a grader (which is an executable or a program stub passed to CMS) or a comparator (a program that decides if the output of the contestant's program is correct) and not by the task type. Hence, the task type doesn't need to know the meaning of the outcome, which is instead known by the grader and by the :doc:`score type <Score types>`.


Standard task types
===================

CMS ships with four task types: Batch, OutputOnly, Communication, TwoSteps. The first two are well tested and reasonably strong against cheating attempts and stable with respect to the evaluation times. Communication should be usable but it is less tested than the first two. The last one, TwoSteps, is probably not ready for usage in a public competition. The first two task types cover all but three of the IOI tasks up to IOI 2012.

OutputOnly does not involve programming languages. Batch works with all supported languages (C, C++, Pascal, Java, Python, PHP), but only the first four if you are using a grader. The other task types have not been tested with Java, Python or PHP.

You can configure, for each task, the behavior of these task types on the task's page in AdminWebServer.


.. _tasktypes_batch:

Batch
-----

In a Batch task, the contestant submits a single source file, in one of the :ref:`allowed programming languages <configuringacontest_programming-languages>`.

The source file is either standalone or to be compiled with a grader provided by the contest admins. The resulting executable does I/O either on standard input and output or on two files with a specified name. The output produced by the contestant's program is then compared to the correct output either using a simple diff algorithm (that ignores whitespaces) or using a comparator, provided by the admins.

The three choices (standalone or with a grader, standard input and output or files, diff or comparator) are specified through parameters.

If the admins want to provide a grader that takes care of reading the input and writing the output (so that the contestants only need to write one or more functions), they must provide a manager for each allowed language, called :file:`grader.ext`, where ``ext`` is the standard extension of a source file in that language. If header files for C/C++ or Pascal are needed, they can be provided with names :file:`{task_name}.h` or :file:`{task_name}lib.pas`. See the end of the section for specific issues of Java.

If the output is compared with a diff, the outcome will be a float, 0.0 if the output is not correct, 1.0 if it is. If the output is validated by a comparator, you need to provide a manager called :file:`checker`. It must be an executable that:

- is compiled statically (e.g., with ``-static`` using ``gcc`` or ``g++``);
- takes three filenames as arguments (input, correct output and contestant's output);
- writes on standard output the outcome (that is going to be used by the score type, and is usually a float between 0.0 and 1.0);
- writes on standard error a message to forward to the contestant.

.. note:: The checker can also print the special strings "translate:success", "translate:wrong" or "translate:partial", which will be respectively shown to the contestants as the localized messages for "Output is correct", "Output isn't correct", and "Output is partially correct".

The submission format must contain one filename ending with ``.%l``. If there are additional files, the contestants are forced to submit them, the admins can inspect them, but they are not used towards the evaluation.

Batch tasks are supported also for Java, with some requirements. The solutions of the contestants must contain a class named like the short name of the task. A grader must have a class named ``grader`` that in turns contains the main method; whether in this case the contestants should write a static method or a class is up to the admins.


.. _tasktypes_outputonly:

OutputOnly
----------

In an OutputOnly task, the contestant submits a file for each testcase. Usually, the semantics is that the task specifies a task to be performed on an input file, and the admins provide a set of testcases composed of an input and an output file (as it is for a Batch task). The difference is that, instead of requiring a program that solves the task without knowing the input files, the contestant are required, given the input files, to provide the output files.

There is only one parameter for OutputOnly tasks, namely how correctness of the contestants' outputs is checked. Similarly to the Batch task type, these can be checked using a diff or using a comparator, that is an executable manager named :file:`checker`, with the same properties of the one for Batch tasks.

OutputOnly tasks usually have many uncorrelated files to be submitted. Contestants may submit the first output in a submission, and the second in another submission, but it is easy to forget  the first output in the other submission; it is also tedious to add every output every time. Hence, OutputOnly tasks have a feature that, if a submission lacks the output for a certain testcase, the current submission is completed with the most recently submitted output for that testcase (if it exists). This has the effect that contestants can work on a testcase at a time, submitting only what they did from the last submission.

The submission format must contain all the filenames of the form :file:`output_{num}.txt` where :samp:`{num}` is a three digit decimal number (padded with zeroes, and goes from 0 (included) to the number of testcases (excluded). Again, you can add other files that are stored but ignored. For example, a valid submission format for an OutputOnly task with three testcases is ``["output_000.txt", "output_001.txt", "output_002.txt"]``.


.. _tasktypes_communication:

Communication
-------------

In a Communication task, a contestant must submit a source file implementing a function, similarly to what happens for a Batch task. The difference is that the admins must provide both a stub, that is a source file that is compiled together with the contestant's source, and a manager, that is an executable.

For usual reactive tasks, ``num_processes`` is set to ``1``. In that case, the two programs communicate through two fifo files. The manager receives the name of the two fifos as its arguments. It is supposed to read from standard input the input of the testcase, and to start communicating some data to the other program through the fifo. The two programs exchange data through the fifo, until the manager is able to assign an outcome to the evaluation. The manager then writes to standard output the outcome and to standard error the message to the user, similarly to the what the checker does for a Batch task.

When ``num_processes`` is greater than ``1``, multiple instances of the submitted program are executed. ``2 * num_processes`` fifos are given to the manager, and two of them are given to each instance of the submitted program. An additional number is given to the submitted program to distinguish the processes. Two instances of the submitted program can't communicate directly. Time and memory consumed are calculated by summation.

If the program linked to the user-provided file fails (for a timeout, or for a non-allowed syscall), the outcome is 0.0 and the message describes the problem to the user.

The submission format must contain one or more filenames ending with ``.%l``. Multiple source files are simply linked together. Usually the number of files to submit is equal to ``num_processes``.


TwoSteps
--------

Warning: use this task type only if you know what are you doing.

In a TwoSteps task, contestants submit two source files implementing a function each (the idea is that the first function gets the input and compute some data from it with some restriction, and the second tries to retrieve the original data).

The admins must provide a manager, which is compiled together with both of the contestant-submitted files. The manager needs to be named :file:`manager.ext`, where ``ext`` is the standard extension of a source file in that language. Furthermore, for C/C++ and Pascal, appropriate header files for the two source files given by the contestants need to be provided, as well as manager header files (:file:`manager.h`, :file:`managerlib.pas`)---**even if they are empty**.

The resulting executable is run twice (one acting as the computer, one acting as the retriever). The manager in the computer executable must take care of reading the input from standard input; the one in the retriever executable of writing the retrieved data to standard output. Both must take responsibility of the communication between them through a pipe.

More precisely, the executable is called with two arguments: the first is an integer which is 0 if the executable is the computer, and 1 if it is the retriever; the second is the name of the pipe to be used for communication between the processes.

Normally, the standard output of the second invocation of the manager is compared to a provided reference output file using the white-diff comparator. However, the admins may provide a :file:`checker` executable, with the same properties as for Batch. If a file with such a name is found in the uploaded manager files, it will be run instead of the white-diff comparator.
