#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import sys
import os
import shutil
import re
import pwd

from glob import glob
from setuptools import setup

from distutils import cmd
from distutils.command.build import build as _build
from distutils.command.install import install as _install
from distutils.command.clean import clean as _clean


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
            print "Error: unexpected filetype for file %s. Not copied" % path



class build_mobox(cmd.Command):
    description = 'Compile mo-box'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print "compiling mo-box..."
        os.chdir("box")
        os.system(os.path.join(".", "compile.sh"))
        os.chdir("..")


class install_mobox(cmd.Command):
    description = 'Install mo-box files'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # We set permissions for each manually installed files, so we want
        # max liberty to change them.
        old_umask = os.umask(0000)

        root = pwd.getpwnam("root")

        print "copying mo-box to /usr/local/bin/."
        makedir(os.path.join("/", "usr", "local", "bin"), root, 0755)
        copyfile(os.path.join(".", "box", "mo-box"),
                 os.path.join("/", "usr", "local", "bin", "mo-box"),
                 root, 0755)

        os.umask(old_umask)


class clean_mobox(cmd.Command):
    description = 'Clean mo-box files'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print "cleaning mo-box..."
        os.chdir("box")
        os.remove(os.path.join(".", "autoconf.h"))
        os.remove(os.path.join(".", "syscall-table.h"))
        os.remove(os.path.join(".", "mo-box"))
        os.remove(os.path.join(".", "mo-box32"))
        os.chdir("..")


class build_trans(cmd.Command):
    description = 'Compile translations'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print "compiling localization files:"
        for locale in glob(os.path.join("cms", "server", "po", "*.po")):
            country_code = re.search("/([^/]*)\.po", locale).groups()[0]
            print "  %s" % country_code
            path = os.path.join("cms", "server", "mo", country_code,
                                "LC_MESSAGES")
            makedir(path)
            os.system("msgfmt %s -o %s" % (locale, os.path.join(path, "cms.mo")))


class install_trans(cmd.Command):
    description = 'Install translations'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # We set permissions for each manually installed files, so we want
        # max liberty to change them.
        old_umask = os.umask(0000)

        root = pwd.getpwnam("root")

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

        os.umask(old_umask)


class clean_trans(cmd.Command):
    description = 'Clean translations'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print "cleaning localization files..."
        for locale in glob(os.path.join("cms", "server", "po", "*.po")):
            country_code = re.search("/([^/]*)\.po", locale).groups()[0]
            path = os.path.join("cms", "server", "mo", country_code,
                                "LC_MESSAGES")
            os.remove(os.path.join(path, "cms.mo"))
            os.removedirs(path)


class build(_build):
    sub_commands = [('build_mobox', None), ('build_trans', None)] + _build.sub_commands

    def run(self):
        # Run all sub-commands (at least those that need to be run)
        _build.run(self)
        print "done."


class install(_install):
    sub_commands = [('install_mobox', None), ('install_trans', None)] + _install.sub_commands

    def run(self):
        # We set permissions for each manually installed files, so we want
        # max liberty to change them.
        old_umask = os.umask(0000)

        print "creating user and group cmsuser."
        os.system("useradd cmsuser -c 'CMS default user' -M -r -s /bin/false -U")
        cmsuser = pwd.getpwnam("cmsuser")
        root = pwd.getpwnam("root")

        print "copying configuration to /usr/local/etc/."
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

        print "creating directories."
        dirs = [os.path.join("/", "var", "local", "log"),
                os.path.join("/", "var", "local", "cache"),
                os.path.join("/", "var", "local", "lib"),
                os.path.join("/", "usr", "local", "share")]
        for _dir in dirs:
            # Skip if destination is a symlink
            if os.path.islink(os.path.join(_dir, "cms")):
                continue
            makedir(_dir, root, 0755)
            _dir = os.path.join(_dir, "cms")
            makedir(_dir, cmsuser, 0770)

        os.umask(old_umask)

        # Run all sub-commands (at least those that need to be run)
        for cmd_name in self.get_sub_commands():
            self.run_command(cmd_name)
        _install.run(self)
        print "done."


class clean(_clean):
    sub_commands = [('clean_mobox', None), ('clean_trans', None)] + _clean.sub_commands

    def run(self):
        # Run all sub-commands (at least those that need to be run)
        for cmd_name in self.get_sub_commands():
            self.run_command(cmd_name)
        _clean.run(self)
        print "done."


old_umask = os.umask(0022)

package_data = {
    "cms.async": [
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
      version="1.0.0pre",
      author="Matteo Boscariol, Stefano Maggiolo, "
             "Giovanni Mascellani, Luca Wehrstedt",
      author_email="contestms@freelists.org",
      url="https://github.com/cms-dev/cms",
      download_url="https://github.com/cms-dev/cms/archive/master.tar.gz",
      description="A contest management system and grader "
                  "for IOI-like programming competitions",
      cmdclass={"build_mobox": build_mobox,
                "install_mobox": install_mobox,
                "clean_mobox": clean_mobox,
                "build_trans": build_trans,
                "install_trans": install_trans,
                "clean_trans": clean_trans,
                "build": build,
                "install": install,
                "clean": clean},
      packages=["cms",
                "cms.db",
                "cms.server",
                "cms.service",
                "cms.async",
                "cms.grading",
                "cms.grading.scoretypes",
                "cms.grading.tasktypes",
                "cmscommon",
                "cmsranking",
                "cmscontrib",
                "cmstaskenv",
                "cmstestsuite",
                "cmstestsuite.web",
                "cmstestsuite.tasks",
                "cmstestsuite.tasks.batch_stdio",
                "cmstestsuite.tasks.batch_fileio"],
      package_data=package_data,
      entry_points={
          "console_scripts": [
              "cmsLogService=cms.service.LogService:main",
              "cmsScoringService=cms.service.ScoringService:main",
              "cmsEvaluationService=cms.service.EvaluationService:main",
              "cmsWorker=cms.service.Worker:main",
              "cmsResourceService=cms.service.ResourceService:main",
              "cmsChecker=cms.service.Checker:main",
              "cmsContestWebServer=cms.server.ContestWebServer:main",
              "cmsAdminWebServer=cms.server.AdminWebServer:main",

              "cmsRankingWebServer=cmsranking.RankingWebServer:main",

              "cmsRunTests=cmstestsuite.RunTests:main",
              "cmsReplayContest=cmstestsuite.ReplayContest:main",
              "cmsAdaptContest=cmstestsuite.AdaptContest:main",
              "cmsTestFileCacher=cmstestsuite.TestFileCacher:main",

              "cmsAddUser=cmscontrib.AddUser:main",
              "cmsComputeComplexity=cmscontrib.ComputeComplexity:main",
              "cmsYamlImporter=cmscontrib.YamlImporter:main",
              "cmsYamlReimporter=cmscontrib.YamlReimporter:main",
              "cmsSpoolExporter=cmscontrib.SpoolExporter:main",
              "cmsContestExporter=cmscontrib.ContestExporter:main",
              "cmsContestImporter=cmscontrib.ContestImporter:main",

              "cmsMake=cmstaskenv.cmsMake:main",
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

os.umask(old_umask)

