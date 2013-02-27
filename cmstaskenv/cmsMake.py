#!/usr/bin/env python2
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


import optparse
import os
import sys
import subprocess
import copy
import functools
import shutil
import tempfile
import yaml

from cms.grading import get_compilation_command
from cms.grading.Sandbox import Sandbox
from cmstaskenv.Test import test_testcases

SOL_DIRNAME = 'sol'
SOL_FILENAME = 'soluzione'
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
INPUT0_TXT = 'input0.txt'
OUTPUT0_TXT = 'output0.txt'
GEN_DIRNAME = 'gen'
GEN_GEN = 'GEN'
GEN_BASENAME = 'generatore'
GEN_EXTS = ['.py', '.sh']
VALIDATOR_BASENAME = 'valida'
GRAD_BASENAME = 'grader'
INPUT_DIRNAME = 'input'
OUTPUT_DIRNAME = 'output'
RESULT_DIRNAME = 'result'

DATA_DIRS = [os.path.join('.', 'cmstaskenv', 'data'),
             os.path.join('/', 'usr', 'local', 'share', 'cms', 'cmsMake')]


def detect_data_dir():
    for _dir in DATA_DIRS:
        if os.path.exists(_dir):
            return os.path.abspath(_dir)


DATA_DIR = detect_data_dir()


def endswith2(string, suffixes):
    """True if string ends with one of the given suffixes.

    """
    return any(filter(lambda x: string.endswith(x), suffixes))


def basename2(string, suffixes):
    """If string ends with one of the specified suffixes, returns its
    basename (i.e., itself after removing the suffix) and the suffix
    packed in a tuple. Otherwise returns None.

    """
    try:
        idx = map(lambda x: string.endswith(x), suffixes).index(True)
    except ValueError:
        return None
    return (string[:-len(suffixes[idx])], string[-len(suffixes[idx]):])


def call(base_dir, args, stdin=None, stdout=None, stderr=None, env=None):
    print >> sys.stderr, "> Executing command %s in dir %s" % \
          (" ".join(args), base_dir)
    if env is None:
        env = {}
    env2 = copy.copy(os.environ)
    env2.update(env)
    res = subprocess.call(args, stdin=stdin, stdout=stdout, stderr=stderr,
                          cwd=base_dir, env=env2)
    if res != 0:
        print >> sys.stderr, "Subprocess returned with error"
        sys.exit(1)


def detect_task_name(base_dir):
    return os.path.split(os.path.realpath(base_dir))[1]


def parse_task_yaml(base_dir):
    parent_dir = os.path.split(os.path.realpath(base_dir))[0]
    yaml_path = os.path.join(parent_dir, "%s.yaml" %
                             (detect_task_name(base_dir)))

    with open(yaml_path) as yaml_file:
        conf = yaml.load(yaml_file)
    return conf


def detect_task_type(base_dir):
    sol_dir = os.path.join(base_dir, SOL_DIRNAME)
    check_dir = os.path.join(base_dir, CHECK_DIRNAME)
    grad_present = os.path.exists(sol_dir) and \
        any(filter(lambda x: x.startswith(GRAD_BASENAME + '.'),
                   os.listdir(sol_dir)))
    stub_present = os.path.exists(sol_dir) and \
        any(filter(lambda x: x.startswith('stub.'),
                   os.listdir(sol_dir)))
    cor_present = os.path.exists(check_dir) and \
        any(filter(lambda x: x.startswith('correttore.'),
                   os.listdir(check_dir)))
    man_present = os.path.exists(check_dir) and \
        any(filter(lambda x: x.startswith('manager.'),
                   os.listdir(check_dir)))

    if not (cor_present or man_present or stub_present or grad_present):
        return ["Batch", "Diff"]  # TODO Could also be an OutputOnly
    elif not (man_present or stub_present or grad_present) and cor_present:
        return ["Batch", "Comp"]  # TODO Could also be an OutputOnly
    elif not (cor_present or man_present or stub_present) and grad_present:
        return ["Batch", "Grad"]
    elif not (man_present or stub_present) and cor_present and grad_present:
        return ["Batch", "GradComp"]
    elif not (cor_present or grad_present) and man_present and stub_present:
        return ["Communication", ""]
    else:
        return ["Invalid", ""]


