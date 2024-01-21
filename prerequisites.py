#!/usr/bin/env python3

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

import argparse
import grp
import os
import pwd
import shutil
import subprocess
import sys
from glob import glob


# Root directories for the /usr and /var trees.
USR_ROOT = os.path.join("/", "usr", "local")
VAR_ROOT = os.path.join("/", "var", "local")

# Do not prompt the user for interactive yes-or-no confirmations:
# always assume yes! This is useful for programmatic use.
ALWAYS_YES = False
# Allow to do operations that should normally be performed as an
# unprivileged user (e.g., building) as root.
AS_ROOT = False
# Do not even try to install configuration files (i.e., copying the
# samples) when installing.
NO_CONF = False
# The user and group that CMS will be run as: will be created and will
# receive the correct permissions to access isolate, the configuration
# file and the system directories.
CMSUSER = "cmsuser"


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
    return ALWAYS_YES or input(message) in ["Y", "y"]


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
    if AS_ROOT:
        return

    if os.geteuid() == 0:
        print("[Error] You must *not* be root to do this, try avoiding 'sudo'")
        exit(1)


def get_real_user():
    """Get the real username (the one who called sudo/su).

    In the case of a user *actually being root* we return an error. If the
    --as-root flag is set, this function returns "root".

    """
    if AS_ROOT:
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


def build_isolate():
    """This function compiles the isolate sandbox.

    """
    assert_not_root()

    print("===== Compiling isolate")
    # We make only the executable isolate, otherwise the tool a2x
    # is needed and we have to add more compilation dependencies.
    subprocess.check_call(["make", "-C", "isolate", "isolate"])


def install_isolate():
    """This function installs the isolate sandbox.

    """
    assert_root()
    root = pwd.getpwnam("root")
    try:
        cmsuser_grp = grp.getgrgid(pwd.getpwnam(CMSUSER).pw_gid)
    except:
        print("[Error] The user %s doesn't exist yet" % CMSUSER)
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

def install_isolate_conf():
    """This function installs the configuration files for isolate

    """
    assert_root()
    root = pwd.getpwnam("root")
    try:
        cmsuser_grp = grp.getgrnam(CMSUSER)
    except:
        print("[Error] The user %s doesn't exist yet" % CMSUSER)
        print("[Error] You need to run the install command at least once")
        exit(1)

    print("===== Copying isolate config to /usr/local/etc/")
    makedir(os.path.join(USR_ROOT, "etc"), root, 0o755)
    copyfile(os.path.join(".", "isolate", "default.cf"),
             os.path.join(USR_ROOT, "etc", "isolate"),
             root, 0o640, group=cmsuser_grp)


def build():
    """This function builds all the prerequisites by calling:
    - build_isolate

    """
    build_isolate()


def install_conf():
    """Install configuration files"""
    assert_root()

    print("===== Copying configuration to /usr/local/etc/")
    root = pwd.getpwnam("root")
    cmsuser = pwd.getpwnam(CMSUSER)
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


