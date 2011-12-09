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

from pyjamas.HTTPRequest import HTTPRequest
from pyjamas.JSONParser import JSONParser

from pyjamas import Window


# Config
submission_url = '/submissions/%s'


class Callback:
    def __init__(self, callback):
        self.callback = callback

    def onCompletion(self, response):
        self.callback(JSONParser().decode(response))

    def onError(self, response, code):
        Window.alert("Error " + code + '\n' + response)


class SubmissionStore:
    def request_update(self, user_id, callback):
        HTTPRequest().asyncGet((submission_url % user_id), Callback(callback))
