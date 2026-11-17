#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
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

"""Tests for the Polygon task loader."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest

from cms.grading.languagemanager import LANGUAGES
from cmscontrib.loaders.polygon import PolygonTaskLoader


CPP_LANGUAGES = [language.name for language in LANGUAGES
                 if language.source_extension == ".cpp"]
PYTHON_LANGUAGES = [language.name for language in LANGUAGES
                    if language.source_extension == ".py"]

COMPILE_FOR_SOLUTION = (
    '<stages><stage name="compile"/></stages>'
    '<assets><asset name="solution"/></assets>')


class FakeFileCacher:
    """Store file contents in memory, keyed by their SHA-1."""

    def __init__(self):
        self.files = {}
        self.puts = []

    def put_file_from_path(self, path, description=""):
        with open(path, "rb") as f:
            content = f.read()
        digest = hashlib.sha1(content).hexdigest()
        self.files[digest] = content
        self.puts.append(path)
        return digest


class TestPolygonTaskLoader(unittest.TestCase):

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.path = os.path.join(self.base_dir, "aplusb")
        os.makedirs(os.path.join(self.path, "files"))
        self.file_cacher = FakeFileCacher()

    def tearDown(self):
        shutil.rmtree(self.base_dir)

    def write(self, relative_path, content=""):
        path = os.path.join(self.path, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def write_problem(self, resources="", assets="", testsets=None,
                      test_count=2):
        """Write problem.xml and the test files it refers to."""
        if testsets is None:
            testsets = ["tests"]
        testset_xml = ""
        for testset in testsets:
            testset_xml += (
                '<testset name="%s">'
                '<time-limit>1000</time-limit>'
                '<memory-limit>268435456</memory-limit>'
                '<test-count>%d</test-count>'
                '<input-path-pattern>%s/%%02d</input-path-pattern>'
                '<answer-path-pattern>%s/%%02d.a</answer-path-pattern>'
                '</testset>' % (testset, test_count, testset, testset))
            for i in range(1, test_count + 1):
                self.write("%s/%02d" % (testset, i), "%d\n" % i)
                self.write("%s/%02d.a" % (testset, i), "%d\n" % i)
        self.write("problem.xml", (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<problem short-name="aplusb">'
            '<names><name language="english" value="A+B"/></names>'
            '<judging input-file="" output-file="">%s</judging>'
            '<files><resources>%s</resources></files>'
            '<assets>%s</assets>'
            '</problem>' % (testset_xml, resources, assets)))

    def load(self):
        loader = PolygonTaskLoader(self.path, self.file_cacher)
        return loader.get_task(get_statement=False)

    def content(self, manager):
        return self.file_cacher.files[manager.digest].decode()

    def test_plain_batch_task(self):
        self.write_problem()
        task = self.load()
        self.assertIsNotNone(task)
        self.assertIsNone(task.allowed_languages)
        dataset = task.active_dataset
        self.assertEqual(dataset.task_type_parameters,
                         ["alone", ["", ""], "diff"])
        self.assertEqual(dataset.managers, {})
        self.assertEqual(sorted(dataset.testcases), ["000", "001"])
        self.assertEqual(
            self.file_cacher.files[dataset.testcases["001"].input], b"2\n")

    def test_declared_cpp_grader_and_header(self):
        self.write("files/grader.cpp", "// grader")
        self.write("files/aplusb.h", "// api")
        self.write("files/testlib.h", "// stock testlib")
        self.write_problem(resources=(
            '<file path="files/testlib.h" type="h.g++"/>'
            '<file for-types="cpp.*" path="files/grader.cpp" '
            'type="cpp.g++17">' + COMPILE_FOR_SOLUTION + '</file>'
            '<file path="files/aplusb.h" type="h.g++">'
            + COMPILE_FOR_SOLUTION + '</file>'))
        task = self.load()
        self.assertIsNotNone(task)
        self.assertEqual(task.allowed_languages, CPP_LANGUAGES)
        dataset = task.active_dataset
        self.assertEqual(dataset.task_type_parameters[0], "grader")
        self.assertEqual(sorted(dataset.managers), ["aplusb.h", "grader.cpp"])
        self.assertEqual(self.content(dataset.managers["grader.cpp"]),
                         "// grader")

    def test_declared_grader_with_other_name(self):
        self.write("files/main.cc", "// grader")
        self.write_problem(resources=(
            '<file for-types="cpp.*" path="files/main.cc">'
            + COMPILE_FOR_SOLUTION + '</file>'))
        task = self.load()
        self.assertEqual(sorted(task.active_dataset.managers), ["grader.cpp"])

    def test_declared_python_grader(self):
        self.write("files/grader.py", "import aplusb\n")
        self.write_problem(resources=(
            '<file for-types="python.*" path="files/grader.py">'
            + COMPILE_FOR_SOLUTION + '</file>'))
        task = self.load()
        self.assertEqual(task.allowed_languages, PYTHON_LANGUAGES)
        self.assertEqual(sorted(task.active_dataset.managers), ["grader.py"])

    def test_cpp_and_python_graders(self):
        self.write("files/grader.cpp", "// grader")
        self.write("files/grader.py", "import aplusb\n")
        self.write_problem(resources=(
            '<file for-types="cpp.*" path="files/grader.cpp">'
            + COMPILE_FOR_SOLUTION + '</file>'
            '<file for-types="python.*" path="files/grader.py">'
            + COMPILE_FOR_SOLUTION + '</file>'))
        task = self.load()
        self.assertEqual(sorted(task.allowed_languages),
                         sorted(CPP_LANGUAGES + PYTHON_LANGUAGES))

    def test_missing_declared_grader_fails(self):
        self.write_problem(resources=(
            '<file for-types="cpp.*" path="files/grader.cpp">'
            + COMPILE_FOR_SOLUTION + '</file>'))
        self.assertIsNone(self.load())

    def test_undeclared_grader_prefers_files_dir(self):
        self.write("files/grader.cpp", "// files grader")
        self.write("files/aplusb.h", "// files api")
        self.write("files/testlib.h", "// stock testlib")
        self.write("grader.cpp", "// root grader")
        self.write("aplusb.h", "// root api")
        self.write_problem()
        task = self.load()
        managers = task.active_dataset.managers
        self.assertEqual(sorted(managers), ["aplusb.h", "grader.cpp"])
        self.assertEqual(self.content(managers["grader.cpp"]),
                         "// files grader")
        self.assertEqual(self.content(managers["aplusb.h"]), "// files api")

    def test_headers_not_imported_without_grader(self):
        self.write("files/testlib.h", "// stock testlib")
        self.write("files/aplusb.h", "// api")
        self.write_problem()
        task = self.load()
        self.assertEqual(task.active_dataset.managers, {})

    def test_graders_stored_once_for_all_testsets(self):
        self.write("files/grader.cpp", "// grader")
        self.write_problem(
            resources=('<file for-types="cpp.*" path="files/grader.cpp">'
                       + COMPILE_FOR_SOLUTION + '</file>'),
            testsets=["tests", "tests2"])
        task = self.load()
        self.assertEqual(len(task.datasets), 2)
        for dataset in task.datasets:
            self.assertEqual(sorted(dataset.managers), ["grader.cpp"])
        grader_puts = [path for path in self.file_cacher.puts
                       if path.endswith("grader.cpp")]
        self.assertEqual(len(grader_puts), 1)

    def test_declared_interactor_is_rejected(self):
        self.write("files/inter.cpp", "// interactor")
        self.write_problem(assets=(
            '<interactor><source path="files/inter.cpp" '
            'type="cpp.g++17"/></interactor>'))
        self.assertIsNone(self.load())

    def test_test_path_outside_package_is_rejected(self):
        self.write_problem()
        problem_xml = os.path.join(self.path, "problem.xml")
        with open(problem_xml, encoding="utf-8") as f:
            content = f.read()
        self.write(os.path.join("..", "secret", "01.a"), "secret\n")
        self.write(os.path.join("..", "secret", "02.a"), "secret\n")
        content = content.replace("tests/%02d.a", "../secret/%02d.a")
        with open(problem_xml, "w", encoding="utf-8") as f:
            f.write(content)
        self.assertIsNone(self.load())

    def test_test_path_with_spaces(self):
        self.path = os.path.join(self.base_dir, "a plus b")
        os.makedirs(os.path.join(self.path, "files"))
        self.write_problem()
        self.write("tests/01", "1\r\n")
        task = self.load()
        self.assertIsNotNone(task)
        expected = b"1\n" if shutil.which("dos2unix") else b"1\r\n"
        self.assertEqual(
            self.file_cacher.files[task.active_dataset.testcases["000"].input],
            expected)


@unittest.skipIf(shutil.which("g++") is None, "g++ is not available")
class TestPolygonChecker(unittest.TestCase):
    """Compile real checkers with the patched testlib.h."""

    CHECKER = """
