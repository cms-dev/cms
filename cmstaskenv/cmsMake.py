#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014-2015 Luca Versari <veluca93@gmail.com>
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

import argparse
import copy
import functools
import logging
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

from cms import utf8_decoder
from cms.grading.languagemanager import SOURCE_EXTS, filename_to_language
from cmscommon.terminal import move_cursor, add_color_to_string, \
    colors, directions
from cmstaskenv.Test import test_testcases, clean_test_env


SOL_DIRNAME = 'sol'
SOL_FILENAME = 'soluzione'
SOL_EXTS = SOURCE_EXTS
CHECK_DIRNAME = 'cor'
CHECK_EXTS = SOL_EXTS
TEXT_DIRNAME = 'testo'
TEXT_TEX = 'testo.tex'
TEXT_PDF = 'testo.pdf'
TEXT_AUX = 'testo.aux'
TEXT_LOG = 'testo.log'
INPUT0_TXT = 'input0.txt'
OUTPUT0_TXT = 'output0.txt'
GEN_DIRNAME = 'gen'
GEN_GEN = 'GEN'
GEN_BASENAME = 'generatore'
GEN_EXTS = ['.py', '.sh', '.cpp', '.c', '.pas']
VALIDATOR_BASENAME = 'valida'
GRAD_BASENAME = 'grader'
STUB_BASENAME = 'stub'
INPUT_DIRNAME = 'input'
OUTPUT_DIRNAME = 'output'
RESULT_DIRNAME = 'result'

DATA_DIRS = [os.path.join('.', 'cmstaskenv', 'data'),
             os.path.join('/', 'usr', 'local', 'share', 'cms', 'cmsMake')]

logger = logging.getLogger()


def detect_data_dir():
    for _dir in DATA_DIRS:
        if os.path.exists(_dir):
            return os.path.abspath(_dir)


DATA_DIR = detect_data_dir()


def endswith2(string, suffixes):
    """True if string ends with one of the given suffixes.

    """
    return any(string.endswith(suffix) for suffix in suffixes)


def basename2(string, suffixes):
    """If string ends with one of the specified suffixes, returns its
    basename (i.e., itself after removing the suffix) and the suffix
    packed in a tuple. Otherwise returns None.

    """
    try:
        suffix = next(s for s in suffixes if string.endswith(s))
        return string[:-len(suffix)], string[-len(suffix):]
    except StopIteration:
        return None, None


def call(base_dir, args, stdin=None, stdout=None, stderr=None, env=None):
    print("> Executing command %s in dir %s" %
          (" ".join(args), base_dir), file=sys.stderr)
    if env is None:
        env = {}
    env2 = copy.copy(os.environ)
    env2.update(env)
    subprocess.check_call(args, stdin=stdin, stdout=stdout, stderr=stderr,
                          cwd=base_dir, env=env2)


def detect_task_name(base_dir):
    return os.path.split(os.path.abspath(base_dir))[1]


def parse_task_yaml(base_dir):
    parent_dir = os.path.split(os.path.abspath(base_dir))[0]

    # We first look for the yaml file inside the task folder,
    # and eventually fallback to a yaml file in its parent folder.
    yaml_path = os.path.join(base_dir, "task.yaml")

    try:
        with open(yaml_path, "rt", encoding="utf-8") as yaml_file:
            conf = yaml.load(yaml_file)
    except OSError:
        yaml_path = os.path.join(parent_dir, "%s.yaml" %
                                 (detect_task_name(base_dir)))

        with open(yaml_path, "rt", encoding="utf-8") as yaml_file:
            conf = yaml.load(yaml_file)
    return conf


