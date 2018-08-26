Task types
**********

Introduction
============

In the CMS terminology, the task type of a task describes how to compile and evaluate the submissions for that task. In particular, they may require additional files called managers, provided by the admins.

A submission goes through two steps involving the task type: the compilation, that usually creates an executable from the submitted files, and the evaluation, that runs this executable against the set of testcases and produces an outcome for each of them.

Note that the outcome doesn't need to be obviously tied to the score for the submission: typically, the outcome is computed by a grader (which is an executable or a program stub passed to CMS) or a comparator (a program that decides if the output of the contestant's program is correct) and not directly by the task type. Hence, the task type doesn't need to know the meaning of the outcome, which is instead known by the grader and by the :doc:`score type <Score types>`.

An exception to this is when the contestant's source fails (for example, exceeding the time limit); in this case the task type will assign directly an outcome, usually 0.0; admins must consider that when planning the outcomes for a task.


Standard task types
===================

CMS ships with four task types: Batch, OutputOnly, Communication, TwoSteps. The first three are well tested and reasonably strong against cheating attempts and stable with respect to the evaluation times. TwoSteps is a somewhat simpler way to implement a special case of a Communication task, but it is substantially less secure with respect to cheating. We suggest avoiding TwoSteps for new tasks, and migrating old tasks to Communication.

