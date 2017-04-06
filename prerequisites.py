#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Build and installation routines needed to run CMS (user creation,
configuration, and so on).

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
import shutil
import re
import pwd
import grp
import argparse

from glob import glob


# Root directories for the /usr and /var trees.
USR_ROOT = os.path.join("/", "usr", "local")
VAR_ROOT = os.path.join("/", "var", "local")


def copyfile(src, dest, owner, perm, group=None):
    """Copy the file src to dest, and assign owner and permissions.

    src (string): the complete path of the source file.
    dest (string): the complete path of the destination file (i.e.,
                   not the destination directory).
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm (integer): the permission for dest (example: 0o660).
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


def try_delete(path):
    """Try to delete a given path, failing gracefully.

    """
    if os.path.isdir(path):
        try:
            os.rmdir(path)
        except OSError:
            print("[Warning] Skipping because directory is not empty: ", path)
    else:
        try:
            os.remove(path)
        except OSError:
            print("[Warning] File not found: ", path)


def makedir(dir_path, owner=None, perm=None):
    """Create a directory with given owner and permission.

    dir_path (string): the new directory to create.
    owner (as given by pwd.getpwnam): the owner we want for dest.
    perm (integer): the permission for dest (example: 0o660).

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


def ask(message):
    """Ask the user and return True if and only if one of the following holds:
    - the users responds "Y" or "y"
    - the "-y" flag was set as a CLI argument

    """
    return "-y" in sys.argv or raw_input(message) in ["Y", "y"]


def assert_root():
    """Check if the current user is root, and exit with an error message if
    needed.

    """
    if os.geteuid() != 0:
        print("[Error] You must be root to do this, try using 'sudo'")
        exit(1)


def assert_not_root():
    """Check if the current user is *not* root, and exit with an error message
    if needed. If the --as-root flag is set, this function does nothing.

    """
    if "--as-root" in sys.argv:
        return

    if os.geteuid() == 0:
        print("[Error] You must *not* be root to do this, try avoiding 'sudo'")
        exit(1)


def get_real_user():
    """Get the real username (the one who called sudo/su).

    In the case of a user *actually being root* we return an error. If the
    --as-root flag is set, this function returns "root".

    """
    if "--as-root" in sys.argv:
        return "root"

    name = os.getenv("SUDO_USER")
    if name is None:
        name = os.popen("logname").read().strip()

    if name == "root":
        print("[Error] You are logged in as root")
        print(
            "[Error] Log in as a normal user instead, and use 'sudo' or 'su'")
        exit(1)

    return name