#include "testlib.h"
int main(int argc, char *argv[]) {
    registerTestlibCmd(argc, argv);
    int expected = ans.readInt();
    int got = ouf.readInt();
    if (got == expected) quitf(_ok, "ok");
    quitp(%s, "partial");
}
"""

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base_dir)

    def run_checker(self, points, output):
        package = os.path.join(self.base_dir, "task%s" % len(
            os.listdir(self.base_dir)))
        os.makedirs(os.path.join(package, "files"))
        with open(os.path.join(package, "files", "check.cpp"), "w") as f:
            f.write(self.CHECKER % points)
        file_cacher = FakeFileCacher()
        loader = PolygonTaskLoader(package, file_cacher)
        digest = loader._compile_checker(
            os.path.join(package, "files", "check.cpp"), "task")
        self.assertIsNotNone(digest)
        checker = os.path.join(package, "checker")
        with open(checker, "wb") as f:
            f.write(file_cacher.files[digest])
        os.chmod(checker, 0o755)
        paths = {}
        for name, content in (("input", "1\n"), ("correct", "5\n"),
                              ("output", output)):
            paths[name] = os.path.join(package, name)
            with open(paths[name], "w") as f:
                f.write(content)
        # CMS passes input, correct output, contestant output.
        return subprocess.run(
            [checker, paths["input"], paths["correct"], paths["output"]],
            capture_output=True, text=True)

    def test_accepted(self):
        result = self.run_checker("0.5", "5\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "1.0")
        self.assertEqual(result.stderr.strip(), "translate:success")

    def test_fractional_points(self):
        result = self.run_checker("0.5", "4\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "0.5")
        self.assertEqual(result.stderr.strip(), "translate:partial")

    def test_points_out_of_range_fail(self):
        result = self.run_checker("7", "4\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be in [0, 1]", result.stderr)


if __name__ == "__main__":
    unittest.main()