def noop():
    pass


def build_sols_list(base_dir, task_type, in_out_files, yaml_conf):
    if yaml_conf.get('only_gen', False):
        return []

    sol_dir = os.path.join(base_dir, SOL_DIRNAME)
    entries = map(lambda x: os.path.join(SOL_DIRNAME, x), os.listdir(sol_dir))
    sources = filter(lambda x: endswith2(x, SOL_EXTS), entries)

    actions = []
    test_actions = []
    for src in sources:
        exe, lang = basename2(src, SOL_EXTS)
        # Delete the dot
        lang = lang[1:]

        # Ignore things known to be auxiliary files
        if exe == os.path.join(SOL_DIRNAME, GRAD_BASENAME):
            continue
        if lang == 'pas' and exe.endswith('lib'):
            continue

        srcs = []
        # The grader, when present, must be in the first position of
        # srcs; see docstring of get_compilation_command().
        if task_type == ['Batch', 'Grad'] or \
                task_type == ['Batch', 'GradComp']:
            srcs.append(os.path.join(SOL_DIRNAME,
                                     GRAD_BASENAME + '.%s' % (lang)))
        srcs.append(src)

        test_deps = [exe] + in_out_files
        if task_type == ['Batch', 'Comp'] or \
                task_type == ['Batch', 'GradComp']:
            test_deps.append('cor/correttore')

        box_path = Sandbox().detect_box_executable()

        def compile_src(srcs, exe, lang):
            if lang != 'pas' or len(srcs) == 1:
                call(base_dir, get_compilation_command(lang, srcs, exe,
                                                       for_evaluation=False))

            # When using Pascal with graders, file naming conventions
            # require us to do a bit of trickery, i.e., performing the
            # compilation in a separate temporary directory
            else:
                tempdir = tempfile.mkdtemp()
                task_name = detect_task_name(base_dir)
                new_srcs = [os.path.split(srcs[0])[1],
                            '%s.pas' % (task_name)]
                new_exe = os.path.split(srcs[1])[1][:-4]
                shutil.copyfile(os.path.join(base_dir, srcs[0]), os.path.join(tempdir, new_srcs[0]))
                shutil.copyfile(os.path.join(base_dir, srcs[1]), os.path.join(tempdir, new_srcs[1]))
                lib_filename = '%slib.pas' % (task_name)
                if os.path.exists(os.path.join(SOL_DIRNAME, lib_filename)):
                    shutil.copyfile(os.path.join(SOL_DIRNAME, lib_filename),
                                    os.path.join(tempdir, lib_filename))
                call(tempdir, get_compilation_command(lang, new_srcs, new_exe,
                                                      for_evaluation=False))
                shutil.copyfile(os.path.join(tempdir, new_exe),
                                os.path.join(base_dir, SOL_DIRNAME, new_exe))
                shutil.copymode(os.path.join(tempdir, new_exe),
                                os.path.join(base_dir, SOL_DIRNAME, new_exe))
                shutil.rmtree(tempdir)

        def test_src(exe, input_num, task_type):
            print "Testing solution %s" % (exe)
            cormgr = ''
            if task_type == ['Batch', 'Comp'] or \
                    task_type == ['Batch', 'GradComp']:
                cormgr = 'cor/correttore'
            test_testcases(
                base_dir,
                input_num,
                box_path,
                exe,
                yaml_conf['timeout'],
                yaml_conf['memlimit'],
                task_type[0],
                task_type[1],
                cormgr=cormgr)

        actions.append((srcs,
                        [exe],
                        functools.partial(compile_src, srcs, exe, lang),
                        'compile solution'))

        input_num = len(in_out_files) / 2
        test_actions.append((test_deps,
                             ['test_%s' % (os.path.split(exe)[1])],
                             functools.partial(test_src,
                                               exe,
                                               input_num,
                                               task_type),
                             'test solution'))

    return actions + test_actions


