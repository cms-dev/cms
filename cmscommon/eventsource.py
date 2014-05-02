#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import re
import time
from collections import deque
from weakref import WeakSet

import six

from gevent import Timeout
from gevent.queue import Queue, Empty
from gevent.pywsgi import WSGIHandler

from werkzeug.wrappers import Request
from werkzeug.exceptions import NotAcceptable


__all__ = [
    "format_event",
    "Publisher", "Subscriber", "EventSource",
    ]


def format_event(id_, event, data):
    """Format the parameters to be sent on an event stream.

    Produce a text that, written on a Server-Sent Events connection,
    will cause the client to receive an event of the given type with
    the given data, and set the last event ID to the given id. No colon
    nor line breaks (i.e. "\\r\\n", "\\r", "\\n") are allowed in the
    event name and all line breaks in the event data will become "\\n".

    id_ (unicode): the ID of the event.
    event (unicode): the name of the event, or None.
    data (unicode): the content of the event, or None.

    return (bytes): the value to write on the stream.

    raise (TypeError): if any parameter isn't unicode.
    raise (ValueError): if event contains illegal characters.

    """
    if not isinstance(id_, six.text_type):
        raise TypeError("Id isn't unicode.")
    result = [b"id:%s" % id_.encode('utf-8')]

    if event is not None and event != "message":
        if not isinstance(event, six.text_type):
            raise TypeError("Event isn't unicode.")
        if not set("\r\n:").isdisjoint(event):
            raise ValueError("Event cannot contain '\\r', '\\n' or ':'.")
        result += [b"event:%s" % event.encode('utf-8')]

    if data is not None:
        if not isinstance(data, six.text_type):
            raise TypeError("Data isn't unicode.")
        for line in re.split("\r\n|(?<!\r)\n|\r(?!\n)", data):
            result += [b"data:%s" % line.encode('utf-8')]

    result += [b'\n']

    return b'\n'.join(result)


class Publisher(object):
    """The publish part of a pub-sub broadcast system.

    Publish-subscribe is actually an improper name, as there's just one
    "topic", making it a simple broadcast system. The publisher class
    is responsible for receiving messages to be sent, keeping them in
    a cache for a while, instantiating subscribers, each with its own
    queue, and pushing new messages to all these queues.

    """
    def __init__(self, size):
        """Instantiate a new publisher.

        size (int): the number of messages to keep in cache.

        """
        # We use a deque as it's efficient to add messages to one end
        # and have the ones at the other end be dropped when the total
        # number exceeds the given limit.
        self._cache = deque(maxlen=size)
        # We use a WeakSet as we want queues to be vanish automatically
        # when no one else is using (i.e. fetching from) them.
        self._sub_queues = WeakSet()

    def put(self, event, data):
        """Dispatch a new item to all subscribers.

        See format_event for details about the parameters.

        event (unicode): the type of event the client will receive.
        data (unicode): the associated data.

        """
        # Number of microseconds since epoch.
        key = int(time.time() * 1000000)
        msg = format_event("%x" % key, event, data)
        # Put into cache.
        self._cache.append((key, msg))
        # Send to all subscribers.
        for queue in self._sub_queues:
            queue.put(msg)

    def get_subscriber(self, last_event_id=None):
        """Obtain a new subscriber.

        The returned subscriber will receive all messages after the one
        with the given index (if they are still in the cache).

        last_event_id (unicode): the ID of the last message the client
            did receive, to request the one generated since then to be
            sent again. If not given no past message will be sent.

        return (Subscriber): a new subscriber instance.

        """
        queue = Queue()
        # If a valid last_event_id is provided see if cache can supply
        # missed events.
        if last_event_id is not None and \
                re.match("^[0-9A-Fa-f]+$", last_event_id):
            last_event_key = int(last_event_id, 16)
            if len(self._cache) > 0 and last_event_key >= self._cache[0][0]:
                # All missed events are in cache.
                for key, msg in self._cache:
                    if key > last_event_key:
                        queue.put(msg)
            else:
                # Some events may be missing. Ask to reinit.
                queue.put(b"event:reinit\n\n")
        # Store the queue and return a subscriber bound to it.
        self._sub_queues.add(queue)
        return Subscriber(queue)


