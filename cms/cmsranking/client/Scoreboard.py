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

from pyjamas.ui.UIObject import UIObject
from pyjamas.ui.FocusWidget import FocusWidget

from pyjamas import Window
from pyjamas import DOM

from __pyjamas__ import JS


JS('''
function round_to_str(value) {
    value *= 100;
    value = Math.round(value);
    value /= 100;
    return value.toString();
}
''')


class omni_container(object):
    def __contains__(self, a):
        return True


class Scoreboard(object):
    def __init__(self, ds, up):
        self.ds = ds
        self.up = up
        self.expanded = omni_container()

        self.tcols_el = DOM.getElementById('Scoreboard_cols')
        self.thead_el = DOM.getElementById('Scoreboard_head')
        self.tbody_el = DOM.getElementById('Scoreboard_body')

        self.ds.add_select_handler(self.select_handler)

        cols_html = self.make_cols(t_key, c_key)
        head_html = self.make_head(t_key, c_key)

        DOM.setInnerHTML(self.tcols_el, cols_html)
        DOM.setInnerHTML(self.thead_el, head_html)

        self.update()


    def make_cols(self):
        result = ''
        JS('''
        var contests = self.ds.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];
                result += "<col class=\\"score task\\" />";
            }
            result += "<col class=\\"score contest\\" />"
        }
        ''')

        return result


    def make_head(self):
        result = '''
<tr>
    <th class="sel"></th>
    <th class="rank">Rank</th>
    <th class="f_name">First Name</th>
    <th class="l_name">Last Name</th>
    <th class="team">Team</th>'''

        JS('''
        var contests = self.ds.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];
                result += "<th class=\\"score task\\"><abbr title=\\"" + \
                    task["name"] + "\\">" + task["name"][0] + "</abbr></th>";
            }
            result += "<th class=\\"score contest\\">" + contest["name"] + "</th>";
        }
        result += "<th class=\\"score global\\">Global</th></tr>";
        ''')

        return result


    def get_score_class(self, score, max_score):
        if score == 0:
            return "score_0"
        elif score == max_score:
            return "score_100"
        else:
            rel_score = int(score / max_score * 10) * 10
            return "score_%d_%d" % (rel_score, rel_score + 10)


    def make_row(self, u_id, user, rank, t_key=None, c_key=None):
        result = '''
<tr id="''' + u_id + '"' + (' class="selected"' if self.ds.get_selected(u_id) else '') + '''>
    <td class="sel">
        <input type="checkbox"''' + ('checked' if self.ds.get_selected(u_id) else '') + ''' />
    </td>
    <td class="rank">''' + str(rank) + '''</td>
    <td class="f_name">''' + JS("user['f_name']") + '''</td>
    <td class="l_name">''' + JS("user['l_name']") + '''</td>'''

        if JS("user['team']"):
            # FIXME: hardcoded flag path
            result += '''<td class="team"><img src="/flags/''' + JS("user['team']") + '''" title="''' + JS("self.ds.teams[user['team']]['name']") + '''" /></td>'''
        else:
            result += '''<td class="team"></td>'''

        global_score = 0.0
        JS('''
        var contests = self.ds.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
        ''')
        contest_score = 0.0
        JS('''
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];
        ''')
        task_score = JS("self.ds.tasks[t_id]['score']");
        score_class = self.get_score_class(JS("self.ds.get_score_t(u_id, t_id)"), task_score)
        if JS("t_id") == t_key:
            score_class += ' sort_key'
        result += '''
    <td class="score task ''' + score_class + '''">''' + JS("round_to_str(self.ds.get_score_t(u_id, t_id))") + '''</td>'''
        contest_score += task_score
        JS('''
            }
        ''')
        score_class = self.get_score_class(JS("self.ds.get_score_c(u_id, c_id)"), contest_score)
        if JS("c_id") == c_key:
            score_class += ' sort_key'
        result += '''
    <td class="score contest ''' + score_class + '''">''' + JS("round_to_str(self.ds.get_score_c(u_id, c_id))") + '''</td>'''
        global_score += contest_score
        JS('''
        }
        ''')
        score_class = self.get_score_class(self.ds.get_score(u_id), global_score)
        if t_key is None and c_key is None:
            score_class += ' sort_key'
        result += '''
    <td class="score global ''' + score_class + '''">''' + JS("round_to_str(self.ds.get_score(u_id))") + '''</td>
</tr>'''

        return result


    def make_body(self, t_key=None, c_key=None):
        JS('''
        var users = new Array();
        for (u_id in self.ds.users) {
            user = self.ds.users[u_id];
            if (t_key !== null) {
                user["score1"] = self.ds.get_score_t(u_id, t_key);
                user["score2"] = self.ds.get_score(u_id);
            } else if (c_key !== null) {
                user["score1"] = self.ds.get_score_c(u_id, c_key);
                user["score2"] = self.ds.get_score(u_id);
            } else {
                user["score1"] = self.ds.get_score(u_id);
                user["score2"] = self.ds.get_score(u_id);
            }
            users.push(user);
        }
        users.sort(function (a, b) {
            if ((a["score1"] > b["score1"]) || ((a["score1"] == b["score1"]) &&
               ((a["score2"] > b["score2"]) || ((a["score2"] == b["score2"]) &&
               ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
               ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
               (a["key"] < b["key"]))))))))) {
                return -1;
            } else {
                return +1;
            }     
        });
        ''')

        result = ''

        JS('''
        var prev_score =  null;
        var rank = 0;
        var equal = 1;

        for (var i in users) {
            user = users[i];
            u_id = user["key"];
            score = user["score1"];

            if (score === prev_score) {
                equal += 1;
            } else {
                prev_score = score;
                rank += equal;
                equal = 1;
            }

            result += self.make_row(u_id, user, rank, t_key, c_key)
        }
        ''')

        return result


    def update(self, t_key=None, c_key=None):
        body_html = self.make_body(t_key, c_key)

        DOM.setInnerHTML(self.tbody_el, body_html)


        # create callbacks for selection
        JS('''
        for (var u_id in self.ds.users) {
            var check = Scoreboard['DOM'].getElementById(u_id).children[0].children[0];
            check.addEventListener('change', self.select_factory(u_id));
        }
        ''')

        # create callbacks for UserPanel
        JS('''
        for (var u_id in self.ds.users) {
            var row = Scoreboard['DOM'].getElementById(u_id);
            row.children[2].addEventListener('click', self.user_callback_factory(u_id));
            row.children[3].addEventListener('click', self.user_callback_factory(u_id));
        }
        ''')

        # create callbacks for sorting
        idx = 5
        row_el = DOM.getChild(self.thead_el, 0)
        JS('''
        var contests = self.ds.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];
        ''')
        elem = DOM.getChild(row_el, idx)
        widget = FocusWidget(elem)
        widget.addClickListener(self.sort_task_factory(JS("t_id")))
        DOM.setEventListener(elem, widget)
        idx += 1
        JS('''
            }
        ''')
        elem = DOM.getChild(row_el, idx)
        widget = FocusWidget(elem)
        widget.addClickListener(self.sort_contest_factory(JS("c_id")))
        DOM.setEventListener(elem, widget)
        idx += 1
        JS('''
        }
        ''')
        elem = DOM.getChild(row_el, idx)
        widget = FocusWidget(elem)
        widget.addClickListener(self.sort_global_factory())
        DOM.setEventListener(elem, widget)

    def select_handler(self, u_id, flag):
        row = DOM.getElementById(u_id)
        cell = DOM.getChild(row, 0)
        check = DOM.getChild(cell, 0)
        # FIXME classList is not supported by all browsers
        JS('''
        if (flag) {
            row.classList.add("selected")
        } else {
            row.classList.remove("selected")
        }
        check.checked = flag
        ''')


    def select_factory(self, u_id):
        def result():
            row = DOM.getElementById(u_id)
            cell = DOM.getChild(row, 0)
            check = DOM.getChild(cell, 0)
            self.ds.set_selected(u_id, DOM.getBooleanAttribute(check, 'checked'))
        return result


    def user_callback_factory(self, u_id):
        def result():
            self.up.show(u_id)
        return result


    def sort_task_factory(self, t_id):
        def result():
            self.update(t_key=t_id)
        return result


    def sort_contest_factory(self, c_id):
        def result():
            self.update(c_key=c_id)
        return result


    def sort_global_factory(self):
        def result():
            self.update()
        return result
