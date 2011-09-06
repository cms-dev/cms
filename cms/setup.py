#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import sys
import os

from distutils.core import setup

setup(name="cms",
      version="0.1",
      author="Matteo Boscariol, Stefano Maggiolo, Giovanni Mascellani",
      author_email="s.maggiolo@gmail.com",
      url="",
      download_url="",
      description="A contest management system and grader "
                  "for IOI-like programming competitions",
      packages=["cms",
                "cms.db",
                "cms.server",
                "cms.service",
                "cms.util",
                "cms.async",
                "cms.box",
                "contribcms"],
      package_data={"cms.async":
                    [os.path.join("static", "*")],
                    "cms.server": [
                        os.path.join("static", "sh", "*"),
                        os.path.join("static", "*.*"),
                        os.path.join("templates","contest","*.*"),
                        os.path.join("templates","admin","*.*"),
                        os.path.join("templates","ranking","*.*"),
                        ]},
      keywords="ioi programming contest grader management system",
      license="Lesser Affero General Public License v3",
      classifiers=["Development Status :: 3 - Alpha",
                   "Natural Language :: English",
                   "Operating System :: POSIX :: Linux",
                   "Programming Language :: Python :: 2",
                   "License :: OSI Approved :: "
                   "GNU Affero General Public License v3",
                  ],
     )

if "build" in sys.argv:
    import re
    from glob import glob

    print "compiling mo-box..."
    os.chdir("box")
    os.system(os.path.join(".", "compile.sh"))
    os.chdir("..")

    print "compiling localization files:"
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print "  %s" % country_code
        path = os.path.join("cms", "server", "mo", country_code, "LC_MESSAGES")
        os.system("mkdir -p %s" % path)
        os.system("msgfmt %s -o %s" % (locale, os.path.join(path, "cms.mo")))

    print "done."

if "install" in sys.argv:
    import shutil
    import re
    from glob import glob

    print "copying mo-box to /usr/local/bin/."
    shutil.copy(os.path.join(".", "box", "mo-box"),
                os.path.join("/", "usr", "local", "bin"))

    print "copying configuration to /usr/local/etc/."
    shutil.copy(os.path.join(".", "examples", "cms.conf"),
                os.path.join("/", "usr", "local", "etc", "cms.conf"))

    print "copying localization files:"
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print "  %s" % country_code
        path = os.path.join("cms", "server", "mo", country_code, "LC_MESSAGES")
        dest_path = os.path.join("/", "usr", "local", "share", "locale",
                                 country_code, "LC_MESSAGES")
        os.system("mkdir -p %s" % dest_path)
        shutil.copy(os.path.join(path, "cms.mo"),
                    os.path.join(dest_path, "cms.mo"))

    print "done."