class Subscriber(object):
    """The subscribe part of a pub-sub broadcast system.

    This class receives the messages sent to the Publisher that created
    it.

    """
    def __init__(self, queue):
        """Create a new subscriber.

        Make it wait for messages on the given queue, managed by the
        Publisher.

        queue (Queue): a message queue.

        """
        self._queue = queue

    def get(self):
        """Retrieve new messages.

        Obtain all messages that were put in the associated publisher
        since this method was last called, or (on the first call) since
        the last_event_id given to get_subscriber.

        return ([objects]): the items put in the publisher, in order
            (actually, returns a generator, not a list).

        raise (OutdatedError): if some of the messages it's supposed to
            retrieve have already been removed from the cache.

        """
        # Block until we have something to do.
        self._queue.peek()
        # Fetch all items that are immediately available.
        try:
            while True:
                yield self._queue.get_nowait()
        except Empty:
            pass


class EventSource(object):
    """A class that implements a Server-Sent Events [1] handler.

    This class is intended to be extended: it takes charge of all the
    hard work of managing a stream of events, leaving to the subclass
    only the fun of determining which events to send.

    Server-Sent Events are a way to make server push using long-polling
    over HTTP connections, preferably with chunked transfer encoding.
    This use wasn't a design goal of WSGI but this class, which is a
    WSGI application, should be able to manage it. It has been written
    to work on a gevent.pywsgi server, but should handle other servers
    as well.

    """
    _GLOBAL_TIMEOUT = 600
    _WRITE_TIMEOUT = 30
    _PING_TIMEOUT = 15

    _CACHE_SIZE = 250

    def __init__(self):
        """Create an event source.

        """
        self._pub = Publisher(self._CACHE_SIZE)

    def send(self, event, data):
        """Send the event to the stream.

        Intended for subclasses to push new events to clients. See
        format_event for the meaning of the parameters.

        event (unicode): the type of the event.
        data (unicode): the data of the event.

        """
        self._pub.put(event, data)

    def __call__(self, environ, start_response):
        """Execute this instance as a WSGI application.

        See the PEP for the meaning of parameters. The separation of
        __call__ and wsgi_app eases the insertion of middlewares.

        """
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        """Execute this instance as a WSGI application.

        See the PEP for the meaning of parameters. The separation of
        __call__ and wsgi_app eases the insertion of middlewares.

        """
        request = Request(environ)
        request.encoding_errors = "strict"

        # The problem here is that we'd like to send an infinite stream
        # of events, but WSGI has been designed to handle only finite
        # responses. Hence, to do this we will have to "abuse" the API
        # a little. This works well with gevent's pywsgi implementation
        # but it may not with others (still PEP-compliant). Therefore,
        # just to be extra-safe, we will terminate the response anyway,
        # after a long timeout, to make it finite.

        # The first such "hack" is the mechanism to trigger the chunked
        # transfer-encoding. The PEP states just that "the server *may*
        # use chunked encoding" to send each piece of data we give it,
        # if we don't specify a Content-Length header and if both the
        # client and the server support it. Accoring to the HTTP spec.
        # all (and only) HTTP/1.1 compliant clients have to support it.
        # We'll assume that the server software supports it too, and
        # actually uses it (gevent does!) even if we have no way to
        # check it. We cannot try to force such behavior as the PEP
        # doesn't even allow us to set the Transfer-Encoding header.

        # The second abuse is the use of the write() callable, returned
        # by start_response, even if the PEP strongly discourages its
        # use in new applications. We do it because we need a way to
        # detect when the client disconnects, and we hope to achieve
        # this by seeing when a call to write() fails, i.e. raises an
        # exception. This behavior isn't documented by the PEP, but it
        # seems reasonable and it's present in gevent (which raises a
        # socket.error).

        # The third non-standard behavior that we expect (related to
        # the previous one) is that no one in the application-to-client
        # chain does response buffering: neither any middleware not the
        # server (gevent doesn't!). This should also hold outside the
        # server realm (i.e. no proxy buffering) but that's definetly
        # not our responsibility.

        # The fourth "hack" is to avoid an error to be printed on the
        # logs. If the client terminates the connection, we catch and
        # silently ignore the exception and return gracefully making
        # the server try to write the last zero-sized chunk (used to
        # mark the end of the stream). This will fail and produce an
        # error. To avoid this we detect if we're running on a gevent
        # server and make it "forget" this was a chunked response.

        # Check if the client will understand what we will produce.
        if request.accept_mimetypes.quality(b"text/event-stream") <= 0:
            return NotAcceptable()(environ, start_response)

        # Initialize the response and get the write() callback. The
        # Cache-Control header is useless for conforming clients, as
        # the spec. already imposes that behavior on them, but we set
        # it explictly to avoid unwanted caching by unaware proxies and
        # middlewares.
        write = start_response(
            b"200 OK",
            [(b"Content-Type", b"text/event-stream; charset=utf-8"),
             (b"Cache-Control", b"no-cache")])

        # This is a part of the fourth hack (see above).
        if hasattr(start_response, "__self__") and \
                isinstance(start_response.__self__, WSGIHandler):
            handler = start_response.__self__
        else:
            handler = None

        # One-shot means that we will terminate the request after the
        # first batch of sent events. We do this when we believe the
        # client doesn't support chunked transfer. As this encoding has
        # been introduced in HTTP/1.1 (as mandatory!) we restrict to
        # requests in that HTTP version. Also, if it comes from an
        # XMLHttpRequest it has been probably sent from a polyfill (not
        # from the native browser implementation) which will be able to
        # read the response body only when it has been fully received.
        if environ[b"SERVER_PROTOCOL"] != b"HTTP/1.1" or request.is_xhr:
            one_shot = True
        else:
            one_shot = False

        # As for the Server-Sent Events [1] spec., this is the way for
        # the client to tell us the ID of the last event it received
        # and to ask us to send it the ones that happened since then.
        # [1] http://www.w3.org/TR/eventsource/
        # The spec. requires implementations to retry the connection
        # when it fails, adding the "Last-Event-ID" HTTP header. But in
        # case of an error they stop, and we have to (manually) delete
        # the EventSource and create a new one. To obtain that behavior
        # again we give the "last_event_id" as a URL query parameter
        # (with lower priority, to have the header override it).
        last_event_id = request.headers.get(b"Last-Event-ID",
                                            type=lambda x: x.decode('utf-8'))
        if last_event_id is None:
            last_event_id = request.args.get(b"last_event_id",
                                             type=lambda x: x.decode('utf-8'))

        # We subscribe to the publisher to receive events.
        sub = self._pub.get_subscriber(last_event_id)

        # Send some data down the pipe. We need that to make the user
        # agent announce the connection (see the spec.). Since it's a
        # comment it will be ignored.
        write(b":\n")

        # XXX We could make the client change its reconnection timeout
        # by sending a "retry:" line.

        # As a last line of defence from very bad-behaving servers we
        # don't want to the request to last longer than _GLOBAL_TIMEOUT
        # seconds (see above). We use "False" to just cause the control
        # exit the with block, instead of raising an exception.
        with Timeout(self._GLOBAL_TIMEOUT, False):
            # Repeat indefinitely.
            while True:
                # Proxies often have a read timeout. We try not to hit
                # it by not being idle for more than _PING_TIMEOUT
                # seconds, sending a ping (i.e. a comment) if there's
                # no real data.
                try:
                    with Timeout(self._PING_TIMEOUT):
                        data = b"".join(sub.get())
                        got_sth = True
                except Timeout:
                    data = b":\n"
                    got_sth = False

                try:
                    with Timeout(self._WRITE_TIMEOUT):
                        write(data)
                # The PEP doesn't tell what has to happen when a write
                # fails. We're conservative, and allow any unexpected
                # event to interrupt the request. We hope it's enough
                # to detect when the client disconnects. It is with
                # gevent, which raises a socket.error. The timeout (we
                # catch that too) is just an extra precaution.
                except Exception:
                    # This is part of the fourth hack (see above).
                    if handler is not None:
                        handler.response_use_chunked = False
                    break

                # If we decided this is one-shot, stop the long-poll as
                # soon as we sent the client some real data.
                if one_shot and got_sth:
                    break

        # An empty iterable tells the server not to send anything.
        return []
