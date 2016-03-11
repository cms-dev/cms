#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Build and installation routines for CMS.

"""

from __future__ import absolute_import
from __future__ import print_function
# setuptools doesn't seem to like this:
# from __future__ import unicode_literals

import io
import re
import os

from setuptools import setup, find_packages


PACKAGE_DATA = {
    "cms.server": [
        os.path.join("static", "*.*"),
        os.path.join("static", "jq", "*.*"),
        os.path.join("admin", "static", "*.*"),
        os.path.join("admin", "static", "jq", "*.*"),
        os.path.join("admin", "static", "sh", "*.*"),
        os.path.join("admin", "templates", "*.*"),
        os.path.join("admin", "templates", "fragments", "*.*"),
        os.path.join("admin", "templates", "views", "*.*"),
        os.path.join("contest", "static", "*.*"),
        os.path.join("contest", "static", "css", "*.*"),
        os.path.join("contest", "static", "img", "*.*"),
        os.path.join("contest", "static", "img", "mimetypes", "*.*"),
        os.path.join("contest", "static", "js", "*.*"),
        os.path.join("contest", "templates", "*.*"),
    ],
    "cms.service": [
        os.path.join("templates", "printing", "*.*"),
    ],
    "cms.locale": [
        os.path.join("*", "LC_MESSAGES", "*.*"),
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
        os.path.join("tasks", "batch_fileio_managed", "code", "*"),
        os.path.join("tasks", "batch_fileio_managed", "data", "*.*"),
        os.path.join("tasks", "communication", "code", "*"),
        os.path.join("tasks", "communication", "data", "*.*"),
    ],
}


def find_version():
    """Return the version string obtained from cms/__init__.py"""
    path = os.path.join("cms", "__init__.py")
    version_file = io.open(path, "rt", encoding="utf-8").read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match is not None:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name="cms",
    version=find_version(),
    author="The CMS development team",
    author_email="contestms@freelists.org",
    url="https://github.com/cms-dev/cms",
    download_url="https://github.com/cms-dev/cms/archive/master.tar.gz",
    description="A contest management system and grader "
                "for IOI-like programming competitions",
    packages=find_packages(),
    package_data=PACKAGE_DATA,
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
            "cmsReplayContest=cmstestsuite.ReplayContest:main",
            "cmsAdaptContest=cmstestsuite.AdaptContest:main",
            "cmsTestFileCacher=cmstestsuite.TestFileCacher:main",
            "cmsAddAdmin=cmscontrib.AddAdmin:main",
            "cmsAddParticipation=cmscontrib.AddParticipation:main",
            "cmsAddSubmission=cmscontrib.AddSubmission:main",
            "cmsAddTeam=cmscontrib.AddTeam:main",
            "cmsAddUser=cmscontrib.AddUser:main",
            "cmsComputeComplexity=cmscontrib.ComputeComplexity:main",
            "cmsDumpExporter=cmscontrib.DumpExporter:main",
            "cmsDumpImporter=cmscontrib.DumpImporter:main",
            "cmsDumpUpdater=cmscontrib.DumpUpdater:main",
            "cmsExportSubmissions=cmscontrib.ExportSubmissions:main",
            "cmsImportContest=cmscontrib.ImportContest:main",
            "cmsImportTask=cmscontrib.ImportTask:main",
            "cmsImportTeam=cmscontrib.ImportTeam:main",
            "cmsImportUser=cmscontrib.ImportUser:main",
            "cmsRWSHelper=cmscontrib.RWSHelper:main",
            "cmsRemoveContest=cmscontrib.RemoveContest:main",
            "cmsRemoveSubmissions=cmscontrib.RemoveSubmissions:main",
            "cmsRemoveTask=cmscontrib.RemoveTask:main",
            "cmsRemoveUser=cmscontrib.RemoveUser:main",
            "cmsSpoolExporter=cmscontrib.SpoolExporter:main",
            "cmsMake=cmstaskenv.cmsMake:main",
            "cmsYamlImporter=cmscompat.YamlImporter:main",
            "cmsYamlReimporter=cmscompat.YamlReimporter:main",
        ]
    },
    keywords="ioi programming contest grader management system",
    license="Affero General Public License v3",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: "
        "GNU Affero General Public License v3",
    ]
)