def detect_task_type(base_dir):
    sol_dir = os.path.join(base_dir, SOL_DIRNAME)
    check_dir = os.path.join(base_dir, CHECK_DIRNAME)
    grad_present = os.path.exists(sol_dir) and \
        any(x.startswith(GRAD_BASENAME + '.') for x in os.listdir(sol_dir))
    stub_present = os.path.exists(sol_dir) and \
        any(x.startswith(STUB_BASENAME + '.') for x in os.listdir(sol_dir))
    cor_present = os.path.exists(check_dir) and \
        any(x.startswith('correttore.') for x in os.listdir(check_dir))
    man_present = os.path.exists(check_dir) and \
        any(x.startswith('manager.') for x in os.listdir(check_dir))

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

    actions = []
    test_actions = []
    for src in (os.path.join(SOL_DIRNAME, x)
                for x in os.listdir(sol_dir)
                if endswith2(x, SOL_EXTS)):
        exe, ext = basename2(src, SOL_EXTS)
        lang = filename_to_language(src)
        # Delete the dot
        ext = ext[1:]
        exe_EVAL = "%s_EVAL" % (exe)

        # Ignore things known to be auxiliary files
        if exe == os.path.join(SOL_DIRNAME, GRAD_BASENAME):
            continue
        if exe == os.path.join(SOL_DIRNAME, STUB_BASENAME):
            continue
        if ext == 'pas' and exe.endswith('lib'):
            continue

        srcs = []
        # The grader, when present, must be in the first position of srcs.
        if task_type == ['Batch', 'Grad'] or \
                task_type == ['Batch', 'GradComp']:
            srcs.append(os.path.join(SOL_DIRNAME,
                                     GRAD_BASENAME + '.%s' % (ext)))
        if task_type == ['Communication', '']:
            srcs.append(os.path.join(SOL_DIRNAME,
                                     STUB_BASENAME + '.%s' % (ext)))
        srcs.append(src)

        test_deps = [exe_EVAL] + in_out_files
        if task_type == ['Batch', 'Comp'] or \
                task_type == ['Batch', 'GradComp']:
            test_deps.append('cor/correttore')
        if task_type == ['Communication', '']:
            test_deps.append('cor/manager')

        def compile_src(srcs, exe, for_evaluation, lang, assume=None):
            # We put everything in a temporary directory to reproduce
            # the same conditions that we have when compiling a
            # submission.
            tempdir = tempfile.mkdtemp()
            try:
                task_name = detect_task_name(base_dir)
                grader_num = 1 if len(srcs) > 1 else 0
                new_srcs = []
                for grader in srcs[:grader_num]:
                    grader_name = os.path.basename(grader)
                    shutil.copyfile(os.path.join(base_dir, grader),
                                    os.path.join(tempdir, grader_name))
                    new_srcs.append(os.path.join(tempdir, grader_name))
                # For now, we assume we only have one non-grader source.
                source_name = task_name + lang.source_extension
                shutil.copyfile(os.path.join(base_dir, srcs[grader_num]),
                                os.path.join(tempdir, source_name))
                new_srcs.append(source_name)
                # Libraries are needed/used only for C/C++ and Pascal
                header_extension = lang.header_extension
                if header_extension is not None:
                    lib_template = "%s" + header_extension
                    lib_filename = lib_template % (task_name)
                    lib_path = os.path.join(
                        base_dir, SOL_DIRNAME, lib_filename)
                    if os.path.exists(lib_path):
                        shutil.copyfile(lib_path,
                                        os.path.join(tempdir, lib_filename))
                new_exe = os.path.join(tempdir, task_name)
                compilation_commands = lang.get_compilation_commands(
                    new_srcs, new_exe, for_evaluation=for_evaluation)
                for command in compilation_commands:
                    call(tempdir, command)
                    move_cursor(directions.UP, erase=True, stream=sys.stderr)
                shutil.copyfile(os.path.join(tempdir, new_exe),
                                os.path.join(base_dir, exe))
                shutil.copymode(os.path.join(tempdir, new_exe),
                                os.path.join(base_dir, exe))
            finally:
                shutil.rmtree(tempdir)

        def test_src(exe, lang, assume=None):
            # Solution names begin with sol/ and end with _EVAL, we strip that
            print(
                "Testing solution",
                add_color_to_string(exe[4:-5], colors.BLACK, bold=True)
            )
            test_testcases(
                base_dir,
                exe,
                language=lang,
                assume=assume)

        actions.append(
            (srcs,
             [exe],
             functools.partial(compile_src, srcs, exe, False, lang),
             'compile solution'))
        actions.append(
            (srcs,
             [exe_EVAL],
             functools.partial(compile_src, srcs, exe_EVAL, True, lang),
             'compile solution with -DEVAL'))

        test_actions.append((test_deps,
                             ['test_%s' % (os.path.split(exe)[1])],
                             functools.partial(test_src, exe_EVAL, lang),
                             'test solution (compiled with -DEVAL)'))

    return actions + test_actions


