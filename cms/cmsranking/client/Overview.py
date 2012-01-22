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

from pyjamas.ui.UIObject import UIObject

from pyjamas import Window
from pyjamas import DOM


class Overview:
    def __init__(self, ds):
        self.ds = ds

        elem = DOM.getElementById("overview")

        inner_html = '''
<div class="bar1"></div>
<div class="bar2"></div>'''

        for u_id in self.ds.users.iterkeys():
            inner_html += '''
<div class="mark1" id="''' + u_id + '''_lm"></div>
<div class="mark2" id="''' + u_id + '''_rm"></div>'''

        DOM.setInnerHTML(elem, inner_html)

        self.ds.add_select_handler(self.update_select)
        self.update_score()

    def update_score(self):
        users = sorted([(-1 * self.ds.get_score(u_id), u_id)
                        for u_id in self.ds.users.iterkeys()])

        prev_score = None
        rank = 0
        equal = 1

        for score, u_id in users:
            score *= -1
            if score != prev_score:
                prev_score = score
                rank += equal
                equal = 1
            else:
                equal += 1

            elem1 = DOM.getElementById(u_id + '_lm')
            DOM.setStyleAttribute(
                elem1, 'bottom', str(score / sum(
                    [task['score'] for task in self.ds.tasks.itervalues()]
                    ) * 100) + '%')

            elem2 = DOM.getElementById(u_id + '_rm')
            DOM.setStyleAttribute(elem2, 'bottom', str(100 - (rank - 1) /
                                                       (len(self.ds.users) - 1)
                                                       * 100) + '%')

    def update_select(self, u_id, flag):
        elem1 = UIObject(Element=DOM.getElementById(u_id + '_lm'))
        elem2 = UIObject(Element=DOM.getElementById(u_id + '_rm'))

        if flag:
            elem1.addStyleName('selected')
            elem2.addStyleName('selected')
        else:
            elem1.removeStyleName('selected')
            elem2.removeStyleName('selected')
