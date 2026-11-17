#!/usr/bin/env python3

# Programming contest management system
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 Edoardo Morassutto <edoardo.morassutto@gmail.com>
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2021 Grace Hawkins <amoomajid99@gmail.com>
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

import logging
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import importlib.resources
import importlib.util
import tempfile
from datetime import datetime, timedelta

from cms import config
from cms.db import Contest, User, Task, Statement, Dataset, Manager, Testcase
from cms.grading.languagemanager import HEADER_EXTS, LANGUAGES
from cmscommon.crypto import build_password
from cmscontrib import touch
from .base_loader import ContestLoader, TaskLoader, UserLoader, LANGUAGE_MAP


logger = logging.getLogger(__name__)


def make_timedelta(t):
    return timedelta(seconds=t)


def _format_test_path(pattern, test_number):
    """Format a Polygon test path pattern for a one-based test number."""
    try:
        return pattern % test_number
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Invalid Polygon test path pattern %r: %s" % (pattern, error)
        ) from error


def _package_path(package_dir, relative_path):
    """Resolve a path taken from a Polygon package.

    Paths in problem.xml are relative to the package directory. Refuse
    absolute paths and ".." components that would read files outside it.

    """
    package_dir = os.path.realpath(package_dir)
    path = os.path.realpath(os.path.join(package_dir, relative_path))
    if os.path.commonpath([package_dir, path]) != package_dir:
        raise ValueError(
            "Path %r points outside the Polygon package" % relative_path)
    return path


def _is_header(filename):
    """Return whether filename is a header for some CMS language."""
    return any(filename.endswith(extension) for extension in HEADER_EXTS)


def _languages_for_source(filename):
    """Return the CMS languages that compile sources named like filename."""
    extension = os.path.splitext(filename)[1]
    return [language for language in LANGUAGES
            if extension in language.source_extensions]


def _solution_compile_resources(root):
    """Return the paths of resources Polygon compiles with solutions.

    Polygon exports graders, and the headers they need, as resources with
    the "compile" stage and the "solution" asset, for example:

        <file for-types="cpp.*" path="files/grader.cpp" type="cpp.g++17">
          <stages><stage name="compile"/></stages>
          <assets><asset name="solution"/></assets>
        </file>

    Other resources, such as testlib.h or olymp.sty, have no such marks.

    """
    paths = []
    for resource in root.iterfind("files/resources/file"):
        stages = {stage.get("name", "").lower()
                  for stage in resource.iterfind("stages/stage")}
        assets = {asset.get("name", "").lower()
                  for asset in resource.iterfind("assets/asset")}
        if "compile" in stages and "solution" in assets \
                and resource.get("path"):
            paths.append(resource.get("path"))
    return paths


