Internals
*********

This section contains some details about some CMS internals. They're
mostly meant for developers, not for users. However, if you're curious
about what's under the hood, you'll find something interesting here
(though without any pretension of completeness).

RPC protocol
============

Different CMS processes communicate between them by mean of TCP
sockets. Once a service has established a socket with another, it can
write messages on the stream; each message is a JSON-encoded object,
terminated by a ``\r\n`` string.
