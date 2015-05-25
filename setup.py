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

from glob import glob
from setuptools import setup, find_packages


PACKAGE_DATA = {
    "cms.io": [
        os.path.join("static", "*"),
    ],
    "cms.server": [
        os.path.join("static", "jq", "*.*"),
        os.path.join("static", "sh", "*.*"),
        os.path.join("static", "css", "*.*"),
        os.path.join("static", "js", "*.*"),
        os.path.join("static", "img", "*.*"),
        os.path.join("static", "img", "mimetypes", "*.*"),
        os.path.join("static", "*.*"),
        os.path.join("templates", "contest", "*.*"),
        os.path.join("templates", "admin", "*.*"),
        os.path.join("templates", "admin", "fragments", "*.*"),
        os.path.join("templates", "ranking", "*.*"),
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
    version="1.3.0pre",
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