class PolygonTaskLoader(TaskLoader):
    """Load a task stored using the Codeforces Polygon format.

    Given the filesystem location of a unpacked task that was packaged
    in the Polygon format (tests should already be generated), parse
    those files and directories to produce data that can be consumed by
    CMS, i.e. a Task object

    Also, as Polygon doesn't support CMS directly, and doesn't allow
    to customize some task parameters, users can add task configuration
    files which will be parsed and applied as is. By default, all tasks
    are batch files, with custom checker and score type is Sum.

    Loaders assumes that checker is check.cpp and written with usage of
    testlib.h. It provides customized version of testlib.h which allows
    using Polygon checkers with CMS. Checkers will be compiled during
    importing the contest. A checker that calls quitp() must report a
    fraction of the test's score in [0, 1].

    Graders are taken from the resources that problem.xml marks as
    compiled with solutions. Each grader becomes the CMS manager
    grader.<extension> (for example grader.cpp or grader.py), headers
    marked the same way are imported under their own names, and the task
    only allows the languages that have a grader. As usual in CMS, a
    Python grader is the entry point and must import the contestant's
    module, which is named after the task.

    Interactive problems are not supported.

    """

    short_name = 'polygon_task'
    description = 'Polygon (XML-based) task format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(os.path.join(path, "problem.xml"))

    def task_has_changed(self):
        """See docstring in class Loader.

        """
        return True

    def _has_interactor(self, root):
        """Return whether the package contains a Polygon interactor."""
        if root.find("assets/interactor") is not None:
            return True
        return any(os.path.exists(path) for path in (
            os.path.join(self.path, "files", "interactor.cpp"),
            os.path.join(self.path, "interactor.cpp"),
        ))

    def _find_checker(self, root):
        """Return the path of the checker source, or None if there is none.

        Prefer the source declared in problem.xml, then files/check.cpp,
        then check.cpp in the package root.

        """
        source = root.find("assets/checker/source")
        if source is not None and source.get("path"):
            path = _package_path(self.path, source.get("path"))
            if os.path.isfile(path):
                return path
        for path in (os.path.join(self.path, "files", "check.cpp"),
                     os.path.join(self.path, "check.cpp")):
            if os.path.isfile(path):
                return path
        return None

    def _find_grader_files(self, root):
        """Find the graders and headers compiled with solutions.

        return: a dict mapping each CMS manager filename to its source path.

        raise ValueError: if a declared file is missing, has no matching
            CMS language, or two files map to the same manager.

        """
        declared = _solution_compile_resources(root)
        if declared:
            sources = [_package_path(self.path, path) for path in declared]
        else:
            # Hand-made packages may lack the resource metadata. Accept
            # grader.<extension> and the headers next to it, looking in
            # files/ first like the checker lookup does.
            sources = []
            extensions = sorted({language.source_extension
                                 for language in LANGUAGES})
            for directory in (os.path.join(self.path, "files"), self.path):
                graders = [os.path.join(directory, "grader" + extension)
                           for extension in extensions]
                graders = [path for path in graders if os.path.isfile(path)]
                if not graders:
                    continue
                headers = [os.path.join(directory, filename)
                           for filename in sorted(os.listdir(directory))
                           if _is_header(filename)
                           and filename != "testlib.h"]
                sources = graders + [path for path in headers
                                     if os.path.isfile(path)]
                break

        files = {}
        for source in sources:
            if not os.path.isfile(source):
                raise ValueError("Grader resource %s is missing" % source)
            filename = os.path.basename(source)
            if _is_header(filename):
                manager_name = filename
            else:
                languages = _languages_for_source(filename)
                if not languages:
                    raise ValueError(
                        "No CMS language compiles the grader %s" % source)
                manager_name = "grader" + languages[0].source_extension
            if manager_name in files and files[manager_name] != source:
                raise ValueError(
                    "Both %s and %s would be imported as manager %s" %
                    (files[manager_name], source, manager_name))
            files[manager_name] = source
        return files

    def _compile_checker(self, checker_src, name):
        """Compile a testlib checker with the patched testlib.h.

        return: the digest of the checker binary, or None on failure.

        """
        with tempfile.TemporaryDirectory() as tempdir:
            # We need to override the testlib.h from the polygon
            # package with our patched version. Since the package
            # includes a testlib.h too, the easiest way to achieve this
            # is to copy the checker source to a temporary directory.
            testlib_res = importlib.resources.files(
                "cmscontrib.loaders").joinpath("polygon/testlib.h")
            with testlib_res.open('rb') as src, \
                    open(os.path.join(tempdir, "testlib.h"), "wb") as dst:
                shutil.copyfileobj(src, dst)
            new_checker_src = os.path.join(tempdir, "check.cpp")
            output_path = os.path.join(tempdir, "check")
            shutil.copyfile(checker_src, new_checker_src)
            code = subprocess.call(["g++", "-x", "c++", "-O2",
                                    "-static", "-DCMS", "-o",
                                    output_path, new_checker_src])
            if code != 0:
                return None
            return self.file_cacher.put_file_from_path(
                output_path, "Manager for task %s" % name)

    def get_task(self, get_statement=True):
        """See docstring in class Loader.

        """

        logger.info("Checking dos2unix presence")
        self.dos2unix_found = shutil.which("dos2unix") is not None
        if not self.dos2unix_found:
            logger.error("dos2unix not found - tests will not be converted!")

        name = os.path.basename(self.path)
        logger.info("Loading parameters for task %s.", name)

        args = {}

        # Here we update the time of the last import.
        touch(os.path.join(self.path, ".itime"))
        # If this file is not deleted, then the import failed.
        touch(os.path.join(self.path, ".import_error"))

        # Get alphabetical task index for use in title.

        tree = ET.parse(os.path.join(self.path, "problem.xml"))
        root = tree.getroot()

        # A Polygon interactor speaks the Polygon file/stdio protocol. CMS
        # interactive controllers use a different START_SOLUTION protocol and
        # cannot run this binary as a normal batch checker or manager.
        if self._has_interactor(root):
            logger.critical(
                "Polygon interactors are not supported by the Polygon loader "
                "(task %s). Convert the interactor to a CMS controller.", name
            )
            return None

        args["name"] = name
        args["title"] = str(root.find('names').find("name").attrib['value'])

        if get_statement:
            args["statements"] = {}
            args["primary_statements"] = []
            for language, lang in LANGUAGE_MAP.items():
                path = os.path.join(self.path, 'statements',
                                    '.pdf', language, 'problem.pdf')
                if os.path.exists(path):
                    digest = self.file_cacher.put_file_from_path(
                        path,
                        "Statement for task %s (lang: %s)" % (name,
                                                              language))
                    args["statements"][lang] = Statement(lang, digest)
                    args["primary_statements"].append(lang)

        args["submission_format"] = ["%s.%%l" % name]

        # These options cannot be configured in the Polygon format.
        # Uncomment the following to set specific values for them.

        # args['max_submission_number'] = 100
        # args['max_user_test_number'] = 100
        # args['min_submission_interval'] = make_timedelta(60)
        # args['min_user_test_interval'] = make_timedelta(60)

        # args['max_user_test_number'] = 10
        # args['min_user_test_interval'] = make_timedelta(60)

        # args['token_mode'] = 'infinite'
        # args['token_max_number'] = 100
        # args['token_min_interval'] = make_timedelta(60)
        # args['token_gen_initial'] = 1
        # args['token_gen_number'] = 1
        # args['token_gen_interval'] = make_timedelta(1800)
        # args['token_gen_max'] = 2

        # Graders and headers do not depend on the testset, so find and
        # store them once. A grader only exists for some languages (usually
        # C++), so the task allows just those; cms_conf.py can override it.
        try:
            grader_files = self._find_grader_files(root)
            checker_src = self._find_checker(root)
        except ValueError as error:
            logger.critical("Task %s: %s", name, error)
            return None
        grader_managers = {}
        for filename, source in grader_files.items():
            logger.info("Importing %s as manager %s", source, filename)
            grader_managers[filename] = self.file_cacher.put_file_from_path(
                source, "Manager %s for task %s" % (filename, name))
        grader_languages = [
            language.name for language in LANGUAGES
            if "grader%s" % language.source_extension in grader_managers]
        compilation_param = "grader" if grader_languages else "alone"
        if grader_languages:
            logger.info("Task %s uses graders, allowing only: %s",
                        name, ", ".join(grader_languages))
            args["allowed_languages"] = grader_languages

        task_cms_conf_path = os.path.join(self.path, 'files', 'cms_conf.py')
        task_cms_conf = None
        if os.path.exists(task_cms_conf_path):
            logger.info("Found additional CMS options for task %s.", name)
            spec = importlib.util.spec_from_file_location(
                'cms_conf', task_cms_conf_path)
            task_cms_conf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(task_cms_conf)
        if task_cms_conf is not None and hasattr(task_cms_conf, "general"):
            args.update(task_cms_conf.general)

        task = Task(**args)

        checker_digest = None
        if checker_src is not None:
            logger.info("Checker found, compiling %s", checker_src)
            checker_digest = self._compile_checker(checker_src, name)
            if checker_digest is None:
                logger.critical("Could not compile checker")
                return None
        else:
            logger.info("Checker not found, using diff")

        judging = root.find('judging')
        testset = None
        for testset in judging:
            testset_name = testset.attrib["name"]

            args = {}
            args["task"] = task
            args["description"] = str(testset_name)
            args["autojudge"] = False

            tl = float(testset.find('time-limit').text)
            ml = int(testset.find('memory-limit').text)
            args["time_limit"] = tl * 0.001
            # Polygon specifies the memory limit in bytes.
            args["memory_limit"] = ml

            args["managers"] = {}
            infile_param = judging.attrib['input-file']
            outfile_param = judging.attrib['output-file']

            for filename, digest in grader_managers.items():
                args["managers"][filename] = Manager(filename, digest)
            if checker_digest is not None:
                args["managers"]["checker"] = Manager("checker",
                                                      checker_digest)
                evaluation_param = "comparator"
            else:
                evaluation_param = "diff"

            args["task_type"] = "Batch"
            args["task_type_parameters"] = [
                compilation_param,
                [infile_param, outfile_param],
                evaluation_param,
            ]

            args["score_type"] = "Sum"
            total_value = 100.0
            input_value = 0.0

            test_count = testset.findtext('test-count')
            if test_count is None:
                logger.critical(
                    "Testset %s for task %s has no test-count.",
                    testset_name, name)
                return None
            try:
                testcases = int(test_count)
            except ValueError:
                logger.critical(
                    "Testset %s for task %s has an invalid test-count %r.",
                    testset_name, name, test_count)
                return None

            input_pattern = testset.findtext('input-path-pattern')
            answer_pattern = testset.findtext('answer-path-pattern')
            if input_pattern is None or answer_pattern is None:
                logger.critical(
                    "Testset %s for task %s has no input/answer path pattern.",
                    testset_name, name)
                return None

            n_input = testcases
            if n_input != 0:
                input_value = total_value / n_input
            args["score_type_parameters"] = input_value

            args["testcases"] = {}

            for i in range(testcases):
                try:
                    infile = _package_path(
                        self.path, _format_test_path(input_pattern, i + 1))
                    outfile = _package_path(
                        self.path, _format_test_path(answer_pattern, i + 1))
                except ValueError as error:
                    logger.critical("%s", error)
                    return None
                missing = [path for path in (infile, outfile)
                           if not os.path.isfile(path)]
                if missing:
                    logger.critical(
                        "Testset %s for task %s references missing file(s): %s",
                        testset_name, name, ", ".join(missing))
                    return None
                if self.dos2unix_found:
                    subprocess.call(["dos2unix", "-q", infile, outfile])
                input_digest = self.file_cacher.put_file_from_path(
                    infile,
                    "Input %d for task %s" % (i, name))
                output_digest = self.file_cacher.put_file_from_path(
                    outfile,
                    "Output %d for task %s" % (i, name))
                testcase = Testcase("%03d" % (i, ), False,
                                    input_digest, output_digest)
                testcase.public = True
                args["testcases"][testcase.codename] = testcase

            if task_cms_conf is not None and \
               hasattr(task_cms_conf, "datasets") and \
               testset_name in task_cms_conf.datasets:
                args.update(task_cms_conf.datasets[testset_name])

            dataset = Dataset(**args)
            if testset_name == "tests":
                task.active_dataset = dataset

        os.remove(os.path.join(self.path, ".import_error"))

        logger.info("Task parameters loaded.")
        return task


