Contest Management System
=========================

Homepage: <http://cms-dev.github.io/>

[![Build Status](https://github.com/cms-dev/cms/workflows/ci/badge.svg)](https://github.com/cms-dev/cms/actions)
[![codecov](https://codecov.io/gh/cms-dev/cms/branch/master/graph/badge.svg)](https://codecov.io/gh/cms-dev/cms)
[![Join the chat at https://gitter.im/cms-dev/cms](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/cms-dev/cms?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Introduction
------------

CMS, or Contest Management System, is a distributed system for running
and (to some extent) organizing a programming contest.

CMS has been designed to be general and to handle many different types
of contests, tasks, scorings, etc. Nonetheless, CMS has been
explicitly build to be used in the 2012 International Olympiad in
Informatics, held in September 2012 in Italy.


Download
--------

**For end-users it's best to download the latest stable version of CMS,
which can be found already packaged at <http://cms-dev.github.io/>.**

This git repository, which contains the development version in its
master branch, is intended for developers and everyone interested in
contributing or just curious to see how the code works and wanting to
hack on it.

Please note that since the sandbox is contained in a
[git submodule](http://git-scm.com/docs/git-submodule) you should append
`--recursive` to the standard `git clone` command to obtain it. Or, if
you have already cloned CMS, simply run the following command from
inside the repository:

```bash
git submodule update --init
```


Support
-------

To learn how to install and use CMS, please read the **documentation**,
available at <https://cms.readthedocs.org/>.

If you have questions or need help troubleshooting some problem,
contact us in the **chat** at [gitter](https://gitter.im/cms-dev/cms),
or write on the **support mailing list**
<contestms-support@googlegroups.com>, where no registration is required
(you can see the archives on
[Google Groups](https://groups.google.com/forum/#!forum/contestms-support)).

To help with the troubleshooting, you can upload on some online
pastebin the relevant **log files**, that you can find in
/var/local/log/cms/ (if CMS was running installed) or in ./log (if it
was running from the local copy).

If you encountered a bug, please file an
[issue](https://github.com/cms-dev/cms/issues) on **GitHub** following
the instructions in the issue template.

**Please don't file issues to ask for help**, we are happy to help
on the mailing list or on gitter, and it is more likely somebody will
answer your query sooner.

You can subscribe to <contestms-announce@googlegroups.com> to receive
**announcements** of new releases and other important news. Register on
[Google Groups](https://groups.google.com/forum/#!forum/contestms-announce).

For **development** queries, you can write to
<contestms-discuss@googlegroups.com> and as before subscribe or see the
archives on
[Google Groups](https://groups.google.com/forum/#!forum/contestms-discuss).



Testimonials
------------

CMS has been used in several official and unofficial contests. Please
find an updated list at <http://cms-dev.github.io/testimonials.html>.

If you used CMS for a contest, selection, or a similar event, and want
to publicize this information, we would be more than happy to hear
from you and add it to that list.
