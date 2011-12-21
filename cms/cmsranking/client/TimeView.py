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

from DataStore import DataStore

from pyjamas import Window
from pyjamas import DOM

from __pyjamas__ import JS

import math


JS('''
function format_time(time) {
    var h = Math.floor(time / 3600);
    var m = Math.floor((time % 3600) / 60);
    var s = time % 60;
    m = m < 10 ? "0" + m : "" + m;
    s = s < 10 ? "0" + s : "" + s;
    return (h + ":" + m + ":" + s);
};
''')

JS('''
function _get_time() {
    // Return the seconds since January 1, 1970 00:00:00 UTC
    var date = new Date();
    return parseInt(date.getTime() / 1000);
}
''')

class TimeView(object):
    def __init__(self, ds):
        self.ds = ds
        JS('''
        self.on_timer();
        window.setInterval(function() {
            self.on_timer();
        }, 1000);
        ''')

    def on_timer(self):
        JS('''
        var cur_time = _get_time();
        var i = null;

        // contests are iterated sorted by begin time
        // and the first one that's still running is chosen
        for (var j in self.ds.contest_list) {
            var contest = self.ds.contest_list[j];
            if (cur_time <= contest['end']) {
                i = contest['key'];
                break;
            }
        }

        elem = TimeView.DOM.getElementById('timer');

        if (i != null) {
            var time_dlt = Math.abs(cur_time - self.ds.contests[i]['begin']);
            var time_str = format_time(time_dlt);
            if (self.ds.contests[i]['begin'] > cur_time) {
                time_str = '-' + time_str;
            }
            result = " \
<div class=\\"contest_name\\">" + self.ds.contests[i]['name'] + "</div> \
<div class=\\"contest_time\\">" + time_str + "</div>";
            elem.innerHTML = result;
            elem.classList.add("active");
        } else {
            elem.innerHTML = 'No active contest';
            elem.classList.remove("active");
        }
        ''')