class PolygonUserLoader(UserLoader):
    """Load a user stored using the Codeforces Polygon format.

    As Polygon doesn't support CMS directly, and doesn't allow
    to specify users, we support(?) a non-standard file named
    contestants.txt to allow importing some set of users.

    """

    short_name = 'polygon_user'
    description = 'Polygon (XML-based) user format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(
            os.path.join(os.path.dirname(path), "contestants.txt"))

    def user_has_changed(self):
        """See docstring in class Loader.

        """
        return True

    def get_user(self):
        """See docstring in class Loader.

        """

        username = os.path.basename(self.path)
        userdata = None

        # This is not standard Polygon feature, but useful for CMS users
        # we assume contestants.txt contains one line for each user:
        #
        # username;password;first_name;last_name;hidden
        #
        # For example:
        #
        # contestant1;123;Cont;Estant;0
        # jury;1234;Ju;Ry;1

        users_path = os.path.join(
            os.path.dirname(self.path), 'contestants.txt')
        if os.path.exists(users_path):
            with open(users_path, "rt", encoding="utf-8") as users_file:
                for user in users_file.readlines():
                    user = user.strip().split(';')
                    name = user[0].strip()
                    if name == username:
                        userdata = [x.strip() for x in user]

        if userdata is not None:
            logger.info("Loading parameters for user %s.", username)
            args = {}
            args['username'] = userdata[0]
            args['password'] = build_password(userdata[1])
            args['first_name'] = userdata[2]
            args['last_name'] = userdata[3]
            args['hidden'] = (len(userdata) > 4 and userdata[4] == '1')
            logger.info("User parameters loaded.")
            return User(**args)
        else:
            logger.critical(
                "User %s not found in contestants.txt file.", username)
            return None