def build_checker_list(base_dir, task_type):
    check_dir = os.path.join(base_dir, CHECK_DIRNAME)
    actions = []

    if os.path.exists(check_dir):
        entries = map(lambda x: os.path.join(CHECK_DIRNAME, x),
                      os.listdir(check_dir))
        sources = filter(lambda x: endswith2(x, SOL_EXTS), entries)
        for src in sources:
            exe, lang = basename2(src, CHECK_EXTS)
            # Delete the dot
            lang = lang[1:]

            def compile_check(src, exe):
                call(base_dir, get_compilation_command(lang, [src], exe))

            actions.append(([src], [exe],
                            functools.partial(compile_check, src, exe),
                            'compile checker'))

    return actions


def build_text_list(base_dir, task_type):
    text_xml = os.path.join(TEXT_DIRNAME, TEXT_XML)
    text_tex = os.path.join(TEXT_DIRNAME, TEXT_TEX)
    text_pdf = os.path.join(TEXT_DIRNAME, TEXT_PDF)
    text_aux = os.path.join(TEXT_DIRNAME, TEXT_AUX)
    text_log = os.path.join(TEXT_DIRNAME, TEXT_LOG)
    text_html = os.path.join(TEXT_DIRNAME, TEXT_HTML)

    def make_html():
        with open(os.path.join(base_dir, text_html), 'w') as fout:
            call(base_dir,
                 ['xsltproc',
                  os.path.join(DATA_DIR, 'problem_layout.xslt'), text_xml],
                 stdout=fout)

    def make_tex():
        with open(os.path.join(base_dir, text_tex), 'w') as fout:
            call(base_dir,
                 ['xsltproc',
                  os.path.join(DATA_DIR, 'problem_layout_tex.xslt'), text_xml],
                 stdout=fout)

    def make_pdf():
        call(base_dir,
             ['pdflatex', '-output-directory', TEXT_DIRNAME,
              '-interaction', 'batchmode', text_tex],
             env={'TEXINPUTS': '.:%s:%s/file:' % (TEXT_DIRNAME, TEXT_DIRNAME)})

    def make_input0():
        with open(os.path.join(base_dir, INPUT0_TXT), 'w') as fout:
            call(base_dir,
                 ['xsltproc',
                  os.path.join(DATA_DIR, 'estrai_input.xslt'), text_xml],
                 stdout=fout)

    def make_output0():
        with open(os.path.join(base_dir, OUTPUT0_TXT), 'w') as fout:
            call(base_dir,
                 ['xsltproc',
                  os.path.join(DATA_DIR, 'estrai_output.xslt'), text_xml],
                 stdout=fout)

    actions = []
    actions.append(([text_xml], [text_html],
                    make_html, 'compile to HTML'))
    actions.append(([text_xml], [text_tex],
                    make_tex, 'compile to LaTeX'))
    actions.append(([text_tex], [text_pdf, text_aux, text_log],
                    make_pdf, 'compile to PDF'))
    actions.append(([text_xml], [INPUT0_TXT],
                    make_input0, 'extract first input'))
    actions.append(([text_xml], [OUTPUT0_TXT],
                    make_output0, 'extract first output'))
    return actions


def iter_file(name):
    for l in open(name, "r"):
        l = (" " + l).split("#")[0][1:].strip("\n")
        if l != "":
            yield l