OutputOnly does not involve programming languages. Batch is tested with all languages CMS supports out of the box, (C, C++, Pascal, Java, C#, Python, PHP, Haskell, Rust), but only with the first five when using a grader. Communication is tested with C, C++, Pascal and Java. TwoSteps only with C. Regardless, with some work all task types should work with all languages.

Task types may have parameters to configure their behaviour (for example, a parameter for Batch defines whether to use a simple diff or a checker to evaluate the output). You can set these parameters, for each task, on the task's page in AdminWebServer.


.. _tasktypes_batch:

Batch
-----

In a Batch task, each testcase has an input (usually kept secret from the contestants), and the contestant's solution must produce a correct output for that input.

.. warning:: If the input, or part thereof, is supposed to be a secret from the contestant's code at least for part of the evaluation, then Batch is insecure and Communication should be used.

The contestant must submit a single source file; thus the submission format should contain one element with a ``.%l`` placeholder for the language extension.

Batch has three parameters:

- the first specifies whether the source submitted by the contestant is compiled on its own, or together with a grader provided by the admins;
- the second specifies the filenames of input and output (for reading and writing by the contestant source or by the grader), or whether to redirect them to standard input and standard output (if left blank);
- the third whether to compare correct output and contestant-produced output with a simple diff, or with an admin-provided comparator.

A grader is a source file that is compiled with the contestant's source, and usually performs I/O for the contestants, so that they only have to implement one or more functions. If the task uses a grader, the admins must provide a manager called :file:`grader.{ext}` for each allowed language, where :file:`{ext}` is the standard extension of a source file in that language. If header files are needed, they can be provided as additional managers with an appropriate extension (for example, ``.h`` for C/C++ and ``lib.pas`` for Pascal).

The output produced by the contestant (possibly through the grader) is then evaluated against the correct output. This can be done with :ref:`white-diff<tasktypes_white_diff>`, or using a :ref:`comparator<tasktypes_checker>`. In the latter case, the admins must provide an executable manager called :file:`checker`. If the contestant's code fails, this step is omitted, and the outcome will be 0.0 and the message will explain the reason.

Batch supports user tests; if a grader is used, the contestants must provide their own grader (a common practice is to provide a simple grader to contestants, that can be used for local testing and for server-side user tests). The output produced by the contestant's solution, possibly through the grader, is sent back to the contestant; it is not evaluated against a correct output.

.. note:: Batch tasks are supported also for Java, with some requirements. The top-level class in the contestant's source must be named like the short name of the task. The one in the grader (containing the main method) must be  named ``grader``.


.. _tasktypes_outputonly:

OutputOnly
----------

In an OutputOnly task, contestants can see the input of each testcase, and have to compute offline a correct output.

In any submission, contestants may submit outputs for any subset of testcases. The submission format therefore must contain one element for each testcase, and the elements must be of the form :file:`output_{codename}.txt` where :samp:`{codename}` is the codename for the testcase.

Moreover, CMS will automatically fill the missing files in the current submission with those in the previous one, as if the contestant had submitted them. For example, if there were 4 testcases, and the following submissions:

- submission s1 with files f1 and f2,
- submission s2 with files f2' and f3,
- submission s3 with file f4,

then s1 will be judged using f1 and f2; s2 will be judged using f1, f2' and f3; and finally s3 will be judged using f1, f2', f3 and f4.

OutputOnly has one parameter, that specifies whether to compare correct output and contestant-produced output with :ref:`white-diff<tasktypes_white_diff>`, or using a :ref:`comparator<tasktypes_checker>` (exactly the same as the third parameter for Batch). In the latter case, the admins must provide an executable manager called :file:`checker`.


.. _tasktypes_communication:

Communication
-------------

Communication tasks are similar to Batch tasks, but should be used when the input, or part of it, must remain secret, at least for some time, to the contestant's code. This is the case, for example, in tasks where the contestant's code must ask questions about the input; or when it must compute the solution incrementally after seeing partial views of the input.

In practice, Communication tasks have two processes, running in two different sandboxes:

- the first (called manager) is entirely controlled by the admins; it reads the input, communicates with the other one, and writes a :ref:`standard manager output<tasktypes_standard_manager_output>`;
- the second is where the contestant's code runs, optionally after being compiled together with an admin-provided stub that helps with the communication with the first process; it doesn't have access to the input, just to what the manager communicates.

This setup ensures that the contestant's code cannot access forbidden data, even in the case they have full knowledge of the admin code.

The admins must provide an executable manager called ``manager``. It can read the testcase input from stdin, and will also receive as argument the filenames of two FIFOs, from and to the contestant process (in this order). It must write to stdout the outcome and to stderr the message for the contestant (see :ref:`details about the format`<tasktypes_standard_manager_output>`). If the contestant's process fails, the output of the manager is ignored, and the outcome will be 0.0 and the message will explain the reason.

Admins can also provide a manager called :file:`stub.{ext}` for each allowed language, where :file:`{ext}` is the standard extension of a source file in that language. The task type can be set up to compile the stub with the contestant's source. Usually, a stub takes care of the communication with the manager, so that the contestants have to implement only a function. As for Batch, admins can also add header file that will be used when compiling the stub and the contestant's source.

The contestant's program, regardless of whether it's compiled with or without a stub, can be set up to communicate with the manager in two ways: through the standard input and output, or through FIFOs (in which case the FIFOs' filenames will be given as arguments, first the one from the manager and then the one to it).

The first parameter of the task type controls the number of user processes. If it is equal to 1, the behavior will be as explained above. If it is an integer N greater than 1, there are a few differences:

- there will be N processes with the contestant's code and the stub (if present) running;
- there will be N pairs of FIFOs, one for each process running the contestant's program; the manager will receive as argument all pairs in order, and each contestant program will receive its own (as arguments or redirected through stdin/stdout);
- each copy of the contestant's program will receive as an additional argument its 0-based index within the running programs;
- the time limit is checked against the total user time of all the contestant's processes.

The submission format must contain one or more filenames ending with ``.%l``. Multiple source files are simply linked together. Usually the number of files to submit is equal to the number of processes.

Communication supports user tests. In addition to the input file, contestant must provide the stub and their source file. The admin-provided manager will be used; the output returned to the contestant will be what the manager writes to the file :file:`output.txt`.

.. note:: Particular care must be taken for tasks where the communication through the FIFOs is particularly large or frequent. In these cases, the time to send the data may dominate the actual algorithm runtime, thus making it hard to distinguish between different complexities.


TwoSteps
--------

.. warning:: This task type is not secure; the user source could intercept the main function and take control of input reading and communication between the processes, which is not monitored. Admins should use Communication instead.

In a TwoSteps task, contestants submit two source files implementing a function each (the idea is that the first function gets the input and compute some data from it with some restriction, and the second tries to retrieve the original data).

The admins must provide a manager, which is compiled together with both of the contestant-submitted files. The manager needs to be named :file:`manager.{ext}`, where ``{ext}`` is the standard extension of a source file in that language. Furthermore, the admins must provide appropriate header files for the two source files and for the manager, even if they are empty.

The resulting executable is run twice (one acting as the computer, one acting as the retriever). The manager in the computer executable must take care of reading the input from standard input; the one in the retriever executable of writing the retrieved data to standard output. Both must take responsibility of the communication between them through a pipe.

More precisely, the executable is called with two arguments: the first is an integer which is 0 if the executable is the computer, and 1 if it is the retriever; the second is the name of the pipe to be used for communication between the processes.

TwoSteps has one parameter, similar to Batch's third, that specifies whether to compare the second process output with the correct output using white-diff or a checker. In the latter case, an executable manager named :file:`checker` must be provided.

TwoSteps supports user tests; contestants must provide the manager in addition to the input and their sources.

**How to migrate from TwoSteps to Communication.** Any TwoSteps task can be implemented as a Communication task with two processes. The functionalities in the stub should be migrated to Communication's manager, which also must enforce any restriction in the computed data.


.. _tasktypes_white_diff:

White-diff comparator
=====================

White-diff is the only built-in comparator. It can be used when each testcase has a unique correct output file, up to whitespaces. White-diff will report an outcome of 1.0 if the correct output and the contestant's output match up to whitespaces, or 0.0 if they don't.

More precisely, white-diff will return that a pair of files match if all of these conditions are satisfied:

- they have the same number of lines (apart from trailing lines composed only of whitespaces, which are ignored);
- for each corresponding line in the two files, the list of non-empty, whitespace-separated tokens is the same (in particular, tokens appear in the same order).

It treats as whitespace any repetition of these characters: space, newline, carriage return, tab, vertical tab, form feed.

Note that spurious empty lines in the middle of an output will make white-diff report a no-match, even if all tokens are correct.


.. _tasktypes_checker:

Checker
=======

When there are multiple correct outputs, or when there is partial scoring, white-diff is not powerful enough. In this cases, a checker can be used to perform a complex validation. It is an executable manager, usually named :file:`checker`.

It will receive as argument three filenames, in order: input, correct output, and contestant's output. It will then write a :ref:`standard manager output<tasktypes_standard_manager_output>` to stdout and stderr.

It is preferred to compile the checker statically (e.g., with ``-static`` using ``gcc`` or ``g++``) to avoid potential problems with the sandbox.


.. _tasktypes_standard_manager_output:

Standard manager output
=======================

A standard manager output is a format that managers can follow to write an outcome and a message for the contestant.

To follow the standard manager output, a manager must write on stdout a single line, containing a floating point number, the outcome; it must write to stderr a single line containing the message for the contestant. Following lines to stdout or stderr will be ignored.

.. note:: If the manager writes to standard error the special strings "translate:success", "translate:wrong" or "translate:partial", these will be respectively shown to the contestants as the localized messages for "Output is correct", "Output isn't correct", and "Output is partially correct".


.. _tasktypes_custom:

Custom task types
=================

If the set of default task types doesn't suit a particular need, a custom task type can be provided. For that, in a separate "workspace" (i.e., a directory disjoint from CMS's tree), write a new Python class that extends :py:class:`cms.grading.tasktypes.TaskType` and implements its abstract methods. The docstrings of those methods explain what they need to do, and the default task types can provide examples.

An accompanying :file:`setup.py` file must also be prepared, which must reference the task type's class as an "entry point": the ``entry_points`` keyword argument of the ``setup`` function, which is a dictionary, needs to contain a key named ``cms.grading.tasktypes`` whose value is a list of strings; each string represents an entry point in the format ``{name}={package.module}:{Class}``, where ``{name}`` is the name of the entry point (at the moment it plays no role for CMS, but please name it in the same way as the class) and ``{package.module}`` and ``{Class}`` are the full module name and the name of the class for the task type.

A full example of :file:`setup.py` is as follows:

.. sourcecode:: python

    from setuptools import setup, find_packages

    setup(
        name="my_task_type",
        version="1.0",
        packages=find_packages(),
        entry_points={
            "cms.grading.tasktypes": [
                "MyTaskType=my_package.my_module:MyTaskType"
            ]
        }
    )

Once that is done, install the distribution by executing

.. sourcecode:: bash

    python3 setup.py install

CMS needs to be restarted for it to pick up the new task type.

For additional information see the `general distutils documentation <https://docs.python.org/3/distutils/setupscript.html>`_ and the `section of the setuptools documentation about entry points <https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins>`_.
