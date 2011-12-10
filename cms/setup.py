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
import shutil
import re
import pwd

from glob import glob
from setuptools import setup

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
                "cmsranking",
                "cmscontrib",
                "cmstest"],
      package_data={"cms.async":
                    [os.path.join("static", "*")],
                    "cms.server": [
                        os.path.join("static", "jq", "*"),
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
              "cmsEvaluationService=cms.service.EvaluationService:main",
              "cmsWorker=cms.service.Worker:main",
              "cmsResourceService=cms.service.ResourceService:main",
              "cmsChecker=cms.service.Checker:main",
              "cmsContestWebServer=cms.server.ContestWebServer:main",
              "cmsAdminWebServer=cms.server.AdminWebServer:main",

              "cmsRankingWebServer=cmsranking.RankingWebServer:main",

              "cmsTestFileStorage=cmstest.TestFileStorage:main",
              "cmsTestFileCacher=cmstest.TestFileCacher:main",

              "cmsYamlImporter=cmscontrib.YamlImporter:main",
              "cmsYamlReimporter=cmscontrib.YamlReimporter:main",
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

def copyfile(src, dest, owner, perm):
    """Copy the file src to dest, and assign owner and permissions.

    src (string): the complete path of the source file.
    dest (string): the complete path of the destination file (i.e.,
                   not the destination directory).
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm (integer): the permission for dest (example: 0660).

    """
    shutil.copy(src, dest)
    os.chmod(dest, perm)
    os.chown(dest, owner.pw_uid, owner.pw_gid)

def makedir(dir_path, owner, perm):
    """Create a directory with given owner and permission.

    dir_path (string): the new directory to create.
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm (integer): the permission for dest (example: 0660).

    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    os.chmod(dir_path, perm)
    os.chown(dir_path, owner.pw_uid, owner.pw_gid)

def copytree(src_path, dest_path, owner, perm_files, perm_dirs):
    """Copy the *content* of src_path in dest_path, assigning the
    given owner and permissions.

    src_path (string): the root of the subtree to copy.
    dest_path (string): the destination path.
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm_files (integer): the permission for copied not-directories.
    perm_dirs (integer): the permission for copied directories.

    """
    for path in glob(os.path.join(src_path, "*")):
        sub_dest = os.path.join(dest_path, os.path.basename(path))
        if os.path.isdir(path):
            makedir(sub_dest, owner, perm_dirs)
            copytree(path, sub_dest, owner, perm_files, perm_dirs)
        elif os.path.isfile(path):
            copyfile(path, sub_dest, owner, perm_files)
        else:
            print "Error: unexpected filetype for file %s. Not copied" % path

if "build" in sys.argv:
    print "compiling mo-box..."
    os.chdir("box")
    os.system(os.path.join(".", "compile.sh"))
    os.chdir("..")

    print "compiling localization files:"
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print "  %s" % country_code
        path = os.path.join("cms", "server", "mo", country_code, "LC_MESSAGES")
        os.makedirs(path)
        os.system("msgfmt %s -o %s" % (locale, os.path.join(path, "cms.mo")))

    print "compiling client code for ranking:"
    os.chdir(os.path.join("cmsranking", "client"))
    os.system("pyjsbuild -o ../static/ Ranking")
    os.chdir(os.path.join("..", ".."))

    print "done."

if "install" in sys.argv:
    # Two kind of files: owned by root with umask 022, or owned by
    # cmsuser with umask 007. The latter because we do not want
    # regular users to sniff around our contests' data. Note that
    # umask is not enough if we copy files (permissions could be less
    # open in repository), so sometimes we do also a chmod.

    print "creating user and group cmsuser."
    os.system("useradd cmsuser -c 'CMS default user' -M -r -s /bin/false -U")
    cmsuser = pwd.getpwnam("cmsuser")
    root = pwd.getpwnam("root")

    print "copying mo-box to /usr/local/bin/."
    copyfile(os.path.join(".", "box", "mo-box"),
             os.path.join("/", "usr", "local", "bin", "mo-box"),
             root, 0755)

    print "copying configuration to /usr/local/etc/."
    conf_file = os.path.join("/", "usr", "local", "etc", "cms.conf")
    if os.path.exists(os.path.join(".", "examples", "cms.conf")):
        copyfile(os.path.join(".", "examples", "cms.conf"), conf_file,
                 cmsuser, 0660)
    else:
        copyfile(os.path.join(".", "examples", "cms.conf.sample"),
                 os.path.join("/", "usr", "local", "etc", "cms.conf"),
                 cmsuser, 0660)

    print "copying localization files:"
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print "  %s" % country_code
        path = os.path.join("cms", "server", "mo", country_code, "LC_MESSAGES")
        dest_path = os.path.join("/", "usr", "local", "share", "locale",
                                 country_code, "LC_MESSAGES")
        makedir(dest_path, root, 0755)
        copyfile(os.path.join(path, "cms.mo"),
                 os.path.join(dest_path, "cms.mo"),
                 root, 0644)

    print "creating directories."
    dirs = [os.path.join("/", "var", "local", "log"),
            os.path.join("/", "var", "local", "cache"),
            os.path.join("/", "var", "local", "lib"),
            os.path.join("/", "usr", "local", "share")]
    for d in dirs:
        makedir(d, root, 0755)
        d = os.path.join(d, "cms")
        makedir(d, cmsuser, 0770)

    print "copying static file for ranking."
    try:
        shutil.rmtree(os.path.join("/", "usr", "local", "share",
                                   "cms", "ranking"))
    except OSError:
        pass
    makedir(os.path.join("/", "usr", "local", "share",
                         "cms", "ranking"), cmsuser, 0770)
    copytree(os.path.join("cmsranking", "static"),
             os.path.join("/", "usr", "local", "share",
                          "cms", "ranking"),
             cmsuser, 0660, 0770)

    print "done."

