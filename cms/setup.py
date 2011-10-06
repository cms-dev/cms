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

from setuptools import setup

old_umask = os.umask(022)

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
                "cmscontrib",
                "cmstest"],
      package_data={"cms.async":
                    [os.path.join("static", "*")],
                    "cms.server": [
                        os.path.join("static", "sh", "*"),
                        os.path.join("static", "*.*"),
                        os.path.join("templates","contest","*.*"),
                        os.path.join("templates","admin","*.*"),
                        os.path.join("templates","ranking","*.*"),
                        ]},
      entry_points={
          "console_scripts": [
              "cmsLogService=cms.service.LogService:main",
              "cmsScoringService=cms.service.ScoringService:main",
              "cmsFileStorage=cms.service.FileStorage:main",
              "cmsEvaluationServer=cms.service.EvaluationServer:main",
              "cmsWorker=cms.service.Worker:main",
              "cmsResourceService=cms.service.ResourceService:main",
              "cmsChecker=cms.service.Checker:main",
              "cmsContestWebServer=cms.server.ContestWebServer:main",
              "cmsAdminWebServer=cms.server.AdminWebServer:main",

              "cmsTestFileStorage=cmstest.TestFileStorage:main",
              "cmsTestFileCacher=cmstest.TestFileCacher:main",

              "cmsYamlImporter=cmscontrib.YamlImporter:main",
              "cmsSpoolExporter=cmscontrib.SpoolExporter:main",
              "cmsContestExporter=cmscontrib.ContestExporter:main",
              "cmsContestImporter=cmscontrib.ContestImporter:main",
              ]
          },
      keywords="ioi programming contest grader management system",
      license="Affero General Public License v3",
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
    import pwd
    from glob import glob

    # Two kind of files: owned by root with umask 022, or owned by
    # cmsuser with umask 007. The latter because we do not want
    # regular users to sniff around our contests' data. Note that
    # umask is not enough if we copy files (permissions could be less
    # open in repository), so sometimes we do also a chmod.
    os.umask(007)

    print "creating user and group cmsuser."
    os.system("useradd cmsuser -c 'CMS default user' -M -r -s /bin/false -U")
    cmsuser = pwd.getpwnam("cmsuser")

    print "copying mo-box to /usr/local/bin/."
    os.umask(022)
    shutil.copy(os.path.join(".", "box", "mo-box"),
                os.path.join("/", "usr", "local", "bin"))
    os.chmod(os.path.join("/", "usr", "local", "bin"), 0755)

    print "copying configuration to /usr/local/etc/."
    os.umask(007)
    conf_file = os.path.join("/", "usr", "local", "etc", "cms.conf")
    if os.path.exists(os.path.join(".", "examples", "cms.conf")):
        shutil.copy(os.path.join(".", "examples", "cms.conf"), conf_file)
    else:
        shutil.copy(os.path.join(".", "examples", "cms.conf.sample"),
                    os.path.join("/", "usr", "local", "etc", "cms.conf"))
    os.chown(conf_file, cmsuser.pw_uid, cmsuser.pw_gid)
    os.chmod(conf_file, 0660)

    print "copying localization files:"
    os.umask(022)
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print "  %s" % country_code
        path = os.path.join("cms", "server", "mo", country_code, "LC_MESSAGES")
        dest_path = os.path.join("/", "usr", "local", "share", "locale",
                                 country_code, "LC_MESSAGES")
        os.system("mkdir -p %s" % dest_path)
        shutil.copy(os.path.join(path, "cms.mo"),
                    os.path.join(dest_path, "cms.mo"))
        os.chmod(os.path.join(dest_path, "cms.mo"), 0644)

    print "creating directories."
    dirs = [os.path.join("/", "var", "local", "log"),
            os.path.join("/", "var", "local", "cache"),
            os.path.join("/", "var", "local", "lib")]
    for d in dirs:
        os.umask(002)
        os.system("mkdir -p %s" % d)
        d = os.path.join(d, "cms")
        os.umask(007)
        os.system("mkdir -p %s" % d)
        os.chown(d, cmsuser.pw_uid, cmsuser.pw_gid)

    print "done."

# Go back to user's umask.
os.umask(old_umask)
