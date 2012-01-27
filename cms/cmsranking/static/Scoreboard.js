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

var Scoreboard = new function () {
    var self = this;

    self.init = function () {
        self.tcols_el = document.getElementById('Scoreboard_cols');
        self.thead_el = document.getElementById('Scoreboard_head');
        self.tbody_el = document.getElementById('Scoreboard_body');

        DataStore.add_select_handler(self.select_handler);

        var cols_html = self.make_cols();
        var head_html = self.make_head();

        self.tcols_el.innerHTML = cols_html;
        self.thead_el.innerHTML = head_html;

        // create callbacks for sorting
        var idx = 5;
        var row_el = self.thead_el.children[0];
        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];

                var elem = row_el.children[idx];
                $(elem).click(self.sort_task_factory(t_id));
                idx += 1;
            }
            var elem = row_el.children[idx];
            $(elem).click(self.sort_contest_factory(c_id));
            idx += 1;
        }
        var elem = row_el.children[idx];
        $(elem).click(self.sort_global_factory());

        self.update(null, null);
    };


    self.make_cols = function () {
        var result = "";
        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];
                result += "<col class=\"score task\" />";
            }
            result += "<col class=\"score contest\" />"
        }

        return result;
    };


    self.make_head = function () {
        var result = " \
<tr> \
    <th class=\"sel\"></th> \
    <th class=\"rank\">Rank</th> \
    <th class=\"f_name\">First Name</th> \
    <th class=\"l_name\">Last Name</th> \
    <th class=\"team\">Team</th>";

        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];
                result += " \
    <th class=\"score task\"><abbr title=\"" + task["name"] + "\">" + task["name"][0] + "</abbr></th>";
            }
            result += " \
    <th class=\"score contest\">" + contest["name"] + "</th>";
        }
        result += " \
    <th class=\"score global\">Global</th></tr>";

        return result;
    };


    self.get_score_class = function (score, max_score) {
        if (score == 0) {
            return "score_0";
        } else if (score == max_score) {
            return "score_100";
        } else {
            var rel_score = parseInt(score / max_score * 10) * 10;
            return "score_" + rel_score + "_" + (rel_score + 10);
        }
    };


    self.make_row = function (u_id, user, rank, t_key, c_key) {
        var result = " \
<tr id=\"" + u_id + '\"' + (DataStore.get_selected(u_id) ? " class=\"selected\"" : "") + "> \
    <td class=\"sel\"> \
        <input type=\"checkbox\"" + (DataStore.get_selected(u_id) ? "checked" : "") + " /> \
    </td> \
    <td class=\"rank\">" + rank + "</td> \
    <td class=\"f_name\">" + user["f_name"] + "</td> \
    <td class=\"l_name\">" + user["l_name"] + "</td>";

        if (user['team']) {
            result += " \
    <td class=\"team\"><img src=\"" + Config.get_flag_url(user["team"]) + "\" title=\"" + DataStore.teams[user["team"]]["name"] + "\" /></td>";
        } else {
            result += " \
    <td class=\"team\"></td>";
        }

        var global_score = 0.0
        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];

            var contest_score = 0.0
            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];

                var task_score = DataStore.tasks[t_id]["score"];

                var score_class = self.get_score_class(DataStore.get_score_t(u_id, t_id), task_score);
                if (t_id === t_key) {
                    score_class += " sort_key";
                }
                result += " \
    <td class=\"score task " + score_class + "\">" + round_to_str(DataStore.get_score_t(u_id, t_id)) + "</td>";
                contest_score += task_score;
            }

            var score_class = self.get_score_class(DataStore.get_score_c(u_id, c_id), contest_score);
            if (c_id === c_key) {
                score_class += " sort_key";
            }
            result += " \
    <td class=\"score contest " + score_class + "\">" + round_to_str(DataStore.get_score_c(u_id, c_id)) + "</td>";
            global_score += contest_score
        }

        var score_class = self.get_score_class(DataStore.get_score(u_id), global_score)
        if (t_key === null && c_key === null) {
            score_class += " sort_key";
        }
        result += " \
    <td class=\"score global " + score_class + "\">" + round_to_str(DataStore.get_score(u_id)) + "</td> \
</tr>";

        return result;
    };

    self.make_body = function (t_key, c_key) {
        var users = new Array();
        for (u_id in DataStore.users) {
            user = DataStore.users[u_id];
            if (t_key !== null) {
                user["score1"] = DataStore.get_score_t(u_id, t_key);
                user["score2"] = DataStore.get_score(u_id);
            } else if (c_key !== null) {
                user["score1"] = DataStore.get_score_c(u_id, c_key);
                user["score2"] = DataStore.get_score(u_id);
            } else {
                user["score1"] = DataStore.get_score(u_id);
                user["score2"] = DataStore.get_score(u_id);
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

        var result = "";

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

        return result;
    };


    self.update = function (t_key, c_key) {
        var body_html = self.make_body(t_key, c_key);
        self.tbody_el.innerHTML = body_html;

        // create callbacks for selection
        for (var u_id in DataStore.users) {
            var check = document.getElementById(u_id).children[0].children[0];
            check.addEventListener('change', self.select_factory(u_id));
        }

        // create callbacks for UserPanel
        for (var u_id in DataStore.users) {
            var row = document.getElementById(u_id);
            row.children[2].addEventListener('click', self.user_callback_factory(u_id));
            row.children[3].addEventListener('click', self.user_callback_factory(u_id));
        }
    };


    self.select_handler = function (u_id, flag) {
        var row = document.getElementById(u_id);
        if (flag) {
            $(row).addClass("selected");
        } else {
            $(row).removeClass("selected");
        }
        var check = row.children[0].children[0];
        check.checked = flag;
    };


    self.select_factory = function (u_id) {
        var result = function () {
            var row = document.getElementById(u_id);
            var check = row.children[0].children[0];
            DataStore.set_selected(u_id, check.checked);
        }
        return result;
    };


    self.user_callback_factory = function (u_id) {
        var result = function () {
            UserDetail.show(u_id);
        };
        return result;
    };


    self.sort_task_factory = function (t_id) {
        var result = function () {
            self.update(t_id, null);
        };
        return result;
    };


    self.sort_contest_factory = function (c_id) {
        var result = function () {
            self.update(null, c_id);
        };
        return result;
    };


    self.sort_global_factory = function (t_id) {
        var result = function () {
            self.update(null, null);
        };
        return result;
    };
};
