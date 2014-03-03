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

// format_time is defined in TimeView

var UserDetail = new function () {
    var self = this;

    self.init = function () {
        $("#UserDetail_bg").click(function (event) {
            if (event.target == event.currentTarget) {
                self.hide();
            }
        });

        $("#UserDetail_close").click(function () {
            self.hide();
        });

        $(document).keyup(function (event) {
            if (event.keyCode == 27) { // ESC key
                self.hide();
            }
        });

        self.f_name_label = $('#UserDetail_f_name');
        self.l_name_label = $('#UserDetail_l_name');
        self.team_label = $('#UserDetail_team');
        self.flag_image = $('#UserDetail_flag');
        self.face_image = $('#UserDetail_face');
        self.title_label = $('#UserDetail_title');

        self.navigator = $('#UserDetail_navigator table tbody');
        self.submission_table = $('#UserDetail_submissions');

        self.score_chart = $('#UserDetail_score_chart')[0];
        self.rank_chart = $('#UserDetail_rank_chart')[0];

        self.navigator.on("click", "td.btn", function () {
            if (self.active !== null) {
                self.active.removeClass("active");
            }
            self.active = $(this).parent();
            self.active.addClass("active");

            if (self.active.hasClass('global')) {
                self.show_global();
            } else if (self.active.hasClass('contest')) {
                self.show_contest(self.active.attr('data-contest'));
            } else if (self.active.hasClass('task')) {
                self.show_task(self.active.attr('data-task'));
            }
        });
    };

    self.show = function (user_id) {
        self.user_id = user_id;
        self.user = DataStore.users[user_id];
        self.data_fetched = 0;
        HistoryStore.request_update(self.history_callback);

        $.ajax({
            url: Config.get_submissions_url(self.user_id),
            dataType: "json",
            success: self.submissions_callback,
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

    self.submissions_callback = function (data) {
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
            self.f_name_label.text(self.user["f_name"]);
            self.l_name_label.text(self.user["l_name"]);
            self.face_image.attr("src", Config.get_face_url(self.user_id));

            if (self.user["team"]) {
                self.team_label.text(DataStore.teams[self.user["team"]]["name"]);
                self.flag_image.attr("src", Config.get_flag_url(self.user['team']));
                self.flag_image.removeClass("hidden");
            } else {
                self.team_label.text("");
                self.flag_image.addClass("hidden");
            }

            var s = "<tr class=\"global\"> \
                        <td class=\"name\">Global</td> \
                        <td class=\"score\">" + (self.global_s.length > 0 ? round_to_str(self.global_s[self.global_s.length-1][1], DataStore.global_score_precision) : 0) + "</td> \
                        <td class=\"rank\">" + (self.global_r.length > 0 ? self.global_r[self.global_r.length-1][1] : 1) + "</td> \
                        <td class=\"btn\"><a>Show</a></td> \
                    </tr>";

            var contests = DataStore.contest_list;
            for (var i in contests) {
                var contest = contests[i];
                var c_id = contest["key"];

                s += "<tr class=\"contest\" data-contest=\"" + c_id +"\"> \
                         <td class=\"name\">" + contest['name'] + "</td> \
                         <td class=\"score\">" + (self.contest_s[c_id].length > 0 ? round_to_str(self.contest_s[c_id][self.contest_s[c_id].length-1][1], contest["score_precision"]) : 0) + "</td> \
                         <td class=\"rank\">" + (self.contest_r[c_id].length > 0 ? self.contest_r[c_id][self.contest_r[c_id].length-1][1] : 1) + "</td> \
                         <td class=\"btn\"><a>Show</a></td> \
                      </tr>"

                var tasks = contest["tasks"];
                for (var j in tasks) {
                    var task = tasks[j];
                    var t_id = task["key"];

                    s += "<tr class=\"task\" data-task=\"" + t_id +"\"> \
                             <td class=\"name\">" + task['name'] + "</td> \
                             <td class=\"score\">" + (self.task_s[t_id].length > 0 ? round_to_str(self.task_s[t_id][self.task_s[t_id].length-1][1], task["score_precision"]) : 0) + "</td> \
                             <td class=\"rank\">" + (self.task_r[t_id].length > 0 ? self.task_r[t_id][self.task_r[t_id].length-1][1] : 1) + "</td> \
                             <td class=\"btn\"><a>Show</a></td> \
                          </tr>"
                }
            }

            self.navigator.html(s);

            self.active = null;

            $('tr.global td.btn', self.navigator).click();

            $("#UserDetail_bg").addClass("open");
        }
    };

    self.show_global = function () {
        self.title_label.text("Global");
        self.submission_table.html("");

        var intervals = new Array();
        var b = 0;
        var e = 0;

        for (var i = 0; i < DataStore.contest_list.length; i += 1) {
            b = DataStore.contest_list[i]["begin"];
            e = DataStore.contest_list[i]["end"];
            while (i+1 < DataStore.contest_list.length && DataStore.contest_list[i+1]["begin"] <= e) {
                i += 1;
                e = (e > DataStore.contest_list[i]["end"] ? e : DataStore.contest_list[i]["end"]);
            }
            intervals.push([b, e]);
        }

        self.draw_charts(intervals, DataStore.global_max_score,
                         self.global_s, self.global_r);
    };

    self.show_contest = function (contest_id) {
        var contest = DataStore.contests[contest_id];

        self.title_label.text(contest["name"]);
        self.submission_table.html("");

        self.draw_charts([[contest["begin"], contest["end"]]], contest["max_score"],
                         self.contest_s[contest_id], self.contest_r[contest_id]);
    };

    self.show_task = function (task_id) {
        var task = DataStore.tasks[task_id];
        var contest = DataStore.contests[task["contest"]];

        self.title_label.text(task["name"]);
        self.submission_table.html(self.make_submission_table(task_id));

        self.draw_charts([[contest["begin"], contest["end"]]], task["max_score"],
                         self.task_s[task_id], self.task_r[task_id]);
    };

    self.draw_charts = function (ranges, max_score, history_s, history_r) {
        var users = DataStore.user_count;

        Chart.draw_chart(self.score_chart, // canvas object
            0, max_score, 0, 0, // y_min, y_max, x_default, h_default
            ranges, // intervals
            history_s, // data
            [102, 102, 238], // color
            [max_score*1/4, // markers
             max_score*2/4,
             max_score*3/4]);
        Chart.draw_chart(self.rank_chart, // canvas object
            users, 1, 1, users-1, // y_min, y_max, x_default, h_default
            ranges, // intervals
            history_r, // data
            [210, 50, 50], // color
            [Math.ceil (users/12), // markers
             Math.ceil (users/4 ),
             Math.floor(users/2 )]);
    };

    self.make_submission_table = function (task_id) {
        var res = " \
<table> \
    <thead> \
        <tr> \
            <td>Time</td> \
            <td>Score</td> \
            <td>Token</td> \
            " + (DataStore.tasks[task_id]['extra_headers'].length > 0 ? "<td>" + DataStore.tasks[task_id]['extra_headers'].join("</td><td>") + "</td>" : "") + " \
        </tr> \
    </thead> \
    <tbody>";

        if (self.submissions[task_id].length == 0) {
            res += " \
        <tr> \
            <td colspan=\"" + (3 + DataStore.tasks[task_id]['extra_headers'].length) + "\">no submissions</td> \
        </tr>";
        } else {
            for (var i in self.submissions[task_id]) {
                var submission = self.submissions[task_id][i];
                time = submission["time"] - DataStore.contests[DataStore.tasks[task_id]["contest"]]["begin"];
                time = format_time(time);
                res += " \
        <tr> \
            <td>" + time + "</td> \
            <td>" + round_to_str(submission['score'], DataStore.tasks[task_id]['score_precision']) + "</td> \
            <td>" + (submission["token"] ? 'Yes' : 'No') + "</td> \
            " + (submission["extra"].length > 0 ? "<td>" + submission["extra"].join("</td><td>") + "</td>" : "") + " \
        </tr>";
            }
        }
        res += " \
    </tbody> \
</table>";
        return res;
    };

    self.hide = function () {
        $("#UserDetail_bg").removeClass("open");
    };
};
