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

        self.generate();

        DataStore.user_create.add(self.create_user);
        DataStore.user_update.add(self.update_user);
        DataStore.user_delete.add(self.delete_user);

        DataStore.score_events.add(self.score_handler);
        DataStore.rank_events.add(self.rank_handler);
    };


    self.generate = function () {
        var cols_html = self.make_cols();
        $(self.tcols_el).html(cols_html);

        var head_html = self.make_head();
        $(self.thead_el).html(head_html);


        // Init cols_list
        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];

            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];

                self.cols_list.push("t_" + t_id);
            }
            self.cols_list.push("c_" + c_id);
        }
        self.cols_list.push("global");

        // Create callbacks for sorting
        $("#Scoreboard_head tr th").slice(5).each(function (index) {
            $(this).click(self.sort_callback_factory(index));
        });

        self.sort_index = self.cols_list.length - 1;
        self.make_body();

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

        // create callbacks for animation-end
        $("#Scoreboard_body tr").bind('animationend', function(event) {
            $(this).removeClass("score_up score_down");
        });

        // Fuck, WebKit!!
        $("#Scoreboard_body tr").bind('webkitAnimationEnd', function(event) {
            $(this).removeClass("score_up score_down");
        });
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
    <th class=\"score task\"><abbr title=\"" + task["name"] + "\">" + task["short_name"] + "</abbr></th>";
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


    self.make_row = function (user) {
        var u_id = user["key"];
        var rank = user["rank"];

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

        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];

            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];

                var score_class = self.get_score_class(user["t_" + t_id], task["max_score"]);
                result += " \
    <td class=\"score task " + score_class + "\">" + round_to_str(user["t_" + t_id]) + "</td>";
            }

            var score_class = self.get_score_class(user["c_" + c_id], contest["max_score"]);
            result += " \
    <td class=\"score contest " + score_class + "\">" + round_to_str(user["c_" + c_id]) + "</td>";
        }

        var score_class = self.get_score_class(user["global"], DataStore.global_max_score);
        result += " \
    <td class=\"score global " + score_class + "\">" + round_to_str(user["global"]) + "</td> \
</tr>";

        return result;
    };

    self.make_body = function () {
        for (var u_id in DataStore.users) {
            var user = DataStore.users[u_id];
            user["row"] = $(self.make_row(user)).get(0);
            self.user_list.push(user);
        }

        self.sort(self.sort_index);
    };


    // We keep a sorted list of user that represent the current order of the
    // scoreboard. In particular we sort using these keys:
    // - the score in the current active column
    // - the global score
    // - the last name
    // - the first name
    // - the key

    self.user_list = new Array();


    // The index of the column that acts as primary sort key.
    self.sort_index = 0;

    // Compare two users. Returns true if "a <= b".
    self.compare_users = function (a, b) {
        var sort_key = self.cols_list[self.sort_index];
        return ((a[sort_key] > b[sort_key]) || ((a[sort_key] == b[sort_key]) &&
               ((a["global"] > b["global"]) || ((a["global"] == b["global"]) &&
               ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
               ((a["f_name"] < b["f_name"]) || ((a["f_name"] == b["f_name"]) &&
               (a["key"] <= b["key"])))))))));
    };


    // Suppose the scoreboard is correctly sorted except for the given user.
    // Move this user (up or down) to put it in his correct position.
    self.move_user = function (user) {
        var list = self.user_list;
        var compare = self.compare_users;

        var list_l = list.length;
        var j = parseInt(user["index"]);

        if (j > 0 && compare(user, list[j-1])) {
            // Move up

            var i = j;
            while (i > 0 && compare(user, list[i-1])) {
                list[i] = list[i-1];
                list[i]["index"] = i;
                i -= 1;
            }
            list[i] = user;
            user["index"] = i;

            if (i == 0) {
                $("#Scoreboard_body").prepend(user["row"]);
            } else {
                $("#Scoreboard_body").children("#" + list[i-1]["key"]).after(user["row"]);
            }
        } else if (j < list_l-1 && compare(list[j+1], user)) {
            // Move down

            var i = j;
            while (i < list_l-1 && compare(list[i+1], user)) {
                list[i] = list[i+1];
                list[i]["index"] = i;
                i += 1;
            }
            list[i] = user;
            user["index"] = i;

            if (i == list_l-1) {
                $("#Scoreboard_body").append(user["row"]);
            } else {
                $("#Scoreboard_body").children("#" + list[i+1]["key"]).before(user["row"]);
            }
        }
    };


    // Sort the scoreboard using the column with the given index.
    self.sort = function (sort_index) {
        $("#Scoreboard_body tr td:nth-child(" + (6 + self.sort_index) + ")").removeClass("sort_key");

        self.sort_index = sort_index;

        var sort_key = self.cols_list[self.sort_index];

        var list = self.user_list;

        list.sort(function (a, b) {
            if ((a[sort_key] > b[sort_key]) || ((a[sort_key] == b[sort_key]) &&
               ((a["global"] > b["global"]) || ((a["global"] == b["global"]) &&
               ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
               ((a["f_name"] < b["f_name"]) || ((a["f_name"] == b["f_name"]) &&
               (a["key"] <= b["key"]))))))))) {
                return -1;
            } else {
                return +1;
            }
        });

        var fragment = document.createDocumentFragment();
        for (var idx in list)
        {
            list[idx]["index"] = idx;
            fragment.appendChild(list[idx]["row"]);
        }

        $("#Scoreboard_body").append(fragment);

        $("#Scoreboard_body tr td:nth-child(" + (6 + self.sort_index) + ")").addClass("sort_key");
    };


    // A list to describe the sortable columns. Its element may be in the form
    // "t_<task_id>", "c_<contest_id>" or "global".
    self.cols_list = new Array();


    // This callback is called by the DataStore when a user is created.
    self.create_user = function (u_id, user) {
        var row = $(self.make_row(user)).get(0);
        $(row).children().eq(5 + self.sort_index).addClass("sort_key");

        user["row"] = row;
        $("#Scoreboard_body").append(row);

        user["index"] = self.user_list.length;
        self.user_list.push(user);
        self.move_user(user);

        // create callbacks for selection
        var check = row.children[0].children[0];
        check.addEventListener('change', self.select_factory(u_id));

        // create callbacks for UserPanel
        row.children[2].addEventListener('click', self.user_callback_factory(u_id));
        row.children[3].addEventListener('click', self.user_callback_factory(u_id));
    };

    // This callback is called by the DataStore when a user is updated.
    // It updates only its basic information (first name, last name and team).
    self.update_user = function (u_id, old_user, user) {
        var row = old_user["row"];
        user["row"] = row;
        user["index"] = old_user["index"];

        self.user_list.splice(user["index"], 1, user);

        $(row).children(".f_name").text(user["f_name"]);
        $(row).children(".l_name").text(user["l_name"]);

        if (user["team"]) {
            $(row).children(".team").html("<img src=\"" + Config.get_flag_url(user["team"]) + "\" title=\"" + DataStore.teams[user["team"]]["name"] + "\" />");
        } else {
            $(row).children(".team").text("");
        }
    };

    // This callback is called by the DataStore when a user is deleted.
    self.delete_user = function (u_id, old_user) {
        var row = old_user["row"];
        self.user_list.splice(old_user["index"], 1);
        delete old_user["row"];
        delete old_user["index"];

        $(row).remove();
    };

    // This callback is called by the DataStore when a user changes score.
    self.score_handler = function (u_id, user, delta) {
        var row = user["row"];

        $(row).children(".score").each(function (index) {
            var score_key = self.cols_list[index];

            if (score_key.substring(0, 2) == "t_") { // task
                var score_class = self.get_score_class(user[score_key], DataStore.tasks[score_key.substring(2)]["max_score"]);
            } else if (score_key.substring(0, 2) == "c_") { // contest
                var score_class = self.get_score_class(user[score_key], DataStore.contests[score_key.substring(2)]["max_score"]);
            } else { // global
                var score_class = self.get_score_class(user[score_key], DataStore.global_max_score);
            }

            $(this).removeClass("score_0 score_0_10 score_10_20 score_20_30 score_30_40 score_40_50 score_50_60 score_60_70 score_70_80 score_80_90 score_90_100 score_100");
            $(this).addClass(score_class);

            $(this).text(round_to_str(user[score_key]));
        });

        self.move_user(user);

        // Restart CSS animation
        if (delta > 0) {
            $(row).addClass("score_up");
        } else {
            $(row).addClass("score_down");
        }
    };

    // This callback is called by the DataStore when a user changes rank.
    self.rank_handler = function (u_id, user) {
        var row = user["row"];

        $(row).children(".rank").text(user["rank"]);
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


    self.sort_callback_factory = function (index) {
        var result = function () {
            self.sort(index);
        };
        return result;
    };
};