def build_checker_list(base_dir, task_type):
    check_dir = os.path.join(base_dir, CHECK_DIRNAME)
    actions = []

    if os.path.exists(check_dir):
        for src in (os.path.join(CHECK_DIRNAME, x)
                    for x in os.listdir(check_dir)
                    if endswith2(x, SOL_EXTS)):
            exe, ext = basename2(src, CHECK_EXTS)
            lang = filename_to_language(src)

            def compile_check(src, exe, assume=None):
                commands = lang.get_compilation_commands([src], exe)
                for command in commands:
                    call(base_dir, command)

            actions.append(([src], [exe],
                            functools.partial(compile_check, src, exe),
                            'compile checker'))

    return actions


def build_text_list(base_dir, task_type):
    text_tex = os.path.join(TEXT_DIRNAME, TEXT_TEX)
    text_pdf = os.path.join(TEXT_DIRNAME, TEXT_PDF)
    text_aux = os.path.join(TEXT_DIRNAME, TEXT_AUX)
    text_log = os.path.join(TEXT_DIRNAME, TEXT_LOG)

    def make_pdf(assume=None):
        call(base_dir,
             ['pdflatex', '-output-directory', TEXT_DIRNAME,
              '-interaction', 'batchmode', text_tex],
             env={'TEXINPUTS': '.:%s:%s/file:' % (TEXT_DIRNAME, TEXT_DIRNAME)})

    actions = []
    if os.path.exists(text_tex):
        actions.append(([text_tex], [text_pdf, text_aux, text_log],
                        make_pdf, 'compile to PDF'))

    return actions