class CLI(object):

    def __init__(self):
        parser = argparse.ArgumentParser(
            description='Script used to manage prerequisites for CMS',
            usage="""%s <command> [<args>] [-y] [--as-root]

Available commands:
   build_l10n        Build localization files
   build_isolate     Build "isolate" sandbox
   build             Build everything
   install_isolate   Install "isolate" sandbox (requires root)
   install           Install everything (requires root)
   uninstall         Uninstall everything (requires root)

Options:
   -y                Don't ask questions interactively (assume "y")
   --no-conf         Don't install configuration files
   --as-root         (DON'T USE) Allow running non-root commands as root
""" % (sys.argv[0]))

        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    def build_l10n(self):
        """This function compiles localization files.

        """
        assert_not_root()

        print("===== Compiling localization files")
        for locale in glob(os.path.join("cms", "locale", "*")):
            if os.path.isdir(locale) \
                    and not os.path.basename(locale).startswith("_"):
                country_code = os.path.basename(locale)
                print("  %s" % country_code)
                path = os.path.join(
                    "cms", "locale", country_code, "LC_MESSAGES")
                locale = os.path.join(locale, "LC_MESSAGES", "cms.po")
                os.system(
                    "msgfmt %s -o %s" % (locale, os.path.join(path, "cms.mo")))

    def build_isolate(self):
        """This function compiles the isolate sandbox.

        """
        assert_not_root()

        print("===== Compiling isolate")
        os.chdir("isolate")
        # We make only the executable isolate, otherwise the tool a2x
        # is needed and we have to add more compilation dependencies.
        os.system("make isolate")
        os.chdir("..")

    def install_isolate(self):
        """This function installs the isolate sandbox.

        """
        assert_root()
        root = pwd.getpwnam("root")
        try:
            cmsuser_grp = grp.getgrnam("cmsuser")
        except:
            print("[Error] The cmsuser doesn't exist yet")
            print("[Error] You need to run the install command at least once")
            exit(1)

        # Check if build_isolate() has been called
        if not os.path.exists(os.path.join("isolate", "isolate")):
            print("[Error] You must run the build_isolate command first")
            exit(1)

        print("===== Copying isolate to /usr/local/bin/")
        makedir(os.path.join(USR_ROOT, "bin"), root, 0o755)
        copyfile(os.path.join(".", "isolate", "isolate"),
                 os.path.join(USR_ROOT, "bin", "isolate"),
                 root, 0o4750, group=cmsuser_grp)

        print("===== Copying isolate config to /usr/local/etc/")
        makedir(os.path.join(USR_ROOT, "etc"), root, 0o755)
        copyfile(os.path.join(".", "isolate", "default.cf"),
                 os.path.join(USR_ROOT, "etc", "isolate"),
                 root, 0o640, group=cmsuser_grp)

    def build(self):
        """This function builds all the prerequisites by calling:
        - build_l10n
        - build_isolate

        """
        self.build_l10n()
        self.build_isolate()

    def install_conf(self):
        """Install configuration files"""
        assert_root()

        print("===== Copying configuration to /usr/local/etc/")
        root = pwd.getpwnam("root")
        cmsuser = pwd.getpwnam("cmsuser")
        makedir(os.path.join(USR_ROOT, "etc"), root, 0o755)
        for conf_file_name in ["cms.conf", "cms.ranking.conf"]:
            conf_file = os.path.join(USR_ROOT, "etc", conf_file_name)
            # Skip if destination is a symlink
            if os.path.islink(conf_file):
                continue
            # If the config exists, check if the user wants to overwrite it
            if os.path.exists(conf_file):
                if not ask("The %s file is already installed, "
                           "type Y to overwrite it: " % (conf_file_name)):
                    continue
            if os.path.exists(os.path.join(".", "config", conf_file_name)):
                copyfile(os.path.join(".", "config", conf_file_name),
                         conf_file, cmsuser, 0o660)
            else:
                conf_file_name = "%s.sample" % conf_file_name
                copyfile(os.path.join(".", "config", conf_file_name),
                         conf_file, cmsuser, 0o660)

    def install(self):
        """This function prepares all that's needed to run CMS:
        - creation of cmsuser user
        - compilation and installation of isolate
        - compilation and installation of localization files
        - installation of configuration files
        and so on.

        """
        assert_root()

        # Get real user to run non-sudo commands
        real_user = get_real_user()

        print("===== Creating user and group cmsuser")
        os.system(
            "useradd cmsuser -c 'CMS default user' -M -r -s /bin/false -U")
        cmsuser = pwd.getpwnam("cmsuser")
        root = pwd.getpwnam("root")

        if real_user == "root":
            # Run build() command as root
            self.build()
        else:
            # Run build() command as not root
            if os.system("sudo -u %s %s build" % (real_user, sys.argv[0])):
                exit(1)

        self.install_isolate()

        # We set permissions for each manually installed files, so we want
        # max liberty to change them.
        old_umask = os.umask(0o000)

        if "--no-conf" not in sys.argv:
            self.install_conf()

        print("===== Creating directories")
        dirs = [os.path.join(VAR_ROOT, "log"),
                os.path.join(VAR_ROOT, "cache"),
                os.path.join(VAR_ROOT, "lib"),
                os.path.join(VAR_ROOT, "run"),
                os.path.join(USR_ROOT, "include"),
                os.path.join(USR_ROOT, "share")]
        for _dir in dirs:
            # Skip if destination is a symlink
            if os.path.islink(os.path.join(_dir, "cms")):
                continue
            makedir(_dir, root, 0o755)
            _dir = os.path.join(_dir, "cms")
            makedir(_dir, cmsuser, 0o770)

        print("===== Copying Polygon testlib")
        path = os.path.join("cmscontrib", "loaders", "polygon", "testlib.h")
        dest_path = os.path.join(USR_ROOT, "include", "cms", "testlib.h")
        copyfile(path, dest_path, root, 0o644)

        os.umask(old_umask)

        if real_user != "root":
            print("===== Adding yourself to the cmsuser group")
            if ask("Type Y if you want me to automatically add "
                   "\"%s\" to the cmsuser group: " % (real_user)):
                os.system("usermod -a -G cmsuser %s" % (real_user))
                print("""
    ###########################################################################
    ###                                                                     ###
    ###    Remember that you must now logout in order to make the change    ###
    ###    effective ("the change" is: being in the cmsuser group).         ###
    ###                                                                     ###
    ###########################################################################
                """)
            else:
                print("""
    ###########################################################################
    ###                                                                     ###
    ###    Remember that you must be in the cmsuser group to use CMS:       ###
    ###                                                                     ###
    ###       $ sudo usermod -a -G cmsuser <your user>                      ###
    ###                                                                     ###
    ###    You must also logout to make the change effective.               ###
    ###                                                                     ###
    ###########################################################################
                """)

    def uninstall(self):
        """This function deletes all that was installed by the install()
        function:
        - deletion of the cmsuser user
        - deletion of isolate
        - deletion of localization files
        - deletion of configuration files
        and so on.

        """
        assert_root()

        print("===== Deleting isolate from /usr/local/bin/")
        try_delete(os.path.join(USR_ROOT, "bin", "isolate"))

        print("===== Deleting configuration to /usr/local/etc/")
        if ask("Type Y if you really want to remove configuration files: "):
            for conf_file_name in ["cms.conf", "cms.ranking.conf"]:
                try_delete(os.path.join(USR_ROOT, "etc", conf_file_name))

        print("===== Deleting localization files")
        for locale in glob(os.path.join("po", "*.po")):
            country_code = re.search(r"/([^/]*)\.po", locale).groups()[0]
            print("  %s" % country_code)
            dest_path = os.path.join(USR_ROOT, "share", "locale",
                                     country_code, "LC_MESSAGES")
            try_delete(os.path.join(dest_path, "cms.mo"))

        print("===== Deleting empty directories")
        dirs = [os.path.join(VAR_ROOT, "log"),
                os.path.join(VAR_ROOT, "cache"),
                os.path.join(VAR_ROOT, "lib"),
                os.path.join(VAR_ROOT, "run"),
                os.path.join(USR_ROOT, "include"),
                os.path.join(USR_ROOT, "share")]
        for _dir in dirs:
            if os.listdir(_dir) == []:
                try_delete(_dir)

        print("===== Deleting Polygon testlib")
        try_delete(os.path.join(USR_ROOT, "include", "cms", "testlib.h"))

        print("===== Deleting user and group cmsuser")
        try:
            for user in grp.getgrnam("cmsuser").gr_mem:
                os.system("gpasswd -d %s cmsuser" % (user))
            os.system("userdel cmsuser")
        except KeyError:
            print("[Warning] Group cmsuser not found")

        print("===== Done")


if __name__ == '__main__':
    CLI()
