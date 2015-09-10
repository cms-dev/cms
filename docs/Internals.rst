Internals
*********

This section contains some details about some CMS internals. They are
mostly meant for developers, not for users. However, if you are curious
about what's under the hood, you will find something interesting here
(though without any pretension of completeness). Moreover, these are
not meant to be full specifications, but only useful notes for the
future.

Oh, I was nearly forgetting: if you are curious about what happens
inside CMS, you may actually be interested in helping us writing
it. We can assure you it is a very rewarding task. After all, if you
are hanging around here, you must have some interest in coding! In
case, feel free `to get in touch with us
<http://cms-dev.github.io/>`_.

RPC protocol
============

Different CMS processes communicate between them by mean of TCP
sockets. Once a service has established a socket with another, it can
write messages on the stream; each message is a JSON-encoded object,
terminated by a ``\r\n`` string (this, of course, means that ``\r\n``
cannot be used in the JSON encoding: this is not a problem, since new
lines inside string represented in the JSON have to be escaped
anyway).

An RPC request must be of the form (it is pretty printed here, but it
is sent in compact form inside CMS)::

  {
    "__method": <name of the requested method>,
    "__data": {
                <name of first arg>: <value of first arg>,
                ...
              },
    "__id": <random ID string>
  }

The arguments in ``__data`` are (of course) not ordered: they have to
be matched according to their names. In particular, this means that
our protocol enables us to use a ``kwargs``-like interface, but not a
``args``-like one. That's not so terrible, anyway.

The ``__id`` is a random string that will be returned in the response,
and it is useful (actually, it's the only way) to match requests with
responses.

The response is of the form::

  {
    "__data": <return value or null>,
    "__error": <null or error string>,
    "__id": <random ID string>
  }

The value of ``__id`` must of course be the same as in the request.
If ``__error`` is not null, then ``__data`` is expected to be null.

Backdoor
========

Setting the ``backdoor`` configuration key to true causes services to
serve a Python console (accessible with netcat), running in the same
interpreter instance as the service, allowing to inspect and modify its
data, live. It will be bound to a local UNIX domain socket, usually at
:file:`/var/local/run/cms/{service}_{shard}`. Access is granted only to
users belonging to the cmsuser group.
Although there's no authentication mechanism to prevent unauthorized
access, the restrictions on the file should make it safe to run the
backdoor everywhere, even on workers that are used as contestants'
machines.
You can use ``rlwrap`` to add basic readline support. For example, the
following is a complete working connection command:

.. sourcecode:: bash

    rlwrap netcat -U /var/local/run/cms/EvaluationService_0

Substitute ``netcat`` with your implementation (``nc``, ``ncat``, etc.)
if needed.
