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


import optparse
import os
import sys
import subprocess

SOL_DIRNAME = 'sol'
SOL_EXTS = ['.cpp', '.c', '.pas']

def endswith2(str, suffixes):
    """True if str ends with one of the given suffixes.

    """
    return any(map(lambda x: str.endswith(x), suffixes))

def basename2(str, suffixes):
    """If str ends with one of the specified suffixes, returns its
    basename (i.e., itself after removing the suffix) and the suffix
    packed in a tuple. Otherwise returns None.

    """
    try:
        idx = map(lambda x: str.endswith(x), suffixes).index(True)
    except ValueError:
        return None
    return (str[:-len(suffixes[idx])], str[-len(suffixes[idx]):])

# Copied from CMS; probably we should unify them
def get_compilation_command(language, source_filenames, executable_filename):
    """Returns the compilation command for the specified language,
    source filenames and executable filename. The command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    language (string): one of the recognized languages.
    source_filenames (list): a list of the string that are the
                             filenames of the source files to compile.
    executable_filename (string): the output file.
    return (list): a list of string to be passed to subprocess.

    """
    # For compiling in 32-bit mode under 64-bit OS: add "-march=i686",
    # "-m32" for gcc/g++. Don't know about Pascal. Anyway, this will
    # require some better support from the evaluation environment
    # (particularly the sandbox, which has to be compiled in a
    # different way depending on whether it will execute 32- or 64-bit
    # programs).
    if language == "c":
        command = ["/usr/bin/gcc", "-DEVAL", "-static", "-O2", "-lm", "-o", executable_filename]
    elif language == "cpp":
        command = ["/usr/bin/g++", "-DEVAL", "-static", "-O2", "-o", executable_filename]
    elif language == "pas":
        command = ["/usr/bin/fpc", "-dEVAL", "-XS", "-O2", "-o%s" % (executable_filename)]
    return command + source_filenames

def call(base_dir, args, stdin=None, stdout=None, stderr=None):
    print >> sys.stderr, "> Executing command %s in dir %s" % (" ".join(args), base_dir)
    return subprocess.call(args, stdin=stdin, stdout=stdout, stderr=stderr, cwd=base_dir)

def build_sols_list(base_dir):
    sol_dir = os.path.join(base_dir, SOL_DIRNAME)
    entries = map(lambda x: os.path.join(SOL_DIRNAME, x), os.listdir(sol_dir))
    sources = filter(lambda x: endswith2(x, SOL_EXTS), entries)

    actions = []
    for src in sources:
        exe, lang = basename2(src, SOL_EXTS)
        # Delete the dot
        lang = lang[1:]
        def compile():
            call(base_dir, get_compilation_command(lang, [src], exe))
        actions.append(([src], [exe], compile, "compilation"))

    return actions

def build_action_list(base_dir):
    # Build a list of actions that cmsMake is able to do here. Each
    # action is described by a tuple (infiles, outfiles, callable,
    # description) where:
    #
    # 1) infiles is a list of files this action depends on;
    #
    # 2) outfiles is a list of files this action produces; it is
    # intended that this action can be skipped if any of the outfiles
    # is newer than any of the infiles; moreover, the outfiles get
    # deleted when the action is cleaned;
    #
    # 3) callable is a callable Python object that, when called,
    # performs the action;
    #
    # 4) description is a human-readable description of what this
    # action does.
    actions = []
    actions += build_sols_list(base_dir)
    return actions

def clean(base_dir, generated_list):
    for f in generated_list:
        try:
            os.remove(os.path.join(base_dir, f))
        except OSError:
            pass

def build_execution_tree(actions):
    def noop():
        pass
    exec_tree = {}
    generated_list = []
    for action in actions:
        for exe in action[1]:
            if exe in exec_tree:
                raise Exception("Targets not unique")
            exec_tree[exe] = (action[0], action[2])
            generated_list.append(exe)
        for src in action[0]:
            if src in exec_tree:
                raise Exception("Targets not unique")
            exec_tree[src] = ([], noop)
    return exec_tree, generated_list

def execute_target(exec_tree, target, already_executed=None, stack=None):
    # Initialization
    if already_executed is None:
        already_executed = set()
    if stack is None:
        stack = set()

    # Get target information
    deps = exec_tree[target][0]
    action = exec_tree[target][1]

    # If this target is already in the stack, we have a circular
    # dependency
    if target in stack:
        raise Exception("Circular dependency detected")

    # If the target was already made in another subtree, we have
    # nothing to do
    if target in already_executed:
        return

    # Otherwise, do a step of the DFS to make dependencies
    already_executed.add(target)
    stack.add(target)
    for dep in deps:
        execute_target(exec_tree, dep, already_executed, stack)
    stack.remove(target)

    # At last: actually make the so long desired action :-)
    action()

def execute_multiple_targets(exec_tree, targets):
    already_executed = set()
    for target in targets:
        execute_target(exec_tree, target, already_executed)

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] [target]")
    parser.add_option("-D", "--base-dir",
                      help="base directory for problem to make (CWD by default)",
                      dest="base_dir", action="store", default=None)
    parser.add_option("-l", "--list",
                      help="list actions that cmsMake is aware of",
                      dest="list", action="store_true", default=False)
    parser.add_option("-c", "--clean",
                      help="clean all generated files",
                      dest="clean", action="store_true", default=False)

    options, args = parser.parse_args()

    base_dir = options.base_dir
    if base_dir is None:
        base_dir = os.getcwd()
    actions = build_action_list(base_dir)
    exec_tree, generated_list = build_execution_tree(actions)

    if [len(args) > 0, options.list, options.clean].count(True) > 1:
        parser.error("Too many commands")

    if options.list:
        print "Available operations:"
        for entry in actions:
            print "  %s -> %s (%s)" % (", ".join(entry[0]), ", ".join(entry[1]), entry[3])

    elif options.clean:
        print "Cleaning"
        clean(base_dir, generated_list)

    else:
        execute_multiple_targets(exec_tree, args)

if __name__ == '__main__':
    main()
