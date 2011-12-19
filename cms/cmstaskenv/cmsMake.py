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
import copy
import functools

from cms.util.Utils import get_compilation_command

SOL_DIRNAME = 'sol'
SOL_EXTS = ['.cpp', '.c', '.pas']
CHECK_DIRNAME = 'cor'
CHECK_EXTS = SOL_EXTS
TEXT_DIRNAME = 'testo'
TEXT_XML = 'testo.xml'
TEXT_TEX = 'testo.tex'
TEXT_PDF = 'testo.pdf'
TEXT_AUX = 'testo.aux'
TEXT_LOG = 'testo.log'
TEXT_HTML = 'testo.html'

DATA_DIRS = [os.path.join('.', 'data'), os.path.join('/', 'usr', 'local', 'share', 'cms', 'cmsMake')]

def detect_data_dir():
    for dir in DATA_DIRS:
        if os.path.exists(dir):
            return os.path.abspath(dir)

DATA_DIR = detect_data_dir()

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

def call(base_dir, args, stdin=None, stdout=None, stderr=None, env=None):
    print >> sys.stderr, "> Executing command %s in dir %s" % (" ".join(args), base_dir)
    if env is None:
        env = {}
    env2 = copy.copy(os.environ)
    env2.update(env)
    return subprocess.call(args, stdin=stdin, stdout=stdout, stderr=stderr, cwd=base_dir, env=env2)

def build_sols_list(base_dir):
    sol_dir = os.path.join(base_dir, SOL_DIRNAME)
    entries = map(lambda x: os.path.join(SOL_DIRNAME, x), os.listdir(sol_dir))
    sources = filter(lambda x: endswith2(x, SOL_EXTS), entries)

    actions = []
    for src in sources:
        exe, lang = basename2(src, SOL_EXTS)
        # Delete the dot
        lang = lang[1:]
        def compile_src(src, exe):
            call(base_dir, get_compilation_command(lang, [src], exe))
        actions.append(([src], [exe], functools.partial(compile_src, src, exe), "compilation"))

    return actions

def build_checker_list(base_dir):
    check_dir = os.path.join(base_dir, CHECK_DIRNAME)
    actions = []

    if os.path.exists(check_dir):
        entries = map(lambda x: os.path.join(CHECK_DIRNAME, x), os.listdir(check_dir))
        sources = filter(lambda x: endswith2(x, SOL_EXTS), entries)
        for src in sources:
            exe, lang = basename2(src, CHECK_EXTS)
            # Delete the dot
            lang = lang[1:]
            def compile_check(src, exe):
                call(base_dir, get_compilation_command(lang, [src], exe))
            actions.append(([src], [exe], functools.partial(compile_check, src, exe), "compilation"))

    return actions

def build_text_list(base_dir):
    text_xml = os.path.join(TEXT_DIRNAME, TEXT_XML)
    text_tex = os.path.join(TEXT_DIRNAME, TEXT_TEX)
    text_pdf = os.path.join(TEXT_DIRNAME, TEXT_PDF)
    text_aux = os.path.join(TEXT_DIRNAME, TEXT_AUX)
    text_log = os.path.join(TEXT_DIRNAME, TEXT_LOG)
    text_html = os.path.join(TEXT_DIRNAME, TEXT_HTML)

    def make_html():
        with open(os.path.join(base_dir, text_html), 'w') as fout:
            call(base_dir,
                 ['xsltproc', os.path.join(DATA_DIR, 'problem_layout.xslt'), text_xml],
                 stdout=fout)

    def make_tex():
        with open(os.path.join(base_dir, text_tex), 'w') as fout:
            call(base_dir,
                 ['xsltproc', os.path.join(DATA_DIR, 'problem_layout_tex.xslt'), text_xml],
                 stdout=fout)

    def make_pdf():
        call(base_dir,
             ['pdflatex', '-output-directory', TEXT_DIRNAME, '-interaction', 'batchmode', text_tex],
             env={'TEXINPUTS': '.:%s:%s/file:' % (TEXT_DIRNAME, TEXT_DIRNAME)})

    actions = []
    actions.append(([text_xml], [text_html], make_html, 'compile to HTML'))
    actions.append(([text_xml], [text_tex], make_tex, 'compile to LaTeX'))
    actions.append(([text_tex], [text_pdf, text_aux, text_log], make_pdf, 'compile to PDF'))
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
    actions += build_checker_list(base_dir)
    actions += build_text_list(base_dir)
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
    src_list = set()
    for action in actions:
        for exe in action[1]:
            if exe in exec_tree:
                raise Exception("Targets not unique")
            exec_tree[exe] = (action[0], action[2])
            generated_list.append(exe)
        for src in action[0]:
            src_list.add(src)
    for src in src_list:
        if src not in exec_tree:
            exec_tree[src] = ([], noop)
    return exec_tree, generated_list

def execute_target(base_dir, exec_tree, target, already_executed=None, stack=None):
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
        execute_target(base_dir, exec_tree, dep, already_executed, stack)
    stack.remove(target)

    # Check if the action really needs to be done (i.e., there is one
    # dependency more recent than the generated file)
    dep_times = max([0] + map(lambda dep: os.stat(os.path.join(base_dir, dep)).st_mtime, deps))
    try:
        gen_time = os.stat(os.path.join(base_dir, target)).st_mtime
    except OSError:
        gen_time = 0
    if gen_time >= dep_times:
        return

    # At last: actually make the so long desired action :-)
    action()

def execute_multiple_targets(base_dir, exec_tree, targets):
    already_executed = set()
    for target in targets:
        execute_target(base_dir, exec_tree, target, already_executed)

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
    parser.add_option("-a", "--all",
                      help="make all targets",
                      dest="all", action="store_true", default=False)

    options, args = parser.parse_args()

    base_dir = options.base_dir
    if base_dir is None:
        base_dir = os.getcwd()
    actions = build_action_list(base_dir)
    exec_tree, generated_list = build_execution_tree(actions)

    if [len(args) > 0, options.list, options.clean, options.all].count(True) > 1:
        parser.error("Too many commands")

    if options.list:
        print "Available operations:"
        for entry in actions:
            print "  %s -> %s (%s) %s" % (", ".join(entry[0]), ", ".join(entry[1]), entry[3], repr(entry[2]))

    elif options.clean:
        print "Cleaning"
        clean(base_dir, generated_list)

    elif options.all:
        print "Making all targets"
        execute_multiple_targets(base_dir, exec_tree, generated_list)

    else:
        execute_multiple_targets(base_dir, exec_tree, args)

if __name__ == '__main__':
    main()