def iter_GEN(name):
    st = 0
    with open(name, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            splitted = line.split('#', 1)

            if len(splitted) == 1:
                # This line represents a testcase, otherwise
                # it's just a blank
                if splitted[0] != '':
                    yield (False, splitted[0], st)

            else:
                testcase, comment = splitted
                is_trivial = comment.startswith(" ")
                testcase = testcase.strip()
                comment = comment.strip()
                testcase_detected = len(testcase) > 0
                copy_testcase_detected = comment.startswith("COPY:")
                subtask_detected = comment.startswith('ST:')

                flags = [testcase_detected,
                         copy_testcase_detected,
                         subtask_detected]

                flags_count = len([x for x in flags if x])

                if flags_count > 1:
                    raise Exception("No testcase and command in"
                                    " the same line allowed")

                if flags_count == 0 and not is_trivial:
                    raise Exception("Unrecognized non-trivial line")

                if testcase_detected:
                    yield (False, testcase, st)

                if copy_testcase_detected:
                    yield (True, comment[5:].strip(), st)

                # This line starts a new subtask
                if subtask_detected:
                    st += 1


def build_gen_list(base_dir, task_type, yaml_conf):
    input_dir = os.path.join(base_dir, INPUT_DIRNAME)
    output_dir = os.path.join(base_dir, OUTPUT_DIRNAME)
    gen_dir = os.path.join(base_dir, GEN_DIRNAME)
    gen_exe = None
    validator_exe = None

    for src in (x for x in os.listdir(gen_dir) if endswith2(x, GEN_EXTS)):
        base, ext = basename2(src, GEN_EXTS)
        lang = filename_to_language(src)
        if base == GEN_BASENAME:
            gen_exe = os.path.join(GEN_DIRNAME, base)
            gen_src = os.path.join(GEN_DIRNAME, base + ext)
            gen_lang = lang
        elif base == VALIDATOR_BASENAME:
            validator_exe = os.path.join(GEN_DIRNAME, base)
            validator_src = os.path.join(GEN_DIRNAME, base + ext)
            validator_lang = lang
    if gen_exe is None:
        raise Exception("Couldn't find generator")
    if validator_exe is None:
        raise Exception("Couldn't find validator")
    gen_GEN = os.path.join(GEN_DIRNAME, GEN_GEN)

    sol_exe = os.path.join(SOL_DIRNAME, SOL_FILENAME)

    # Count non-trivial lines in GEN and establish which external
    # files are needed for input generation
    testcases = list(iter_GEN(os.path.join(base_dir, gen_GEN)))
    testcase_num = len(testcases)
    copy_files = [x[1] for x in testcases if x[0]]

    def compile_src(src, exe, lang, assume=None):
        if lang.source_extension in ['.cpp', '.c', '.pas']:
            commands = lang.get_compilation_commands(
                [src], exe, for_evaluation=False)
            for command in commands:
                call(base_dir, command)
        elif lang.source_extension in ['.py', '.sh']:
            os.symlink(os.path.basename(src), exe)
        else:
            raise Exception("Wrong generator/validator language!")

    # Question: why, differently from outputs, inputs have to be
    # created all together instead of selectively over those that have
    # been changed since last execution? This is a waste of time,
    # usually generating inputs is a pretty long thing. Answer:
    # because cmsMake architecture, which is based on file timestamps,
    # doesn't make us able to understand which lines of gen/GEN have
    # been changed. Douch! We'll have to think better this thing for
    # the new format we're developing.
    def make_input(assume=None):
        n = 0
        try:
            os.makedirs(input_dir)
        except OSError:
            pass
        for (is_copy, line, st) in testcases:
            print(
                "Generating",
                add_color_to_string("input # %d" % n, colors.BLACK,
                                    stream=sys.stderr, bold=True),
                file=sys.stderr
            )
            new_input = os.path.join(input_dir, 'input%d.txt' % (n))
            if is_copy:
                # Copy the file
                print("> Copy input file from:", line)
                copy_input = os.path.join(base_dir, line)
                shutil.copyfile(copy_input, new_input)
            else:
                # Call the generator
                with open(new_input, 'wb') as fout:
                    call(base_dir,
                         [gen_exe] + line.split(),
                         stdout=fout)
            command = [validator_exe, new_input]
            if st != 0:
                command.append("%s" % st)
            call(base_dir, command)
            n += 1
            for _ in range(3):
                move_cursor(directions.UP, erase=True, stream=sys.stderr)

    def make_output(n, assume=None):
        try:
            os.makedirs(output_dir)
        except OSError:
            pass
        print(
            "Generating",
            add_color_to_string("output # %d" % n, colors.BLACK,
                                stream=sys.stderr, bold=True),
            file=sys.stderr
        )

        temp_dir = tempfile.mkdtemp(prefix=os.path.join(base_dir, "tmp"))
        use_stdin = yaml_conf.get("infile") in {None, ""}
        use_stdout = yaml_conf.get("outfile") in {None, ""}

        # Names of the actual source and destination.
        infile = os.path.join(input_dir, 'input%d.txt' % (n))
        outfile = os.path.join(output_dir, 'output%d.txt' % (n))

        # Names of the input and output in temp directory.
        copied_infile = os.path.join(
            temp_dir,
            "input.txt" if use_stdin else yaml_conf.get("infile"))
        copied_outfile = os.path.join(
            temp_dir,
            "output.txt" if use_stdout else yaml_conf.get("outfile"))

        os.symlink(infile, copied_infile)
        fin = None
        fout = None

        try:
            if use_stdin:
                fin = open(copied_infile, "rb")
            if use_stdout:
                fout = open(copied_outfile, 'wb')

            shutil.copy(sol_exe, temp_dir)

            # If the task of of type Communication, then there is
            # nothing to put in the output files
            if task_type != ['Communication', '']:
                call(temp_dir, [os.path.join(temp_dir, SOL_FILENAME)],
                     stdin=fin, stdout=fout)
                move_cursor(directions.UP, erase=True, stream=sys.stderr)

        finally:
            if fin is not None:
                fin.close()
            if fout is not None:
                fout.close()

        os.rename(copied_outfile, outfile)
        shutil.rmtree(temp_dir)

        move_cursor(directions.UP, erase=True, stream=sys.stderr)

    actions = []
    actions.append(([gen_src],
                    [gen_exe],
                    functools.partial(compile_src, gen_src, gen_exe, gen_lang),
                    "compile the generator"))
    actions.append(([validator_src],
                    [validator_exe],
                    functools.partial(compile_src, validator_src,
                                      validator_exe, validator_lang),
                    "compile the validator"))
    actions.append(([gen_GEN, gen_exe, validator_exe] + copy_files,
                    [os.path.join(INPUT_DIRNAME, 'input%d.txt' % (x))
                     for x in range(0, testcase_num)],
                    make_input,
                    "input generation"))

    for n in range(testcase_num):
        actions.append(([os.path.join(INPUT_DIRNAME, 'input%d.txt' % (n)),
                         sol_exe],
                        [os.path.join(OUTPUT_DIRNAME, 'output%d.txt' % (n))],
                        functools.partial(make_output, n),
                        "output generation"))
    in_out_files = [os.path.join(INPUT_DIRNAME, 'input%d.txt' % (n))
                    for n in range(testcase_num)] + \
                   [os.path.join(OUTPUT_DIRNAME, 'output%d.txt' % (n))
                    for n in range(testcase_num)]
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
    gen_actions, in_out_files = build_gen_list(base_dir, task_type, yaml_conf)
    actions += gen_actions
    actions += build_sols_list(base_dir, task_type, in_out_files, yaml_conf)
    actions += build_checker_list(base_dir, task_type)
    actions += build_text_list(base_dir, task_type)
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

    # Delete compiled and/or backup files
    for dirname, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if any(filename.endswith(ext) for ext in {".o", ".pyc", "~"}):
                os.remove(os.path.join(dirname, filename))


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
                   debug=False, assume=None):
    # Initialization
    if debug:
        print(">> Target %s is requested" % (target))
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
            print(">> Target %s has already been built, ignoring..." %
                  (target))
        return

    # Otherwise, do a step of the DFS to make dependencies
    if debug:
        print(">> Building dependencies for target %s" % (target))
    already_executed.add(target)
    stack.add(target)
    for dep in deps:
        execute_target(base_dir, exec_tree, dep,
                       already_executed, stack, assume=assume)
    stack.remove(target)
    if debug:
        print(">> Dependencies built for target %s" % (target))

    # Check if the action really needs to be done (i.e., there is one
    # dependency more recent than the generated file)
    dep_times = max(
        [0] + [os.stat(os.path.join(base_dir, dep)).st_mtime for dep in deps])
    try:
        gen_time = os.stat(os.path.join(base_dir, target)).st_mtime
    except OSError:
        gen_time = 0
    if gen_time >= dep_times:
        if debug:
            print(">> Target %s is already new enough, not building" %
                  (target))
        return

    # At last: actually make the so long desired action :-)
    if debug:
        print(">> Acutally building target %s" % (target))
    action(assume=assume)
    if debug:
        print(">> Target %s finished to build" % (target))


