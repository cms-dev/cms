/* Programming contest management system
 * Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

function round_to_str(value) {
    value *= 100;
    value = Math.round(value);
    value /= 100;
    return value.toString();
}

function format_time(time) {
    var h = Math.floor(time / 3600);
    var m = Math.floor((time % 3600) / 60);
    var s = time % 60;
    m = m < 10 ? "0" + m : "" + m;
    s = s < 10 ? "0" + s : "" + s;
    return (h + ":" + m + ":" + s);
};

var UserDetail = new function () {
    var self = this;

    self.init = function () {
        $("#user_detail_background").click(function (event) {
            if (event.target == event.currentTarget) {
                self.hide();
            }
        });

        $("#user_detail_close").click(function () {
            self.hide();
        });

        self.f_name_label = document.getElementById('user_detail_f_name');
        self.l_name_label = document.getElementById('user_detail_l_name');
        self.team_label = document.getElementById('user_detail_team');
        self.team_image = document.getElementById('user_detail_flag');
        self.face_image = document.getElementById('user_detail_face');
        self.title_label = document.getElementById('user_detail_title');

        self.scores = document.getElementById('user_detail_scores');
        self.subm_table = document.getElementById('user_detail_submissions');

        self.score_chart = document.getElementById('user_detail_score_chart');
        self.rank_chart = document.getElementById('user_detail_rank_chart');
    };

    self.show = function (user_id) {
        self.user_id = user_id;
        self.user = DataStore.users[user_id];
        self.data_fetched = 0;
        HistoryStore.request_update(self.history_callback);

        $.ajax({
            url: Config.get_submissions_url(self.user_id),
            dataType: "json",
            success: self.submits_callback,
            error: function () {
                console.error("Error while getting the submissions for " + self.user_id); 
            }
        });
    };

    self.history_callback = function () {
        self.task_s = new Object();
        self.task_r = new Object();
        for (var t_id in DataStore.tasks) {
            self.task_s[t_id] = HistoryStore.get_score_history_for_task(self.user_id, t_id);
            self.task_r[t_id] = HistoryStore.get_rank_history_for_task(self.user_id, t_id);
        }

        self.contest_s = new Object();
        self.contest_r = new Object();
        for (var c_id in DataStore.contests) {
            self.contest_s[c_id] = HistoryStore.get_score_history_for_contest(self.user_id, c_id);
            self.contest_r[c_id] = HistoryStore.get_rank_history_for_contest(self.user_id, c_id);
        }

        self.global_s = HistoryStore.get_score_history(self.user_id);
        self.global_r = HistoryStore.get_rank_history(self.user_id);

        self.data_fetched += 1;
        self.do_show();
    }

    self.submits_callback = function (data) {
        self.submissions = new Object();
        for (var t_id in DataStore.tasks) {
            self.submissions[t_id] = new Array();
        }
        for (var i = 0; i < data.length; i += 1) {
            var submission = data[i];
            self.submissions[submission['task']].push(submission);
        }

        self.data_fetched += 1;
        self.do_show();
    };

    self.do_show = function () {
        if (self.data_fetched == 2) {
            self.f_name_label.innerHTML = self.user["f_name"];
            self.l_name_label.innerHTML = self.user["l_name"];
            self.face_image.setAttribute("src", Config.get_face_url(self.user_id));

            if (self.user["team"]) {
                self.team_label.innerHTML = DataStore.teams[self.user["team"]]["name"];
                self.team_image.setAttribute("src", Config.get_flag_url(self.user['team']));
                $(self.team_image).removeClass("hidden");
            } else {
                self.team_label.innerHTML = "";
                $(self.team_image).addClass("hidden");
            }

            var s = "<tr class=\"global\"> \
                        <td>Global</td> \
                        <td>" + (self.global_s.length > 0 ? round_to_str(self.global_s[self.global_s.length-1][1]) : 0) + "</td> \
                        <td>" + (self.global_r.length > 0 ? self.global_r[self.global_r.length-1][1] : 1) + "</td> \
                        <td><a>Show</a></td> \
                    </tr>";

            var contests = DataStore.contest_list;
            for (var i in contests) {
                var contest = contests[i];
                var c_id = contest["key"];

                s += "<tr class=\"contest\"> \
                         <td>" + contest['name'] + "</td> \
                         <td>" + (self.contest_s[c_id].length > 0 ? round_to_str(self.contest_s[c_id][self.contest_s[c_id].length-1][1]) : 0) + "</td> \
                         <td>" + (self.contest_r[c_id].length > 0 ? self.contest_r[c_id][self.contest_r[c_id].length-1][1] : 1) + "</td> \
                         <td><a>Show</a></td> \
                      </tr>"

                var tasks = contest["tasks"];
                for (var j in tasks) {
                    var task = tasks[j];
                    var t_id = task["key"];

                    s += "<tr class=\"task\"> \
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
            var contests = DataStore.contest_list;
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

            $("body").addClass("user_panel");
        }
    };

    self.callback_global_factory = function (widget) {
        function callback(evt) {
            if (self.active !== null) {
                $(self.active).removeClass("active");
            }
            self.active = widget;
            $(self.active).addClass("active");

            self.title_label.innerHTML = "Global";
            self.subm_table.innerHTML = "";

            var intervals = new Array();
            var b = 0;
            var e = 0;

            for (var i = 0; i < DataStore.contest_list.length; i += 1)
            {
                b = DataStore.contest_list[i]["begin"];
                e = DataStore.contest_list[i]["end"];
                while (i+1 < DataStore.contest_list.length && DataStore.contest_list[i+1]["begin"] <= e) {
                    i += 1;
                    e = (e > DataStore.contest_list[i]["end"] ? e : DataStore.contest_list[i]["end"]);
                }
                intervals.push([b, e]);
            }

            var score = DataStore.global_max_score;
            var users = Object.keys(DataStore.users).length;

            Chart.draw_chart(self.score_chart, // canvas object
                0, score, 0, 0, // y_min, y_max, x_default, h_default
                intervals, // intervals
                self.global_s, // data
                [102, 102, 238], // color
                [score*1/4, // markers
                 score*2/4,
                 score*3/4]);
            Chart.draw_chart(self.rank_chart,
                users, 1, 1, users-1,
                intervals,
                self.global_r,
                [210, 50, 50],
                [Math.ceil (users/12),
                 Math.ceil (users/4 ),
                 Math.floor(users/2 )]);
        }
        return callback;
    };

    self.callback_task_factory = function (widget, task_id) {
        function callback(evt) {
            if (self.active != null) {
                self.active.classList.remove("active");
            }
            self.active = widget;
            self.active.classList.add("active");

            self.title_label.innerHTML = DataStore.tasks[task_id]["name"];
            self.subm_table.innerHTML = self.make_submission_table(task_id);

            var task = DataStore.tasks[task_id];
            var contest = DataStore.contests[task["contest"]];

            var score = task["max_score"];
            var users = Object.keys(DataStore.users).length;

            Chart.draw_chart(self.score_chart, // canvas object
                0, score, 0, 0, // y_min, y_max, x_default, h_default
                [[contest["begin"], contest["end"]]], // intervals
                self.task_s[task_id], // data
                [102, 102, 238], // color
                [score*1/4, // markers
                 score*2/4,
                 score*3/4])
            Chart.draw_chart(self.rank_chart,
                users, 1, 1, users-1,
                [[contest["begin"], contest["end"]]],
                self.task_r[task_id],
                [210, 50, 50],
                [Math.ceil (users/12),
                 Math.ceil (users/4 ),
                 Math.floor(users/2 )])
        }

        return callback;
    };

    self.callback_contest_factory = function (widget, contest_id) {
        function callback(evt) {
            if (self.active !== null) {
                self.active.classList.remove("active");
            }
            self.active = widget;
            self.active.classList.add("active");

            self.title_label.innerHTML = DataStore.contests[contest_id]["name"];
            self.subm_table.innerHTML = "";

            var contest = DataStore.contests[contest_id];

            var score = contest["max_score"];
            var users = Object.keys(DataStore.users).length

            Chart.draw_chart(self.score_chart, // canvas object
                0, score, 0, 0, // y_min, y_max, x_default, h_default
                [[contest["begin"], contest["end"]]], // intervals
                self.contest_s[contest_id], // data
                [102, 102, 238], // color
                [score*1/4, // markers
                 score*2/4,
                 score*3/4])
            Chart.draw_chart(self.rank_chart,
                users, 1, 1, users-1,
                [[contest["begin"], contest["end"]]],
                self.contest_r[contest_id],
                [210, 50, 50],
                [Math.ceil (users/12),
                 Math.ceil (users/4 ),
                 Math.floor(users/2 )])
        }
        return callback;
    };

    self.make_submission_table = function (task_id) {
        var res = " \
            <thead> \
                <tr> \
                    <td>Time</td> \
                    <td>Score</td> \
                    <td>Token</td> \
                    " + (DataStore.tasks[task_id]['extra_headers'].length > 0 ? "<td>" + DataStore.tasks[task_id]['extra_headers'].join("</td><td>") + "</td>" : "") + " \
                </tr> \
            </thead><tbody>";

        if (self.submissions[task_id].length == 0) {
            res += "<tr><td colspan=\"" + (3 + DataStore.tasks[task_id]['extra_headers'].length) + "\">No Submissions</td></tr>";
        } else {
            for (var i in self.submissions[task_id]) {
                var submission = self.submissions[task_id][i];
                time = submission["time"] - DataStore.contests[DataStore.tasks[task_id]["contest"]]["begin"];
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
    };

    self.hide = function (widget) {
        $("body").removeClass("user_panel");
    };
};
