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


class UserPanel(object):
    def __init__(self, ds, hs):
        self.ds = ds
        self.hs = hs

        self.body = UIObject(Element=DOM.getElementById('body'))

        background = DOM.getElementById('UserPanel_top')

        JS('''
        background.addEventListener("click", function(evt){
            if (evt.target == background){
                self.hide();
            }
        });
        ''')

        # this is how it should be done
        self.close_button = FocusWidget(DOM.getElementById('UserPanel_close'))
        self.close_button.addClickListener(self.hide)
        DOM.setEventListener(DOM.getElementById('UserPanel_close'), self.close_button)

        # FIXME these is how it shouldn't be done
        self.f_name_label = DOM.getElementById('UserPanel_f_name')
        self.l_name_label = DOM.getElementById('UserPanel_l_name')
        self.team_label = DOM.getElementById('UserPanel_team')
        self.team_image = DOM.getElementById('UserPanel_flag')
        self.face_image = DOM.getElementById('UserPanel_face')
        self.title_label = DOM.getElementById('UserPanel_title')

        self.summary = DOM.getElementById('UserPanel_summary')
        self.submits = DOM.getElementById('UserPanel_submits')

        chart_panel = FlowPanel(Element=DOM.getElementById('UserPanel_charts'),
                                StyleName='charts')
        self.score_chart = GWTCanvas(940, 250, 940, 250)
        self.rank_chart = GWTCanvas(940, 250, 940, 250)
        chart_panel.add(self.score_chart)
        chart_panel.add(HTML("<br/>"))
        chart_panel.add(self.rank_chart)

    def show(self, user_id):
        self.user_id = user_id
        self.user = self.ds.users[user_id]
        self.data_fetched = 0
        self.hs.request_update(self.history_callback)
        SubmissionStore().request_update(self.user_id, self.submits_callback)

    def history_callback(self):
        self.task_s = dict()
        self.task_r = dict()
        for t in self.ds.tasks.iterkeys():
            self.task_s[t] = self.hs.get_score_history_for_task(self.user_id, t)
            self.task_r[t] = self.hs.get_rank_history_for_task(self.user_id, t)

        self.contest_s = dict()
        self.contest_r = dict()
        for c in self.ds.contests.iterkeys():
            self.contest_s[c] = self.hs.get_score_history_for_contest(self.user_id, c)
            self.contest_r[c] = self.hs.get_rank_history_for_contest(self.user_id, c)

        self.global_s = self.hs.get_score_history(self.user_id)
        self.global_r = self.hs.get_rank_history(self.user_id)

        self.data_fetched += 1
        self.do_show()

    def submits_callback(self, data):
        self.submissions = dict()
        for i in data:
            if i['task'] not in self.submissions:
                self.submissions[i['task']] = [i]
            else:
                self.submissions[i['task']].append(i)
        self.data_fetched += 1
        self.do_show()

    def do_show(self):
        if self.data_fetched == 2:

            # FIXME possible security issue: code injection
            self.f_name_label.innerHTML = self.user['f_name']
            self.l_name_label.innerHTML = self.user['l_name']
            DOM.setAttribute(self.face_image, 'src', '/faces/' + self.user_id)

            if self.user['team']:
                self.team_label.innerHTML = self.ds.teams[self.user['team']]['name']
                DOM.setAttribute(self.team_image, 'src', '/flags/' + self.user['team'])
                JS('''
                self.team_image.classList.remove('hidden');
                ''')
            else:
                self.team_label.innerHTML = ''
                JS('''
                self.team_image.classList.add('hidden');
                ''')

            s =  """<tr class="global">
                        <td>Global</td>
                        <td>"""+str(self.global_s[-1][1] if self.global_s else 0)+"""</td>
                        <td>"""+str(self.global_r[-1][1] if self.global_r else 1)+"""</td>
                        <td><a>Show</a></td>
                    </tr>"""

            for c_id, contest in self.ds.iter_contests():
                s += """<tr class="contest">
                            <td>"""+contest['name']+"""</td>
                            <td>"""+str(self.contest_s[c_id][-1][1] if self.contest_s[c_id] else 0)+"""</td>
                            <td>"""+str(self.contest_r[c_id][-1][1] if self.contest_r[c_id] else 1)+"""</td>
                            <td><a>Show</a></td>
                        </tr>"""
                for t_id, task in self.ds.iter_tasks():
                    if task['contest'] is c_id:
                        s += """<tr class="task">
                                    <td>"""+task['name']+"""</td>
                                    <td>"""+str(self.task_s[t_id][-1][1] if self.task_s[t_id] else 0)+"""</td>
                                    <td>"""+str(self.task_r[t_id][-1][1] if self.task_r[t_id] else 1)+"""</td>
                                    <td><a>Show</a></td>
                                </tr>"""
            self.summary.innerHTML = s

            self.active = None

            glob_show = FocusWidget(DOM.getChild(DOM.getChild(self.summary, 0), 3))
            glob_show.addClickListener(self.callback_global)
            DOM.setEventListener(DOM.getChild(DOM.getChild(self.summary, 0), 3), glob_show)

            i = 1
            for c_id, contest in self.ds.iter_contests():
                cont_show = FocusWidget(DOM.getChild(DOM.getChild(self.summary, i), 3))
                cont_show.addClickListener(self.callback_factory_contest(c_id))
                DOM.setEventListener(DOM.getChild(DOM.getChild(self.summary, i), 3), cont_show)
                i += 1
                for t_id, task in self.ds.iter_tasks():
                    if task['contest'] is c_id:
                        task_show = FocusWidget(DOM.getChild(DOM.getChild(self.summary, i), 3))
                        task_show.addClickListener(self.callback_factory_task(t_id))
                        DOM.setEventListener(DOM.getChild(DOM.getChild(self.summary, i), 3), task_show)
                        i += 1

            self.callback_global(glob_show)

            self.body.addStyleName("user_panel")

    def callback_global(self, widget):
        self.title_label.innerHTML = 'Global'
        self.submits.innerHTML = ''

        if self.active:
            self.active.removeStyleName("active")
        self.active = widget
        self.active.addStyleName("active")

        intervals = []
        contests = sorted(self.ds.contests.itervalues(), key=lambda c: c['begin'])
        i = 0
        b = 0
        e = 0
        while i < len(contests):
            b = contests[i]['begin']
            e = contests[i]['end']
            while i+1 < len(contests) and contests[i+1]['begin'] <= e:  # someone may want only a <
                i += 1
                e = max(e, contests[i]['end'])
            intervals.append((b, e))
            i += 1

        score = sum([t['score'] for t in self.ds.tasks.itervalues()])

        Chart.draw_chart(self.score_chart, 0, score, 0, 0,
                intervals, self.hs.get_score_history(self.user_id),
                (102, 102, 238), [score/4, score/2, score*3/4, score])
        Chart.draw_chart(self.rank_chart, len(self.ds.users), 1, 1, len(self.ds.users),
                intervals, self.hs.get_rank_history(self.user_id),
                (210, 50, 50), [1, math.ceil(len(self.ds.users)/12), math.ceil(len(self.ds.users)/4), math.floor(len(self.ds.users)/2)])

    def callback_factory_task(self, task_id):
        def result(widget):
            if self.active:
                self.active.removeStyleName("active")
            self.active = widget
            self.active.addStyleName("active")

            self.title_label.innerHTML = self.ds.tasks[task_id]['name']
            s = """<thead>
                <tr>
                    <td>Time</td>
                    <td>Score</td>
                    <td>Token</td>
                    """ + '\n'.join(['<td>'+x+'</td>' for x in self.ds.tasks[task_id]['extra_headers']]) + """
                </tr>
            </thead><tbody>"""
            if task_id not in self.submissions or not self.submissions[task_id]:
                s += '<tr><td colspan="'+str(3+len(self.ds.tasks[task_id]['extra_headers']))+'">No Submissions</td></tr>'
            else:
                for i in self.submissions[task_id]:
                    time = i['time'] - self.ds.contests[self.ds.tasks[task_id]['contest']]['begin']
                    time = '%02d' % (time//3600) + ':' + '%02d' % (time//60%60) + ':' + '%02d' % (time%60)
                    s += '<tr><td>'+time+'''</td>
                    <td>'''+str(i['score'])+'''</td>
                    <td>'''+('Yes' if i['token'] else 'No')+'''</td>
                    ''' + ''.join(['<td>'+x+'</td>' for x in i['extra']]) + '</tr>'
            s += '</tbody>'
            self.submits.innerHTML = s
            
            task = self.ds.tasks[task_id]
            contest = self.ds.contests[task['contest']]
            score = task['score']
            Chart.draw_chart(self.score_chart, 0, score, 0, 0,
                [(contest['begin'], contest['end'])],
                self.hs.get_score_history_for_task(self.user_id, task_id),
                (102, 102, 238), [score/4, score/2, score*3/4, score])
            Chart.draw_chart(self.rank_chart, len(self.ds.users), 1, 1, len(self.ds.users),
                [(contest['begin'], contest['end'])],
                self.hs.get_rank_history_for_task(self.user_id, task_id),
                (210, 50, 50), [1, math.ceil(len(self.ds.users)/12), math.ceil(len(self.ds.users)/4), math.floor(len(self.ds.users)/2)])
        return result

    def callback_factory_contest(self, contest_id):
        def result(widget):
            if self.active:
                self.active.removeStyleName("active")
            self.active = widget
            self.active.addStyleName("active")

            self.title_label.innerHTML = self.ds.contests[contest_id]['name']
            self.submits.innerHTML = ''

            contest = self.ds.contests[contest_id]
            score = sum([t['score'] for t in self.ds.tasks.itervalues()
                         if t['contest'] == contest_id])
            Chart.draw_chart(self.score_chart, 0, score, 0, 0,
                [(contest['begin'], contest['end'])],
                self.hs.get_score_history_for_contest(self.user_id, contest_id),
                (102, 102, 238), [score/4, score/2, score*3/4, score])
            Chart.draw_chart(self.rank_chart, len(self.ds.users), 1, 1, len(self.ds.users),
                [(contest['begin'], contest['end'])],
                self.hs.get_rank_history_for_contest(self.user_id, contest_id),
                (210, 50, 50), [1, math.ceil(len(self.ds.users)/12), math.ceil(len(self.ds.users)/4), math.floor(len(self.ds.users)/2)])
        return result

    def hide(self, widget):
        self.body.removeStyleName("user_panel")