def execute_multiple_targets(base_dir, exec_tree, targets,
                             debug=False, assume=None):
    already_executed = set()
    for target in targets:
        execute_target(base_dir, exec_tree, target,
                       already_executed, debug=debug, assume=assume)


def main():
    # Parse command line options
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument("-D", "--base-dir", action="store", type=utf8_decoder,
                        help="base directory for problem to make "
                        "(CWD by default)")
    parser.add_argument("-l", "--list", action="store_true", default=False,
                        help="list actions that cmsMake is aware of")
    parser.add_argument("-c", "--clean", action="store_true", default=False,
                        help="clean all generated files")
    parser.add_argument("-a", "--all", action="store_true", default=False,
                        help="make all targets")
    group.add_argument("-y", "--yes",
                       dest="assume", action="store_const", const='y',
                       help="answer yes to all questions")
    group.add_argument("-n", "--no",
                       dest="assume", action="store_const", const='n',
                       help="answer no to all questions")
    parser.add_argument("-d", "--debug", action="store_true", default=False,
                        help="enable debug messages")
    parser.add_argument("targets", action="store", type=utf8_decoder,
                        nargs="*", metavar="target", help="target to build")
    options = parser.parse_args()

    base_dir = options.base_dir
    if base_dir is None:
        base_dir = os.getcwd()
    else:
        base_dir = os.path.abspath(base_dir)

    assume = options.assume

    task_type = detect_task_type(base_dir)
    yaml_conf = parse_task_yaml(base_dir)
    actions = build_action_list(base_dir, task_type, yaml_conf)
    exec_tree, generated_list = build_execution_tree(actions)

    if [len(options.targets) > 0, options.list, options.clean,
            options.all].count(True) > 1:
        parser.error("Too many commands")

    if options.list:
        print("Task name: %s" % (detect_task_name(base_dir)))
        print("Task type: %s %s" % (task_type[0], task_type[1]))
        print("Available operations:")
        for entry in actions:
            print("  %s: %s -> %s" %
                  (entry[3], ", ".join(entry[0]), ", ".join(entry[1])))

    elif options.clean:
        print("Cleaning")
        clean(base_dir, generated_list)

    elif options.all:
        print("Making all targets")
        print()
        try:
            execute_multiple_targets(base_dir, exec_tree,
                                     generated_list, debug=options.debug,
                                     assume=assume)

        # After all work, possibly clean the left-overs of testing
        finally:
            clean_test_env()

    else:
        try:
            execute_multiple_targets(base_dir, exec_tree,
                                     options.targets, debug=options.debug,
                                     assume=assume)

        # After all work, possibly clean the left-overs of testing
        finally:
            clean_test_env()


if __name__ == '__main__':
    main()
