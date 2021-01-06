#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Masaki Hara <ackie.h.gmai@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

import os
import re

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py


PACKAGE_DATA = {
    "cms.server": [
        "static/*.*",
        "static/jq/*.*",
        "admin/static/*.*",
        "admin/static/jq/*.*",
        "admin/static/sh/*.*",
        "admin/templates/*.*",
        "admin/templates/fragments/*.*",
        "admin/templates/macro/*.*",
        "contest/static/*.*",
        "contest/static/css/*.*",
        "contest/static/img/*.*",
        "contest/static/img/mimetypes/*.*",
        "contest/static/js/*.*",
        "contest/templates/*.*",
        "contest/templates/macro/*.*",
    ],
    "cms.service": [
        "templates/printing/*.*",
    ],
    "cms.locale": [
        "*/LC_MESSAGES/*.*",
    ],
    "cmsranking": [
        "static/img/*.*",
        "static/lib/*.*",
        "static/*.*",
    ],
    "cmstestsuite": [
        "code/*.*",
        "tasks/batch_stdio/data/*.*",
        "tasks/batch_fileio/data/*.*",
        "tasks/batch_fileio_managed/code/*",
        "tasks/batch_fileio_managed/data/*.*",
        "tasks/communication_fifoio_stubbed/code/*",
        "tasks/communication_fifoio_stubbed/data/*.*",
        "tasks/communication_many_fifoio_stubbed/code/*",
        "tasks/communication_many_fifoio_stubbed/data/*.*",
        "tasks/communication_many_stdio_stubbed/code/*",
        "tasks/communication_many_stdio_stubbed/data/*.*",
        "tasks/communication_stdio/code/*",
        "tasks/communication_stdio/data/*.*",
        "tasks/communication_stdio_stubbed/code/*",
        "tasks/communication_stdio_stubbed/data/*.*",
        "tasks/outputonly/data/*.*",
        "tasks/outputonly_comparator/code/*",
        "tasks/outputonly_comparator/data/*.*",
        "tasks/twosteps/code/*.*",
        "tasks/twosteps/data/*.*",
        "tasks/twosteps_comparator/code/*",
        "tasks/twosteps_comparator/data/*.*",
    ],
}


def find_version():
    """Return the version string obtained from cms/__init__.py"""
    path = os.path.join("cms", "__init__.py")
    with open(path, "rt", encoding="utf-8") as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                                  f.read(), re.M)
    if version_match is not None:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


# We piggyback the translation catalogs compilation onto build_py since
# the po and mofiles will be part of the package data for cms.locale,
# which is collected at this stage.
class build_py_and_l10n(build_py):
    def run(self):
        self.run_command("compile_catalog")
        # The build command of distutils/setuptools searches the tree
        # and compiles a list of data files before run() is called and
        # then stores that value. Hence we need to refresh it.
        self.data_files = self._get_data_files()
        super().run()


