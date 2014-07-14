#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""Build and installation routines for CMS.

"""

from __future__ import absolute_import
from __future__ import print_function
# setuptools doesn't seem to like this:
# from __future__ import unicode_literals

import sys
import os
import shutil
import re
import pwd
import grp

from glob import glob
from setuptools import setup


def do_setup():
    """Execute the setup thanks to setuptools.

    """
    old_umask = os.umask(0022)

    package_data = {
        "cms.io": [
            os.path.join("static", "*"),
        ],
        "cms.server": [
            os.path.join("static", "jq", "*.*"),
            os.path.join("static", "sh", "*.*"),
            os.path.join("static", "css", "*.*"),
            os.path.join("static", "js", "*.*"),
            os.path.join("static", "img", "*.*"),
            os.path.join("static", "img", "mimetypes", "*.*"),
            os.path.join("static", "*.*"),
            os.path.join("templates", "contest", "*.*"),
            os.path.join("templates", "admin", "*.*"),
            os.path.join("templates", "ranking", "*.*"),
        ],
        "cmsranking": [
            os.path.join("static", "img", "*.*"),
            os.path.join("static", "lib", "*.*"),
            os.path.join("static", "*.*"),
        ],
        "cmstestsuite": [
            os.path.join("code", "*.*"),
            os.path.join("tasks", "batch_stdio", "data", "*.*"),
            os.path.join("tasks", "batch_fileio", "data", "*.*"),
            os.path.join("tasks", "batch_fileio_managed", "code", "*"),
            os.path.join("tasks", "batch_fileio_managed", "data", "*.*"),
            os.path.join("tasks", "communication", "code", "*"),
            os.path.join("tasks", "communication", "data", "*.*"),
        ],
    }

    # Apparently, pip installs package_data with the permissions they
    # have on the source. We fix the source permissions here. (Though,
    # pip works on a copy, so no changes happen.)
    for package in package_data:
        for path in package_data[package]:
            for file_ in glob(os.path.join(package.replace(".", "/"), path)):
                os.chmod(file_, 0644)

    setup(name="cms",
          version="1.1.0",
          author="The CMS development team",
          author_email="contestms@freelists.org",
          url="https://github.com/cms-dev/cms",
          download_url="https://github.com/cms-dev/cms/archive/master.tar.gz",
          description="A contest management system and grader "
                      "for IOI-like programming competitions",
          packages=["cms",
                    "cms.db",
                    "cms.server",
                    "cms.service",
                    "cms.io",
                    "cms.grading",
                    "cms.grading.scoretypes",
                    "cms.grading.tasktypes",
                    "cmscommon",
                    "cmsranking",
                    "cmscontrib",
                    "cmscontrib.updaters",
                    "cmstaskenv",
                    "cmstestsuite",
                    "cmstestsuite.web",
                    "cmstestsuite.tasks",
                    "cmstestsuite.tasks.batch_stdio",
                    "cmstestsuite.tasks.batch_fileio",
                    "cmstestsuite.tasks.batch_fileio_managed",
                    "cmstestsuite.tasks.communication",
                    "cmscompat"],
          package_data=package_data,
          scripts=["scripts/cmsLogService",
                   "scripts/cmsScoringService",
                   "scripts/cmsEvaluationService",
                   "scripts/cmsWorker",
                   "scripts/cmsResourceService",
                   "scripts/cmsChecker",
                   "scripts/cmsContestWebServer",
                   "scripts/cmsAdminWebServer",
                   "scripts/cmsProxyService",

                   "scripts/cmsRankingWebServer",

                   "scripts/cmsInitDB",
                   "scripts/cmsDropDB"],
          entry_points={
              "console_scripts": [
                  "cmsRunTests=cmstestsuite.RunTests:main",
                  "cmsReplayContest=cmstestsuite.ReplayContest:main",
                  "cmsAdaptContest=cmstestsuite.AdaptContest:main",
                  "cmsTestFileCacher=cmstestsuite.TestFileCacher:main",

                  "cmsAddUser=cmscontrib.AddUser:main",
                  "cmsRemoveUser=cmscontrib.RemoveUser:main",
                  "cmsRemoveTask=cmscontrib.RemoveTask:main",
                  "cmsComputeComplexity=cmscontrib.ComputeComplexity:main",
                  "cmsImporter=cmscontrib.Importer:main",
                  "cmsReimporter=cmscontrib.Reimporter:main",
                  "cmsSpoolExporter=cmscontrib.SpoolExporter:main",
                  "cmsContestExporter=cmscontrib.ContestExporter:main",
                  "cmsContestImporter=cmscontrib.ContestImporter:main",
                  "cmsDumpUpdater=cmscontrib.DumpUpdater:main",
                  "cmsRWSHelper=cmscontrib.RWSHelper:main",

                  "cmsMake=cmstaskenv.cmsMake:main",

                  "cmsYamlImporter=cmscompat.YamlImporter:main",
                  "cmsYamlReimporter=cmscompat.YamlReimporter:main",
              ]
          },
          keywords="ioi programming contest grader management system",
          license="Affero General Public License v3",
          classifiers=[
              "Development Status :: 3 - Alpha",
              "Natural Language :: English",
              "Operating System :: POSIX :: Linux",
              "Programming Language :: Python :: 2",
              "License :: OSI Approved :: "
              "GNU Affero General Public License v3",
          ])
    os.umask(old_umask)


def copyfile(src, dest, owner, perm, group=None):
    """Copy the file src to dest, and assign owner and permissions.

    src (string): the complete path of the source file.
    dest (string): the complete path of the destination file (i.e.,
                   not the destination directory).
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm (integer): the permission for dest (example: 0660).
    group (as given by grp.getgrnam): the group we want for dest; if
                                      not specified, use owner's
                                      group.

    """
    shutil.copy(src, dest)
    owner_id = owner.pw_uid
    if group is not None:
        group_id = group.gr_gid
    else:
        group_id = owner.pw_gid
    os.chown(dest, owner_id, group_id)
    os.chmod(dest, perm)


def makedir(dir_path, owner=None, perm=None):
    """Create a directory with given owner and permission.

    dir_path (string): the new directory to create.
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm (integer): the permission for dest (example: 0660).

    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    if perm is not None:
        os.chmod(dir_path, perm)
    if owner is not None:
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
            print("Error: unexpected filetype for file %s. Not copied" % path)