class PolygonContestLoader(ContestLoader):
    """Load a contest stored using the Codeforces Polygon format.

    Given the filesystem location of a unpacked package of contest in
    the Polygon format, parse those files and directories to produce
    data that can be consumed by CMS, i.e. a Contest object.

    Polygon (by now) doesn't allow custom contest-wide files, so
    general contest options should be hard-coded in the loader.

    """

    short_name = 'polygon_contest'
    description = 'Polygon (XML-based) contest format'

    @staticmethod
    def detect(path):
        """See docstring in class Loader.

        """
        return os.path.exists(os.path.join(path, "contest.xml")) and \
            os.path.exists(os.path.join(path, "problems"))

    def get_task_loader(self, taskname):
        taskpath = os.path.join(self.path, "problems", taskname)
        return PolygonTaskLoader(taskpath, self.file_cacher)

    def get_contest(self):
        """See docstring in class Loader.

        """

        name = os.path.split(self.path)[1]

        logger.info("Loading parameters for contest %s.", name)

        args = {}

        tree = ET.parse(os.path.join(self.path, "contest.xml"))
        root = tree.getroot()

        args['name'] = name

        # TODO: find proper way to choose contest primary language.

        self.primary_language = root.find('names') \
            .find('name').attrib['language']

        # All available contest languages are allowed to be used.

        self.languages = []
        for alternative_name in root.find('names'):
            self.languages.append(alternative_name.attrib['language'])

        logger.info("Contest languages are %s %s",
                    self.primary_language, str(self.languages))

        args['description'] = root.find('names') \
            .find("name[@language='%s']" % self.primary_language) \
            .attrib['value']

        logger.info("Contest description is %s", args['description'])

        # For now Polygon doesn't support custom contest-wide files,
        # so we need to hardcode some contest settings.

        args['start'] = datetime(1970, 1, 1)
        args['stop'] = datetime(1970, 1, 1)

        # Uncomment the following to set specific values for these
        # options.

        # args['max_submission_number'] = 100
        # args['max_user_test_number'] = 100
        # args['min_submission_interval'] = make_timedelta(60)
        # args['min_user_test_interval'] = make_timedelta(60)
        # args['max_user_test_number'] = 10
        # args['min_user_test_interval'] = make_timedelta(60)

        # args['token_mode'] = 'infinite'
        # args['token_max_number'] = 100
        # args['token_min_interval'] = make_timedelta(60)
        # args['token_gen_initial'] = 1
        # args['token_gen_number'] = 1
        # args['token_gen_interval'] = make_timedelta(1800)
        # args['token_gen_max'] = 2

        logger.info("Contest parameters loaded.")

        tasks = []
        for problem in root.find('problems'):
            tasks.append(os.path.basename(problem.attrib['url']))

        participations = []

        # This is not standard Polygon feature, but useful for CMS users
        # we assume contestants.txt contains one line for each user:
        #
        # username;password;first_name;last_name;hidden
        #
        # For example:
        #
        # contestant1;123;Cont;Estant;0
        # jury;1234;Ju;Ry;1

        users_path = os.path.join(self.path, 'contestants.txt')
        if os.path.exists(users_path):
            with open(users_path, "rt", encoding="utf-8") as users_file:
                for user in users_file.readlines():
                    user = user.strip()
                    user = user.split(';')
                    participations.append({
                        "username": user[0].strip(),
                        "password": build_password(user[1].strip()),
                        "hidden": user[4].strip()
                        # "ip" is not passed
                    })

        return Contest(**args), tasks, participations

    def contest_has_changed(self):
        """See docstring in class Loader.

        """
        return True