setup(
    name="cms",
    version=find_version(),
    author="The CMS development team",
    author_email="contestms@googlegroups.com",
    url="https://github.com/cms-dev/cms",
    download_url="https://github.com/cms-dev/cms/archive/master.tar.gz",
    description="A contest management system and grader "
                "for IOI-like programming competitions",
    packages=find_packages(),
    package_data=PACKAGE_DATA,
    cmdclass={"build_py": build_py_and_l10n},
    scripts=["scripts/cmsLogService",
             "scripts/cmsScoringService",
             "scripts/cmsEvaluationService",
             "scripts/cmsWorker",
             "scripts/cmsResourceService",
             "scripts/cmsChecker",
             "scripts/cmsContestWebServer",
             "scripts/cmsAdminWebServer",
             "scripts/cmsProxyService",
             "scripts/cmsPrintingService",
             "scripts/cmsRankingWebServer",
             "scripts/cmsInitDB",
             "scripts/cmsDropDB"],
    entry_points={
        "console_scripts": [
            "cmsRunTests=cmstestsuite.RunTests:main",
            "cmsAddAdmin=cmscontrib.AddAdmin:main",
            "cmsAddParticipation=cmscontrib.AddParticipation:main",
            "cmsAddStatement=cmscontrib.AddStatement:main",
            "cmsAddSubmission=cmscontrib.AddSubmission:main",
            "cmsAddTeam=cmscontrib.AddTeam:main",
            "cmsAddTestcases=cmscontrib.AddTestcases:main",
            "cmsAddUser=cmscontrib.AddUser:main",
            "cmsCleanFiles=cmscontrib.CleanFiles:main",
            "cmsDumpExporter=cmscontrib.DumpExporter:main",
            "cmsDumpImporter=cmscontrib.DumpImporter:main",
            "cmsDumpUpdater=cmscontrib.DumpUpdater:main",
            "cmsExportSubmissions=cmscontrib.ExportSubmissions:main",
            "cmsImportContest=cmscontrib.ImportContest:main",
            "cmsImportDataset=cmscontrib.ImportDataset:main",
            "cmsImportTask=cmscontrib.ImportTask:main",
            "cmsImportTeam=cmscontrib.ImportTeam:main",
            "cmsImportUser=cmscontrib.ImportUser:main",
            "cmsRWSHelper=cmscontrib.RWSHelper:main",
            "cmsRemoveContest=cmscontrib.RemoveContest:main",
            "cmsRemoveParticipation=cmscontrib.RemoveParticipation:main",
            "cmsRemoveSubmissions=cmscontrib.RemoveSubmissions:main",
            "cmsRemoveTask=cmscontrib.RemoveTask:main",
            "cmsRemoveUser=cmscontrib.RemoveUser:main",
            "cmsSpoolExporter=cmscontrib.SpoolExporter:main",
            "cmsMake=cmstaskenv.cmsMake:main",
        ],
        "cms.grading.tasktypes": [
            "Batch=cms.grading.tasktypes.Batch:Batch",
            "Communication=cms.grading.tasktypes.Communication:Communication",
            "OutputOnly=cms.grading.tasktypes.OutputOnly:OutputOnly",
            "TwoSteps=cms.grading.tasktypes.TwoSteps:TwoSteps",
            "Notice=cms.grading.tasktypes.Notice:Notice",
        ],
        "cms.grading.scoretypes": [
            "Sum=cms.grading.scoretypes.Sum:Sum",
            "GroupMin=cms.grading.scoretypes.GroupMin:GroupMin",
            "GroupMul=cms.grading.scoretypes.GroupMul:GroupMul",
            "GroupThreshold=cms.grading.scoretypes.GroupThreshold:GroupThreshold",
        ],
        "cms.grading.languages": [
            "C++11 / g++=cms.grading.languages.cpp11_gpp:Cpp11Gpp",
            "C++14 / g++=cms.grading.languages.cpp14_gpp:Cpp14Gpp",
            "C++17 / g++=cms.grading.languages.cpp17_gpp:Cpp17Gpp",
            "C11 / gcc=cms.grading.languages.c11_gcc:C11Gcc",
            "C# / Mono=cms.grading.languages.csharp_mono:CSharpMono",
            "Haskell / ghc=cms.grading.languages.haskell_ghc:HaskellGhc",
            "Java / JDK=cms.grading.languages.java_jdk:JavaJDK",
            "Pascal / fpc=cms.grading.languages.pascal_fpc:PascalFpc",
            "PHP=cms.grading.languages.php:Php",
            "Python 2 / CPython=cms.grading.languages.python2_cpython:Python2CPython",
            "Python 3 / CPython=cms.grading.languages.python3_cpython:Python3CPython",
            "Rust=cms.grading.languages.rust:Rust",
        ],
    },
    keywords="ioi programming contest grader management system",
    license="Affero General Public License v3",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: "
        "GNU Affero General Public License v3",
    ]
)
