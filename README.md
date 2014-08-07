Contest Management System
=========================

Homepage: <http://cms-dev.github.io/>


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

Please note that since the sandbox is contained in a [git submodule]
(http://git-scm.com/docs/git-submodule) you should append `--recursive`
to the standard `git clone` command to obtain it. Or, if you have
already cloned CMS, simply run the following command from inside the
repository:

```bash
git submodule update --init
```


Support
-------

The complete CMS documentation is at <https://cms.readthedocs.org/>.

The mailing list for announcements, user support and general discussion
is <contestms@freelists.org>. You can subscribe at
<http://www.freelists.org/list/contestms>. So far, it is an extremely
low traffic mailing list.

The mailing list for development discussion (to submit feedback,
proposals and critics, get opinions and reviews, etc.) is
<contestms-dev@freelists.org>. You can subscribe at
<http://www.freelists.org/list/contestms-dev>.

**Please don't use these mailing lists for bug reports. File them on
[github](https://github.com/cms-dev/cms/issues) instead.**

To help with the troubleshooting, you can collect the complete log
files that are placed in /var/local/log/cms/ (if CMS was running
installed) or in ./log (if it was running from the local copy).


Testimonials
------------

CMS has been used in several official and unofficial contests. Please
find an updated list at <http://cms-dev.github.io/testimonials.html>.

If you used CMS for a contest, selection, or a similar event, and want
to publicize this information, we would be more than happy to hear
from you and add it to that list.