def build():
    """This function builds the pieces of CMS that need a compilation
    and are not handled by setuptools: isolate, localization files,
    pyjamas code for the client of RWS.


    """
    print("compiling isolate...")
    os.chdir("isolate")
    os.system(os.path.join(".", "compile.sh"))
    os.chdir("..")

    print("compiling localization files:")
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print("  %s" % country_code)
        path = os.path.join("cms", "server", "mo", country_code,
                            "LC_MESSAGES")
        makedir(path)
        os.system("msgfmt %s -o %s" % (locale, os.path.join(path, "cms.mo")))

    print("done.")


def install():
    """Manual installation of files not handled by setuptools: cmsuser
    user, isolate, configuration, localization files, static files for
    RWS.

    """
    # We set permissions for each manually installed files, so we want
    # max liberty to change them.
    old_umask = os.umask(0000)

    print("creating user and group cmsuser.")
    os.system("useradd cmsuser -c 'CMS default user' -M -r -s /bin/false -U")
    cmsuser = pwd.getpwnam("cmsuser")
    root = pwd.getpwnam("root")
    cmsuser_grp = grp.getgrnam("cmsuser")

    print("copying isolate to /usr/local/bin/.")
    makedir(os.path.join("/", "usr", "local", "bin"), root, 0755)
    copyfile(os.path.join(".", "isolate", "isolate"),
             os.path.join("/", "usr", "local", "bin", "isolate"),
             root, 04750, group=cmsuser_grp)

    print("copying configuration to /usr/local/etc/.")
    makedir(os.path.join("/", "usr", "local", "etc"), root, 0755)
    for conf_file_name in ["cms.conf", "cms.ranking.conf"]:
        conf_file = os.path.join("/", "usr", "local", "etc", conf_file_name)
        # Skip if destination is a symlink
        if os.path.islink(conf_file):
            continue
        if os.path.exists(os.path.join(".", "examples", conf_file_name)):
            copyfile(os.path.join(".", "examples", conf_file_name),
                     conf_file, cmsuser, 0660)
        else:
            conf_file_name = "%s.sample" % conf_file_name
            copyfile(os.path.join(".", "examples", conf_file_name),
                     conf_file, cmsuser, 0660)

    print("copying localization files:")
    for locale in glob(os.path.join("cms", "server", "po", "*.po")):
        country_code = re.search("/([^/]*)\.po", locale).groups()[0]
        print("  %s" % country_code)
        path = os.path.join("cms", "server", "mo", country_code, "LC_MESSAGES")
        dest_path = os.path.join("/", "usr", "local", "share", "locale",
                                 country_code, "LC_MESSAGES")
        makedir(dest_path, root, 0755)
        copyfile(os.path.join(path, "cms.mo"),
                 os.path.join(dest_path, "cms.mo"),
                 root, 0644)

    print("creating directories.")
    dirs = [os.path.join("/", "var", "local", "log"),
            os.path.join("/", "var", "local", "cache"),
            os.path.join("/", "var", "local", "lib"),
            os.path.join("/", "var", "local", "run"),
            os.path.join("/", "usr", "local", "share")]
    for _dir in dirs:
        # Skip if destination is a symlink
        if os.path.islink(os.path.join(_dir, "cms")):
            continue
        makedir(_dir, root, 0755)
        _dir = os.path.join(_dir, "cms")
        makedir(_dir, cmsuser, 0770)

    os.umask(old_umask)
    print("done.")


if __name__ == "__main__":
    do_setup()
    if "build" in sys.argv:
        build()
    if "install" in sys.argv:
        install()
