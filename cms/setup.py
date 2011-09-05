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

from distutils.core import setup
import sys
import os

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
                "cms.box"],
      package_data={"cms.async":
                    [os.path.join("static", "*")],
                    "cms.server":
                    [
                     os.path.join("static", "contest", "sh", "*"),
                     os.path.join("static", "admin", "sh", "*"),
                     os.path.join("static", "ranking", "sh", "*"),
                     os.path.join("static", "contest","*.*"),
                     os.path.join("static", "admin","*.*"),
                     os.path.join("static", "ranking","*.*"),
                     os.path.join("templates","contest","errors","*.*"),
                     os.path.join("templates","admin","errors","*.*"),
                     os.path.join("templates","ranking","errors","*.*"),
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
    import os
    print "compiling mo-box..."
    os.chdir("box")
    os.system(os.path.join(".", "compile.sh"))
    os.chdir("..")
    print "  done."

if "install" in sys.argv:
    import shutil
    import os
    print "copying mo-box to /usr/local/bin/."
    shutil.copy(os.path.join(".", "box", "mo-box"),
                os.path.join("/", "usr", "local", "bin"))
    shutil.copy(os.path.join(".", "examples", "cms.conf"),
                os.path.join("/", "usr", "local", "etc", "cms.conf"))

