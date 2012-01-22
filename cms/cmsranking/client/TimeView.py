# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011-2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from DataStore import DataStore

from pyjamas import Window
from pyjamas import DOM

from __pyjamas__ import JS

import math


def _get_time():
    """Return the seconds since January 1, 1970 00:00:00 UTC"""
    JS('''
    var date = new Date();
    return parseInt(date.getTime() / 1000);
    ''')


class TimeView(object):
    def __init__(self, ds):
        self.ds = ds
        JS('''
        window.setInterval(function() {
            self.on_timer();
        }, 1000);
        ''')

    def on_timer(self):
        cur_time = _get_time()
        i = None
        # contests are iterated sorted by begin time
        # and the first one that's still running is chosen
        for c_id, contest in self.ds.iter_contests():
            if cur_time <= contest['end']:
                i = c_id
                break

        elem = DOM.getElementById('timer')
        if i is not None:
            time_dlt = abs(cur_time - self.ds.contests[i]['begin'])
            time_str = '%d:%02d:%02d' % (time_dlt / 3600,
                                         time_dlt / 60 % 60,
                                         time_dlt % 60)
            if self.ds.contests[i]['begin'] > cur_time:
                time_str = '-' + time_str
            html = '<div class="contest_name">%s</div>\n' \
                   '<div class="contest_time">%s</div>\n'
            result = html % (self.ds.contests[i]['name'], time_str)
            DOM.setInnerHTML(elem, result)
            JS('elem.classList.add("active");')
        else:
            DOM.setInnerHTML(elem, 'No active contest')
            JS('elem.classList.remove("active");')
