#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
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

import os

from setuptools import setup, find_packages


# Install cms.mo files
DATA_FILES = []
for root, subdirs, files in os.walk("mo"):
    if subdirs == []:
        DATA_FILES.append((root, [os.path.join(root, files[0])]))

PACKAGE_DATA = {
    "cms.server": [
        os.path.join("static", "*.*"),
        os.path.join("static", "jq", "*.*"),
        os.path.join("admin", "static", "*.*"),
        os.path.join("admin", "static", "jq", "*.*"),
        os.path.join("admin", "static", "sh", "*.*"),
        os.path.join("admin", "templates", "*.*"),
        os.path.join("admin", "templates", "fragments", "*.*"),
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


setup(
    name="cms",
    version="1.3.dev0",
    author="The CMS development team",
    author_email="contestms@freelists.org",
    url="https://github.com/cms-dev/cms",
    download_url="https://github.com/cms-dev/cms/archive/master.tar.gz",
    description="A contest management system and grader "
                "for IOI-like programming competitions",
    packages=find_packages(),
    package_data=PACKAGE_DATA,
    data_files=DATA_FILES,
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
            "cmsAddUser=cmscontrib.AddUser:main",
            "cmsRemoveUser=cmscontrib.RemoveUser:main",
            "cmsAddTask=cmscontrib.AddTask:main",
            "cmsRemoveTask=cmscontrib.RemoveTask:main",
            "cmsComputeComplexity=cmscontrib.ComputeComplexity:main",
            "cmsAddContest=cmscontrib.AddContest:main",
            "cmsDumpExporter=cmscontrib.DumpExporter:main",
            "cmsDumpImporter=cmscontrib.DumpImporter:main",
            "cmsSpoolExporter=cmscontrib.SpoolExporter:main",
            "cmsContestExporter=cmscontrib.ContestExporter:main",
            "cmsContestImporter=cmscontrib.ContestImporter:main",
            "cmsDumpUpdater=cmscontrib.DumpUpdater:main",
            "cmsRWSHelper=cmscontrib.RWSHelper:main",
            "cmsMake=cmstaskenv.cmsMake:main",
            "cmsYamlImporter=cmscompat.YamlImporter:main",
            "cmsYamlReimporter=cmscompat.YamlReimporter:main",
        ]
    },
    keywords="ioi programming contest grader management system",
    license="Affero General Public License v3",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: "
        "GNU Affero General Public License v3",
    ]
)