def build_gen_list(base_dir, task_type):
    input_dir = os.path.join(base_dir, INPUT_DIRNAME)
    output_dir = os.path.join(base_dir, OUTPUT_DIRNAME)
    gen_dir = os.path.join(base_dir, GEN_DIRNAME)
    entries = os.listdir(gen_dir)
    sources = filter(lambda x: endswith2(x, GEN_EXTS), entries)
    gen_exe = None
    validator_exe = None

    for src in sources:
        base, lang = basename2(src, GEN_EXTS)
        if base == GEN_BASENAME:
            gen_exe = os.path.join(GEN_DIRNAME, base + lang)
        elif base == VALIDATOR_BASENAME:
            validator_exe = os.path.join(GEN_DIRNAME, base + lang)
    if gen_exe is None:
        raise Exception("Couldn't find generator")
    if validator_exe is None:
        raise Exception("Couldn't find validator")
    gen_GEN = os.path.join(GEN_DIRNAME, GEN_GEN)

    sol_exe = os.path.join(SOL_DIRNAME, SOL_FILENAME)

    # Count non-trivial lines in GEN
    testcase_num = 0
    for line in iter_file(os.path.join(base_dir, gen_GEN)):
        testcase_num += 1

    def make_input():
        n = 0
        try:
            os.makedirs(input_dir)
        except OSError:
            pass
        for line in iter_file(os.path.join(base_dir, gen_GEN)):
            print >> sys.stderr, "Generating input # %d" % (n)
            with open(os.path.join(input_dir,
                                   'input%d.txt' % (n)), 'w') as fout:
                call(base_dir,
                     [gen_exe] + line.split(),
                     stdout=fout)
            call(base_dir,
                 [validator_exe, os.path.join(input_dir,
                                              'input%d.txt' % (n))])
            n += 1

    def make_output(n):
        try:
            os.makedirs(output_dir)
        except OSError:
            pass
        print >> sys.stderr, "Generating output # %d" % (n)
        with open(os.path.join(input_dir, 'input%d.txt' % (n))) as fin:
            with open(os.path.join(output_dir,
                                   'output%d.txt' % (n)), 'w') as fout:
                call(base_dir, [sol_exe], stdin=fin, stdout=fout)

    actions = []
    actions.append(([gen_GEN, gen_exe],
                    map(lambda x: os.path.join(INPUT_DIRNAME,
                                               'input%d.txt' % (x)),
                        range(0, testcase_num)),
                    make_input,
                    "input generation"))

    for n in xrange(testcase_num):
        actions.append(([os.path.join(INPUT_DIRNAME, 'input%d.txt' % (n)),
                         sol_exe],
                        [os.path.join(OUTPUT_DIRNAME, 'output%d.txt' % (n))],
                        functools.partial(make_output, n),
                        "output generation"))
    in_out_files = [os.path.join(INPUT_DIRNAME, 'input%d.txt' % (n))
                    for n in xrange(testcase_num)] + \
                    [os.path.join(OUTPUT_DIRNAME, 'output%d.txt' % (n))
                     for n in xrange(testcase_num)]
    return actions, in_out_files


def build_action_list(base_dir, task_type, yaml_conf):
    """Build a list of actions that cmsMake is able to do here. Each
    action is described by a tuple (infiles, outfiles, callable,
    description) where:

    1) infiles is a list of files this action depends on;

    2) outfiles is a list of files this action produces; it is
    intended that this action can be skipped if all the outfiles is
    newer than all the infiles; moreover, the outfiles get deleted
    when the action is cleaned;

    3) callable is a callable Python object that, when called,
    performs the action;

    4) description is a human-readable description of what this
    action does.

    """
    actions = []
    gen_actions, in_out_files = build_gen_list(base_dir, task_type)
    actions += gen_actions
    actions += build_sols_list(base_dir, task_type, in_out_files, yaml_conf)
    actions += build_checker_list(base_dir, task_type)
    #actions += build_text_list(base_dir, task_type)
    return actions


def clean(base_dir, generated_list):
    # Delete all generated files
    for f in generated_list:
        try:
            os.remove(os.path.join(base_dir, f))
        except OSError:
            pass

    # Delete other things
    try:
        os.rmdir(os.path.join(base_dir, INPUT_DIRNAME))
    except OSError:
        pass
    try:
        os.rmdir(os.path.join(base_dir, OUTPUT_DIRNAME))
    except OSError:
        pass
    try:
        shutil.rmtree(os.path.join(base_dir, RESULT_DIRNAME))
    except OSError:
        pass

    # Delete backup files
    os.system("find %s -name '*.pyc' -delete" % (base_dir))
    os.system("find %s -name '*~' -delete" % (base_dir))


