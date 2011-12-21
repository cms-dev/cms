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

from SubmissionStore import SubmissionStore
import Chart

from pyjamas.Canvas.GWTCanvas import GWTCanvas
from pyjamas.ui.UIObject import UIObject
from pyjamas.ui.FocusWidget import FocusWidget
from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.FlowPanel import FlowPanel
from pyjamas.ui.Label import Label
from pyjamas.ui.HTML import HTML
from pyjamas.ui.Image import Image

from pyjamas import Window
from pyjamas import DOM

from __pyjamas__ import JS

import math
import time


JS('''
function round_to_str(value) {
    value *= 100;
    value = Math.round(value);
    value /= 100;
    return value.toString();
}
''')

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


class UserDetail(object):
    def __init__(self, ds, hs):
        self.ds = ds
        self.hs = hs

        self.body = UIObject(Element=DOM.getElementById('body'))

        JS('''
        var background = UserDetail['DOM'].getElementById("user_detail_background")
        background.addEventListener("click", function(evt) {
            if (evt.target == background) {
                self.hide();
            }
        });
        ''')

        JS('''
        UserDetail['DOM'].getElementById("user_detail_close").addEventListener("click", function(evt) {
            self.hide();
        });
        ''')

        self.f_name_label = DOM.getElementById('user_detail_f_name')
        self.l_name_label = DOM.getElementById('user_detail_l_name')
        self.team_label = DOM.getElementById('user_detail_team')
        self.team_image = DOM.getElementById('user_detail_flag')
        self.face_image = DOM.getElementById('user_detail_face')
        self.title_label = DOM.getElementById('user_detail_title')

        self.scores = DOM.getElementById('user_detail_scores')
        self.subm_table = DOM.getElementById('user_detail_submissions')

        self.score_chart = GWTCanvas(940, 250, 940, 250)
        self.rank_chart = GWTCanvas(940, 250, 940, 250)

        chart_panel = FlowPanel(Element=DOM.getElementById('user_detail_charts'),
                                StyleName='charts')
        self.score_chart = GWTCanvas(940, 250, 940, 250)
        self.rank_chart = GWTCanvas(940, 250, 940, 250)
        chart_panel.add(self.score_chart)
        chart_panel.add(HTML("<br/>"))
        chart_panel.add(self.rank_chart)

    def show(self, user_id):
        JS('''
        self.user_id = user_id
        self.user = self.ds.users[user_id]
        ''')
        self.data_fetched = 0
        self.hs.request_update(self.history_callback)
        SubmissionStore().request_update(self.user_id, self.submits_callback)

    def history_callback(self):
        JS('''
        self.task_s = new Object();
        self.task_r = new Object();
        for (var t_id in self.ds.tasks) {
            self.task_s[t_id] = self.hs.get_score_history_for_task(self.user_id, t_id);
            self.task_r[t_id] = self.hs.get_rank_history_for_task(self.user_id, t_id);
        }

        self.contest_s = new Object();
        self.contest_r = new Object();
        for (var c_id in self.ds.contests) {
            self.contest_s[c_id] = self.hs.get_score_history_for_contest(self.user_id, c_id);
            self.contest_r[c_id] = self.hs.get_rank_history_for_contest(self.user_id, c_id);
        }

        self.global_s = self.hs.get_score_history(self.user_id);
        self.global_r = self.hs.get_rank_history(self.user_id);
        ''')

        self.data_fetched += 1
        self.do_show()

    def submits_callback(self, data):
        JS('''
        self.submissions = new Object();
        for (var t_id in self.ds.tasks) {
            self.submissions[t_id] = new Array();
        }
        for (var i = 0; i < data.length; i += 1) {
            var submission = data[i];
            self.submissions[submission['task']].push(submission);
        }
        ''')

        self.data_fetched += 1
        self.do_show()

    def do_show(self):
        if self.data_fetched == 2:
            JS('''
            self.f_name_label.innerHTML = self.user["f_name"];
            self.l_name_label.innerHTML = self.user["l_name"];
            self.face_image.setAttribute("src", "/faces/" + self.user_id);

            if (self.user["team"]) {
                self.team_label.innerHTML = self.ds.teams[self.user["team"]]["name"];
                self.team_image.setAttribute("src", '/flags/' + self.user['team']);
                // FIXME classList!!
                self.team_image.classList.remove("hidden");
            } else {
                self.team_label.innerHTML = "";
                // FIXME classList!!
                self.team_image.classList.add("hidden");
            }
            ''')

            JS('''
            var s = "<tr class=\\"global\\"> \
                        <td>Global</td> \
                        <td>" + (self.global_s.length > 0 ? round_to_str(self.global_s[self.global_s.length-1][1]) : 0) + "</td> \
                        <td>" + (self.global_r.length > 0 ? self.global_r[self.global_r.length-1][1] : 1) + "</td> \
                        <td><a>Show</a></td> \
                    </tr>";

            var contests = self.ds.contest_list;
            for (var i in contests) {
                var contest = contests[i];
                var c_id = contest["key"];

                s += "<tr class=\\"contest\\"> \
                         <td>" + contest['name'] + "</td> \
                         <td>" + (self.contest_s[c_id].length > 0 ? round_to_str(self.contest_s[c_id][self.contest_s[c_id].length-1][1]) : 0) + "</td> \
                         <td>" + (self.contest_r[c_id].length > 0 ? self.contest_r[c_id][self.contest_r[c_id].length-1][1] : 1) + "</td> \
                         <td><a>Show</a></td> \
                      </tr>"

                var tasks = contest["tasks"];
                for (var j in tasks) {
                    var task = tasks[j];
                    var t_id = task["key"];

                    s += "<tr class=\\"task\\"> \
                             <td>" + task['name'] + "</td> \
                             <td>" + (self.task_s[t_id].length > 0 ? round_to_str(self.task_s[t_id][self.task_s[t_id].length-1][1]) : 0) + "</td> \
                             <td>" + (self.task_r[t_id].length > 0 ? self.task_r[t_id][self.task_r[t_id].length-1][1] : 1) + "</td> \
                             <td><a>Show</a></td> \
                          </tr>"
                }
            }

            self.scores.innerHTML = s;

            self.active = null;

            var element = self.scores.children[0].children[3];
            element.addEventListener("click", self.callback_global_factory(element));

            var row_idx = 1;
            var contests = self.ds.contest_list;
            for (var i in contests) {
                var contest = contests[i];
                var c_id = contest["key"];

                var element = self.scores.children[row_idx].children[3];
                element.addEventListener("click", self.callback_contest_factory(element, c_id));
                row_idx += 1;

                var tasks = contest["tasks"];
                for (var j in tasks) {
                    var task = tasks[j];
                    var t_id = task["key"];

                    var element = self.scores.children[row_idx].children[3];
                    element.addEventListener("click", self.callback_task_factory(element, t_id));
                    row_idx += 1;
                }
            }

            self.callback_global_factory(self.scores.children[0].children[3])(null);
            ''')

            self.body.addStyleName("user_panel")

    def callback_global_factory(self, widget):
        JS('''function callback(evt) {
            if (self.active !== null) {
                self.active.classList.remove("active");
            }
            self.active = widget;
            self.active.classList.add("active");

            self.title_label.innerHTML = "Global";
            self.subm_table.innerHTML = "";
            ''')

        intervals = []
        b = 0
        e = 0
        JS('''/* ECCOMI */
        for (var i = 0; i < self.ds.contest_list.length; i += 1)
        {
            b = self.ds.contest_list[i]["begin"];
            e = self.ds.contest_list[i]["end"];
            while (i+1 < self.ds.contest_list.length && self.ds.contest_list[i+1]["begin"] <= e) {
                i += 1;
                e = (e > self.ds.contest_list[i]["end"] ? e : self.ds.contest_list[i]["end"]);
            }
            intervals.append(pyjslib.tuple([b, e]));
        }
        ''')

        score = 0
        JS('''
        for (var t_id in self.ds.tasks) {
            score += self.ds.tasks[t_id]["score"];
        }
        ''')
        users = JS('Object.keys(self.ds.users).length')

        Chart.draw_chart(self.score_chart, # canvas object
            0, score, 0, 0, # y_min, y_max, x_default, h_default
            intervals, # intervals
            JS('self.global_s'), # data
            (102, 102, 238), # color
            [score*1/4, # markers
             score*2/4,
             score*3/4])
        Chart.draw_chart(self.rank_chart,
            users, 1, 1, users-1,
            intervals,
            JS('self.global_r'),
            (210, 50, 50),
            [JS('Math.ceil (users/12)'),
             JS('Math.ceil (users/4 )'),
             JS('Math.floor(users/2 )')])

        JS('''
        }
        return callback;
        ''')

    def callback_task_factory(self, widget, task_id):
        JS('''function callback(evt) {
            if (self.active != null) {
                self.active.classList.remove("active");
            }
            self.active = widget;
            self.active.classList.add("active");

            self.title_label.innerHTML = self.ds.tasks[task_id]["name"];
            self.subm_table.innerHTML = self.make_submission_table(task_id);
            ''')

        task = JS('self.ds.tasks[task_id]')
        contest = JS('self.ds.contests[task["contest"]]')
        score = JS('task["score"]')
        users = JS('Object.keys(self.ds.users).length')

        Chart.draw_chart(self.score_chart, # canvas object
            0, score, 0, 0, # y_min, y_max, x_default, h_default
            [(JS('contest["begin"]'), JS('contest["end"]'))], # intervals
            JS('self.task_s[task_id]'), # data
            (102, 102, 238), # color
            [score*1/4, # markers
             score*2/4,
             score*3/4])
        Chart.draw_chart(self.rank_chart,
            users, 1, 1, users-1,
            [(JS('contest["begin"]'), JS('contest["end"]'))],
            JS('self.task_r[task_id]'),
            (210, 50, 50),
            [JS('Math.ceil (users/12)'),
             JS('Math.ceil (users/4 )'),
             JS('Math.floor(users/2 )')])

        JS('''
        }
        return callback;
        ''')

    def callback_contest_factory(self, widget, contest_id):
        JS('''function callback(evt) {
            if (self.active !== null) {
                self.active.classList.remove("active");
            }
            self.active = widget;
            self.active.classList.add("active");

            self.title_label.innerHTML = self.ds.contests[contest_id]["name"];
            self.subm_table.innerHTML = "";
            ''')

        contest = JS('self.ds.contests[contest_id]')
        score = 0
        JS('''
        for (var i in contest["tasks"]) {
            score += contest["tasks"][i]["score"];
        }
        ''')
        users = JS('Object.keys(self.ds.users).length')

        Chart.draw_chart(self.score_chart, # canvas object
            0, score, 0, 0, # y_min, y_max, x_default, h_default
            [(JS('contest["begin"]'), JS('contest["end"]'))], # intervals
            JS('self.contest_s[contest_id]'), # data
            (102, 102, 238), # color
            [score*1/4, # markers
             score*2/4,
             score*3/4])
        Chart.draw_chart(self.rank_chart,
            users, 1, 1, users-1,
            [(JS('contest["begin"]'), JS('contest["end"]'))],
            JS('self.contest_r[contest_id]'),
            (210, 50, 50),
            [JS('Math.ceil (users/12)'),
             JS('Math.ceil (users/4 )'),
             JS('Math.floor(users/2 )')])

        JS('''
        }
        return callback;
        ''')

    def make_submission_table(self, task_id):
        JS('''
        var res = " \
            <thead> \
                <tr> \
                    <td>Time</td> \
                    <td>Score</td> \
                    <td>Token</td> \
                    " + (self.ds.tasks[task_id]['extra_headers'].length > 0 ? "<td>" + self.ds.tasks[task_id]['extra_headers'].join("</td><td>") + "</td>" : "") + " \
                </tr> \
            </thead><tbody>";

        if (self.submissions[task_id].length == 0) {
            res += "<tr><td colspan=\\"" + (3 + self.ds.tasks[task_id]['extra_headers'].length) + "\\">No Submissions</td></tr>";
        } else {
            for (var i in self.submissions[task_id]) {
                var submission = self.submissions[task_id][i];
                time = submission["time"] - self.ds.contests[self.ds.tasks[task_id]["contest"]]["begin"];
                time = format_time(time);
                res += " \
                    <tr> \
                        <td>" + time + "</td> \
                        <td>" + round_to_str(submission['score']) + "</td> \
                        <td>" + (submission["token"] ? 'Yes' : 'No') + "</td> \
                        " + (submission["extra"].length > 0 ? "<td>" + submission["extra"].join("</td><td>") + "</td>" : "") + " \
                    </tr>";
            }
        }
        res += "</tbody>";
        return res;
        ''')

    def hide(self, widget):
        self.body.removeStyleName("user_panel")
