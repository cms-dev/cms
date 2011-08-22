#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""An example of a data provider.

Read all the data from disk (from contests/, tasks/, teams/, users/
and submissions/) and provide it to the competition module.
No real-time update of the data is done.

"""

import os
import re
import json

from operator import attrgetter

import competition

contests_data = {}
for path in os.listdir('contests'):
    if re.match('[a-zA-Z0-9_]+\.json', path):
        with open(os.path.join('contests', path)) as f:
            iden = re.findall('([a-zA-Z0-9_]+)\.json', path)[0]
            data = json.load(f)
            contests_data[iden] = data

tasks_data = {}
for path in os.listdir('tasks'):
    if re.match('[a-zA-Z0-9_]+\.json', path):
        with open(os.path.join('tasks', path)) as f:
            iden = re.findall('([a-zA-Z0-9_]+)\.json', path)[0]
            data = json.load(f)
            tasks_data[iden] = data

teams_data = {}
for path in os.listdir('teams'):
    if re.match('[a-zA-Z0-9_]+\.json', path):
        with open(os.path.join('teams', path)) as f:
            iden = re.findall('([a-zA-Z0-9_]+)\.json', path)[0]
            data = json.load(f)
            teams_data[iden] = data

users_data = {}
for path in os.listdir('users'):
    if re.match('[a-zA-Z0-9_]+\.json', path):
        with open(os.path.join('users', path)) as f:
            iden = re.findall('([a-zA-Z0-9_]+)\.json', path)[0]
            data = json.load(f)
            users_data[iden] = data

competition.load_data(contests_data, tasks_data, teams_data, users_data)

sub_list = []

for path in os.listdir('submissions'):
    if re.match('[a-zA-Z0-9_]+\.json', path):
        with open(os.path.join('submissions', path)) as f:
            data = json.load(f)
            iden = re.findall('([a-zA-Z0-9_]+)\.json', path)[0]
            sub_list.append(competition.Submission(iden, data))

sub_list.sort(key=attrgetter('time'))

for sub in sub_list:
    competition.scores[sub.user.id][sub.task.id].create_submission(sub)

for user in competition.users:
    for rank in competition.compute_rank_history(user):
        pass