def build_execution_tree(actions):
    """Given a set of actions as described in the docstring of
    build_action_list(), builds an execution tree and the list of all
    the buildable files. The execution tree is a dictionary that maps
    each builable or source file to the tuple (infiles, callable),
    where infiles and callable are as in the docstring of
    build_action_list().

    """
    exec_tree = {}
    generated_list = []
    src_list = set()
    for action in actions:
        for exe in action[1]:
            if exe in exec_tree:
                raise Exception("Target %s not unique" % (exe))
            exec_tree[exe] = (action[0], action[2])
            generated_list.append(exe)
        for src in action[0]:
            src_list.add(src)
    for src in src_list:
        if src not in exec_tree:
            exec_tree[src] = ([], noop)
    return exec_tree, generated_list


def execute_target(base_dir, exec_tree, target,
                   already_executed=None, stack=None,
                   debug=False):
    # Initialization
    if debug:
        print ">> Target %s is requested" % (target)
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
        if debug:
            print ">> Target %s has already been built, ignoring..." % (target)
        return

    # Otherwise, do a step of the DFS to make dependencies
    if debug:
        print ">> Building dependencies for target %s" % (target)
    already_executed.add(target)
    stack.add(target)
    for dep in deps:
        execute_target(base_dir, exec_tree, dep, already_executed, stack)
    stack.remove(target)
    if debug:
        print ">> Dependencies built for target %s" % (target)

    # Check if the action really needs to be done (i.e., there is one
    # dependency more recent than the generated file)
    dep_times = max([0] + map(lambda dep: os.stat(
        os.path.join(base_dir, dep)).st_mtime, deps))
    try:
        gen_time = os.stat(os.path.join(base_dir, target)).st_mtime
    except OSError:
        gen_time = 0
    if gen_time >= dep_times:
        if debug:
            print ">> Target %s is already new enough, not building" % (target)
        return

    # At last: actually make the so long desired action :-)
    if debug:
        print ">> Acutally building target %s" % (target)
    action()
    if debug:
        print ">> Target %s finished to build" % (target)


def execute_multiple_targets(base_dir, exec_tree, targets, debug=False):
    already_executed = set()
    for target in targets:
        execute_target(base_dir, exec_tree, target,
                       already_executed, debug=debug)


def main():
    # Parse command line options
    parser = optparse.OptionParser(usage="usage: %prog [options] [target]")
    parser.add_option("-D", "--base-dir",
                      help="base directory for problem to make "
                      "(CWD by default)",
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
    parser.add_option("-d", "--debug",
                      help="enable debug messages",
                      dest="debug", action="store_true", default=False)
    options, args = parser.parse_args()

    base_dir = options.base_dir
    if base_dir is None:
        base_dir = os.getcwd()
    else:
        base_dir = os.path.abspath(base_dir)

    task_type = detect_task_type(base_dir)
    yaml_conf = parse_task_yaml(base_dir)
    actions = build_action_list(base_dir, task_type, yaml_conf)
    exec_tree, generated_list = build_execution_tree(actions)

    if [len(args) > 0, options.list, options.clean,
        options.all].count(True) > 1:
        parser.error("Too many commands")

    if options.list:
        print "Task name: %s" % (detect_task_name(base_dir))
        print "Task type: %s %s" % (task_type[0], task_type[1])
        print "Available operations:"
        for entry in actions:
            print "  %s: %s -> %s" % (entry[3], ", ".join(entry[0]),
                                      ", ".join(entry[1]))

    elif options.clean:
        print "Cleaning"
        clean(base_dir, generated_list)

    elif options.all:
        print "Making all targets"
        execute_multiple_targets(base_dir, exec_tree,
                                 generated_list, debug=options.debug)

    else:
        execute_multiple_targets(base_dir, exec_tree,
                                 args, debug=options.debug)

if __name__ == '__main__':
    main()