def install():
    """This function prepares all that's needed to run CMS:
    - creation of cmsuser user
    - compilation and installation of isolate
    - installation of configuration files
    and so on.

    """
    assert_root()

    # Get real user to run non-sudo commands
    real_user = get_real_user()

    try:
        cmsuser_pw = pwd.getpwnam(CMSUSER)
    except KeyError:
        print("===== Creating user %s" % CMSUSER)
        subprocess.check_call(["useradd", CMSUSER, "--system",
                               "--comment", "CMS default user",
                               "--shell", "/bin/false", "-U"])
        cmsuser_pw = pwd.getpwnam(CMSUSER)
    cmsuser_gr = grp.getgrgid(cmsuser_pw.pw_gid)

    root_pw = pwd.getpwnam("root")

    if real_user == "root":
        # Run build() command as root
        build()
    else:
        # Run build() command as not root
        subprocess.check_call(["sudo", "-E", "-u", real_user,
                               sys.executable, sys.argv[0], "build"])

    install_isolate()

    # We set permissions for each manually installed files, so we want
    # max liberty to change them.
    old_umask = os.umask(0o000)

    if not NO_CONF:
        install_isolate_conf()
        install_conf()

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
        makedir(_dir, root_pw, 0o755)
        _dir = os.path.join(_dir, "cms")
        makedir(_dir, cmsuser_pw, 0o770)
    extra_dirs = [os.path.join(VAR_ROOT, "cache", "cms", "fs-cache-shared")]
    for _dir in extra_dirs:
        makedir(_dir, cmsuser_pw, 0o770)

    print("===== Copying Polygon testlib")
    path = os.path.join("cmscontrib", "loaders", "polygon", "testlib.h")
    dest_path = os.path.join(USR_ROOT, "include", "cms", "testlib.h")
    copyfile(path, dest_path, root_pw, 0o644)

    os.umask(old_umask)

    if real_user != "root":
        gr_name = cmsuser_gr.gr_name
        print("===== Adding yourself to the %s group" % gr_name)
        if ask("Type Y if you want me to automatically add "
               "\"%s\" to the %s group: " % (real_user, gr_name)):
            subprocess.check_call(["usermod", "-a", "-G", gr_name, real_user])
            print("""
###########################################################################
###                                                                     ###
###    Remember that you must now logout in order to make the change    ###
###    effective ("the change" is: being in the %s group).         ###
###                                                                     ###
###########################################################################
            """ % gr_name)
        else:
            print("""
###########################################################################
###                                                                     ###
###    Remember that you must be in the %s group to use CMS:       ###
###                                                                     ###
###       $ sudo usermod -a -G %s <your user>                      ###
###                                                                     ###
###    You must also logout to make the change effective.               ###
###                                                                     ###
###########################################################################
            """ % (gr_name, gr_name))


def uninstall():
    """This function deletes all that was installed by the install()
    function:
    - deletion of the cmsuser user
    - deletion of isolate
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

    print("===== Deleting empty directories")
    extra_dirs = [os.path.join(VAR_ROOT, "cache", "cms", "fs-cache-shared")]
    for _dir in extra_dirs:
        if os.listdir(_dir) == []:
            try_delete(_dir)
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

    print("===== Deleting user and group %s" % CMSUSER)
    try:
        # Just to check whether it exists.
        pwd.getpwnam(CMSUSER)
    except KeyError:
        pass
    else:
        if ask("Do you want to delete user %s? [y/N] " % CMSUSER):
            subprocess.check_call(["userdel", CMSUSER])
    try:
        # Just to check whether it exists. If CMSUSER had a different primary
        # group, we'll do nothing here.
        grp.getgrnam(CMSUSER)
    except KeyError:
        pass
    else:
        if ask("Do you want to delete group %s? [y/N] " % CMSUSER):
            subprocess.check_call(["groupdel", CMSUSER])
        elif ask("Do you want to remove all users from group %s? [y/N] "
                 % CMSUSER):
            for user in grp.getgrnam(CMSUSER).gr_mem:
                subprocess.check_call(["gpasswd", "-d", user, CMSUSER])

    print("===== Done")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script used to manage prerequisites for CMS')

    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Don't ask questions interactively")
    parser.add_argument(
        "--no-conf", action="store_true",
        help="Don't install configuration files")
    parser.add_argument(
        "--as-root", action="store_true",
        help="(DON'T USE) Allow running non-root commands as root")
    parser.add_argument(
        "--cmsuser", action="store", type=str, default=CMSUSER,
        help="(DON'T USE) The user CMS will be run as"
    )

    subparsers = parser.add_subparsers(metavar="command",
                                       help="Subcommand to run")
    subparsers.add_parser("build_isolate",
                          help="Build \"isolate\" sandbox") \
        .set_defaults(func=build_isolate)
    subparsers.add_parser("build",
                          help="Build everything") \
        .set_defaults(func=build)
    subparsers.add_parser("install_isolate",
                          help="Install \"isolate\" sandbox (requires root)") \
        .set_defaults(func=install_isolate)
    subparsers.add_parser("install",
                          help="Install everything (requires root)") \
        .set_defaults(func=install)
    subparsers.add_parser("uninstall",
                          help="Uninstall everything (requires root)") \
        .set_defaults(func=uninstall)

    args = parser.parse_args()

    ALWAYS_YES = args.yes
    NO_CONF = args.no_conf
    AS_ROOT = args.as_root
    CMSUSER = args.cmsuser

    if not hasattr(args, "func"):
        parser.error("Please specify a command to run. "
                     "Use \"--help\" for more information.")

    args.func()
