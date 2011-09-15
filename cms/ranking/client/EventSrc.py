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

# uncomment if you use polyfill
# import EventSource.js

from __pyjamas__ import JS

import EventSource.js


class EventSrc:
    def __init__(self, url):
        JS("self.event_src = new EventSource(url);")

    def add_event_listener(self, name, listener):
        JS("self.event_src.addEventListener(name, listener);")
