API for ContestWebServer
************************

Error handling
==============

Generally, API calls will return a non-200 status code on invalid usage. In
that case, the body of the response *may* be a JSON object with an "error"
field, containing additional information on the error.

Authentication
==============

All the log-in methods and restrictions that apply to normal ContestWebServer
usage also apply for API usage. In particular, this implies that IP autologin,
if configured, can be used for API calls.

Otherwise, making a ``POST`` request to the ``/api/login`` endpoint, passing
``username`` and ``password`` as form data (as is done for regular login), will
return a JSON object with the following structure:

.. sourcecode:: json

  {"login_data": /* string */ }

The content of the returned login data string should be passed to API calls
that require authentication in a ``X-CMS-Authorization`` header.

All other API methods described here require authentication.

Task list
=========

An authenticated ``GET`` request to ``/api/task_list``, done while the contest
is running, will return the following object:

.. sourcecode:: json

  {
    "tasks": [
      {
        "name": /* string */,
        "statements": [/* strings */],
        "submission_format": [/* strings */]
      }
    ]
  }


Tasks are ordered in the same order as in the UI. The ``name`` of the task is
used for additional task-specific API calls. ``statements`` contains a list of
languages for which a statement is available. ``submission_format`` contains a
list of files that will need to be submitted, where filenames containing the
``%l`` string represent source files (that will be compiled and run on the
server), and all other filenames represent output files.

Submit
======

An authenticated ``POST`` request to ``/api/{taskname}/submit`` will send a
submission. Files should be provided (according to the submission format) as
form data, with field names matching the submission format.

The request will return an object with the ID of the new submission:

.. sourcecode:: json

  {"id": /* string */}


List submissions
================

An authenticated ``GET`` request to ``/api/{taskname}/submission_list`` will
return an object describing all the submission done so far on the given task,
in chronological order:

.. sourcecode:: json

  {
    "list": [
      { "id": /* string */ }
    ]
  }

Task statement
==============

A PDF version of the task statement for a given language can be retrieved by
making an authenticated ``GET`` request to
``tasks/{taskname}/statements/{lang}``.

Scoring information
===================

An authenticated ``GET`` request to ``/tasks/{taskname}/submissions/{id}`` will
retrieve information on the submission with the given ``id``. In particular,
its field ``public_score`` will contain the score of this submission, and
``task_public_score`` will contain the current score for the task.

Additional details on the submission's results can be retrieved by making an
authenticated ``GET`` request to ``/tasks/{taskname}/submissions/{id}/details``.
The endpoint will return an HTML snippet matching what is seen by contestants.

Impersonation of users
======================

Administrators may impersonate a user and perform requests on their behalf.

This is accomplished by using the authentication endpoint without ``password``
and with an additional ``admin_token`` parameter equal to the
``contest_admin_token`` from the CMS configuration. The returned authentication
token refers to the given user, but it is marked as impersonated.

Requests carrying an impersonated authentication token may bypass certain
restrictions:

* IP-based login restrictions do no apply. (But if IP-based autologin is set,
  it overrides all authentication tokens including impersonated ones.)

* Hidden participation is never blocked.

* Requests can carry special parameters (either in the URL or in ``POST`` data)
  that bypasses further restrictions when set to ``1``:

    * ``override_phase_check`` lets the operation proceed regardless of contest
      phase (for example, you can submit even though the contest has already
      ended).

    * ``override_official`` (in the submit endpoint) makes the submission count
      as official regardless of contest phase.

    * ``override_max_number`` (in the submit endpoint) skips all checks for the
      maximum number of submits.

    * ``override_min_interval`` (in the submit endpoint) skips all checks for
      the minimum time interval between submits.
