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

from __pyjamas__ import JS

import re


class TeamSearch(object):
    def __init__(self, ds):
        self.ds = ds

        inputfield = DOM.getElementById('team_search_input')
        background = DOM.getElementById('team_search_bg')
        close_button = DOM.getElementById('team_search_close')

        JS('''
        inputfield.addEventListener("focus", function(evt){
            self.show();
        });

        inputfield.addEventListener("input", function(evt){
            self.update();
        });

        background.addEventListener("click", function(evt){
            if (evt.target == background){
                self.hide();
            }
        });

        close_button.addEventListener("click", function(evt){
            self.hide();
        });
        ''')

        self.t_head = DOM.getElementById('team_search_head')
        self.t_body = DOM.getElementById('team_search_body')

        self.body = UIObject(Element=DOM.getElementById('body'))
        self.open = False

        self.generate()
        self.update()
        self.ds.add_select_handler(self.select_handler)

    def generate(self):
        self.sel = dict()
        self.cnt = dict()

        for t_id in self.ds.teams.iterkeys():
            self.sel[t_id] = 0
            self.cnt[t_id] = 0

        for u_id, user in self.ds.users.iteritems():
            if user['team']:
                self.cnt[user['team']] += 1

        inner_html = ''
        for t_id, team in sorted(self.ds.teams.iteritems(),
                                 key=lambda a: a[1]['name']):
            # FIXME hardcoded flag path
            inner_html += '''
<div class="item" id="''' + t_id + '''">
    <input type="checkbox" id="''' + t_id + '''_check" />
    <label for="''' + t_id + '''_check">
        <img class="flag" src="/flags/''' + t_id + '''" />
        ''' + team['name'] + '''
    </label>
</div>'''
        DOM.setInnerHTML(self.t_body, inner_html)

        for t_id, team in self.ds.teams.iteritems():
            elem = DOM.getElementById(t_id + '_check')
            JS('''
            elem.addEventListener('change', self.callback_factory(t_id, elem))
            ''')

    def select_handler(self, u_id, flag):
        user = self.ds.users[u_id]

        if not user['team']:
            return

        if flag:
            self.sel[user['team']] += 1
        else:
            self.sel[user['team']] -= 1

        elem = DOM.getElementById(user['team'] + '_check')
        if self.sel[user['team']] == self.cnt[user['team']]:
            JS('elem.checked = true;')
            JS('elem.indeterminate = false;')
        elif self.sel[user['team']] > 0:
            JS('elem.checked = false;')
            JS('elem.indeterminate = true;')
        else:
            JS('elem.checked = false;')
            JS('elem.indeterminate = false;')

    def show(self):
        if not self.open:
            self.body.addStyleName('team_search')
            self.open = True

    def hide(self):
        if self.open:
            self.body.removeStyleName('team_search')
            self.open = False

    def update(self):
        inputfield = DOM.getElementById('team_search_input')
        search_text = DOM.getAttribute(inputfield, 'value')

        if search_text == '':
            for t_id, team in self.ds.teams.iteritems():
                el = UIObject(Element=DOM.getElementById(t_id))
                el.removeStyleName('hidden')
        else:
            for t_id, team in self.ds.teams.iteritems():
                if re.search(search_text.lower(), team['name'].lower()):
                    el = UIObject(Element=DOM.getElementById(t_id))
                    el.removeStyleName('hidden')
                else:
                    el = UIObject(Element=DOM.getElementById(t_id))
                    el.addStyleName('hidden')

    def callback_factory(self, t_id, elem):
        def result():
            status = DOM.getBooleanAttribute(elem, 'checked')
            for u_id, user in self.ds.users.iteritems():
                if user['team'] == t_id:
                    self.ds.set_selected(u_id, status)
        return result
