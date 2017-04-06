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

var escapeHTML = (function() {
    var escapeMap = {
        '&' : '&amp;',
        '<' : '&lt;',
        '>' : '&gt;',
        '"' : '&quot;',
        "'" : '&#x27;',
        '/' : '&#x2F;',
        '`' : '&#x60;'
    };
    var escapeHTML = function(str) {
        return String(str).replace(/[&<>"'\/`]/g, function(ch) {
            return escapeMap[ch];
        });
    };
    return escapeHTML;
})();

var Scoreboard = new function () {
    var self = this;

    self.init = function () {
        self.tcols_el = $('#Scoreboard_cols');
        self.thead_el = $('#Scoreboard_head');
        self.tbody_el = $('#Scoreboard_body');

        self.generate();

        DataStore.user_create.add(self.create_user);
        DataStore.user_update.add(self.update_user);
        DataStore.user_delete.add(self.delete_user);

        DataStore.score_events.add(self.score_handler);
        DataStore.rank_events.add(self.rank_handler);
        DataStore.select_events.add(self.select_handler);
    };


    self.generate = function () {
        self.tcols_el.html(self.make_cols());
        self.thead_el.html(self.make_head());

        // Create callbacks for sorting
        self.thead_el.on("click", "th.score", function () {
            $("col[data-sort_key=" + self.sort_key + "]", self.tcols_el).removeClass("sort_key");
            $("tr td[data-sort_key=" + self.sort_key + "]", self.thead_el).removeClass("sort_key");
            $("tr td[data-sort_key=" + self.sort_key + "]", self.tbody_el).removeClass("sort_key");

            var $this = $(this);

            if ($this.hasClass("global")) {
                self.sort_key = "global";
            } else if ($this.hasClass("contest")) {
                self.sort_key = "c_" + $this.data("contest");
            } else if ($this.hasClass("task")) {
                self.sort_key = "t_" + $this.data("task");
            }

            self.sort();

            $("col[data-sort_key=" + self.sort_key + "]", self.tcols_el).addClass("sort_key");
            $("tr td[data-sort_key=" + self.sort_key + "]", self.thead_el).addClass("sort_key");
            $("tr td[data-sort_key=" + self.sort_key + "]", self.tbody_el).addClass("sort_key");
        });

        self.sort_key = "global";
        self.make_body();

        // Set initial style
        $("col[data-sort_key=" + self.sort_key + "]", self.tcols_el).addClass("sort_key");
        $("tr td[data-sort_key=" + self.sort_key + "]", self.thead_el).addClass("sort_key");
        $("tr td[data-sort_key=" + self.sort_key + "]", self.tbody_el).addClass("sort_key");

        // Create callbacks for selection
        self.tbody_el.on("click", "td.sel", function () {
            DataStore.toggle_selected($(this).parent().data("user"));
        });

        // Create callbacks for UserPanel
        self.tbody_el.on("click", "td.f_name, td.l_name", function () {
            UserDetail.show($(this).parent().data("user"));
        });

        // Create callbacks for animation-end
        self.tbody_el.on('animationend', 'tr', function(event) {
            $(this).removeClass("score_up score_down");
        });

        // Fuck, WebKit!!
        self.tbody_el.on('webkitAnimationEnd', 'tr', function(event) {
            $(this).removeClass("score_up score_down");
        });
    };


    self.make_cols = function () {
        // We want some columns to have a fixed, constant width at all screen
        // sizes (i.e. the sel, rank and team columns) while having the other
        // columns scale accoring to the available horizontal space. Yet, we
        // also want these columns' widths to keep a certain ratio one to each
        // other, for example the task score, contest score and global score
        // columns should be in a 3:4:5 ratio. Since the number of columns is
        // not known beforehand, this is quite difficult to achieve.
        // We cannot specify all the widths using pixel sizes (or similar)
        // because when there are many tasks the table may overflow, and when
        // there are few tasks it may underflow (and, in such cases, the
        // remaining width is divided proportionally among all columns, thus
        // enlarging the constant width columns too). We cannot use relative
        // widths (i.e. using precent values) because it seems that some
        // versions of IE don't like it when the sum of the widths is greater
        // than 100% (and this may happen when there are many tasks).
        // We cannot use an 'auto' width on all columns because this would not
        // preserve the ratio among widths.
        // We cannot mix fixed/percent/auto widths because, depending on the
        // way we do it, the solution may not scale well at high resolutions or
        // it may again be difficult to keep the ratio that we want.
        // Also, I would like not to use JS or strange HTML constructions to
        // achieve this goal: it would be great if we could do this using just
        // simple CSS rules.
        // I couldn't find the perfect solution, so the one I'm implementing is
        // a bit of a compromise, which tries to mess as little as possible
        // with JS and HTML. So, at the moment, this is what we do: we set the
        // columns with fixed width to their fixed width (via CSS). We don't
        // define a width for all other columns, thus leaving them at their
        // default value: auto. Yet, we don't create a single <col/> element
        // for each column, but we create 3 for the task columns, 4 for the
        // contest columns, 5 for the global column, etc. Then we set the
        // colspan attribute of task cells to 3, of contest cells to 4, of
        // global cells to 5, etc. This way, since all <col/>s with a width of
        // 'auto' get the same computed width, we keep the 3:4:5 ratio and are
        // able to scale well at each screen size, while keeping the constant
        // width columns constant. (Note: we gave the first_ and last_name
        // columns a "width" of 10 <col/> elements.)
        // Suggestion on other solution that get the same result and don't mess
        // this much with JS and HTML are extremely welcome!
        var result = " \
<col class=\"sel\"/> \
<col class=\"rank\"/> \
<col class=\"f_name\"/> <col/><col/><col/><col/><col/><col/><col/><col/><col/> \
<col class=\"l_name\"/> <col/><col/><col/><col/><col/><col/><col/><col/><col/> \
<col class=\"team\"/>";

        var contests = DataStore.contest_list;
        for (var i in contests) {
            var contest = contests[i];
            var c_id = contest["key"];

            var tasks = contest["tasks"];
            for (var j in tasks) {
                var task = tasks[j];
                var t_id = task["key"];

                result += " \
<col class=\"score task\" data-task=\"" + t_id + "\" data-sort_key=\"t_" + t_id + "\"/> <col/><col/>";
            }

            result += " \
<col class=\"score contest\" data-contest=\"" + c_id + "\" data-sort_key=\"c_" + c_id + "\"/> <col/><col/><col/>";
        }

        result += " \
<col class=\"score global\" data-sort_key=\"global\"/> <col/><col/><col/><col/>";

        return result;
    };


    self.make_head = function () {
        // See the comment in .make_cols() for the reason we use colspans.
        var result = " \
<tr> \
    <th class=\"sel\"></th> \
    <th class=\"rank\">Rank</th> \
    <th colspan=\"10\" class=\"f_name\">First Name</th> \
    <th colspan=\"10\" class=\"l_name\">Last Name</th> \
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
    <th colspan=\"3\" class=\"score task\" data-task=\"" + t_id + "\" data-sort_key=\"t_" + t_id + "\"><abbr title=\"" + escapeHTML(task["name"]) + "\">" + escapeHTML(task["short_name"]) + "</abbr></th>";
            }

            result += " \
    <th colspan=\"4\" class=\"score contest\" data-contest=\"" + c_id + "\" data-sort_key=\"c_" + c_id + "\"><abbr title=\"" + escapeHTML(contest["name"]) + "\">" + escapeHTML(contest["name"]) + "</abbr></th>";
        }

        result += " \
    <th colspan=\"5\" class=\"score global\" data-sort_key=\"global\">Global</th> \
</tr>";

        return result;
    };


    self.make_body = function () {
        for (var u_id in DataStore.users) {
            var user = DataStore.users[u_id];
            user["row"] = $(self.make_row(user))[0];
            self.user_list.push(user);
        }

        self.sort();
    };


    self.make_row = function (user) {
        // See the comment in .make_cols() for the reason we use colspans.
        var result = " \
<tr class=\"user" + (user["selected"] > 0 ? " selected color" + user["selected"] : "") + "\" data-user=\"" + user["key"] + "\"> \
    <td class=\"sel\"></td> \
    <td class=\"rank\">" + user["rank"] + "</td> \
    <td colspan=\"10\" class=\"f_name\">" + escapeHTML(user["f_name"]) + "</td> \
    <td colspan=\"10\" class=\"l_name\">" + escapeHTML(user["l_name"]) + "</td>";

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
    <td colspan=\"3\" class=\"score task " + score_class + "\" data-task=\"" + t_id + "\" data-sort_key=\"t_" + t_id + "\">" + round_to_str(user["t_" + t_id], task["score_precision"]) + "</td>";
            }

            var score_class = self.get_score_class(user["c_" + c_id], contest["max_score"]);
            result += " \
    <td colspan=\"4\" class=\"score contest " + score_class + "\" data-contest=\"" + c_id + "\" data-sort_key=\"c_" + c_id + "\">" + round_to_str(user["c_" + c_id], contest["score_precision"]) + "</td>";
        }

        var score_class = self.get_score_class(user["global"], DataStore.global_max_score);
        result += " \
    <td colspan=\"5\" class=\"score global " + score_class + "\" data-sort_key=\"global\">" + round_to_str(user["global"], DataStore.global_score_precision) + "</td> \
</tr>";

        return result;
    };


    self.get_score_class = function (score, max_score) {
        if (score <= 0) {
            return "score_0";
        } else if (score >= max_score) {
            return "score_100";
        } else {
            var rel_score = parseInt(score / max_score * 10) * 10;
            return "score_" + rel_score + "_" + (rel_score + 10);
        }
    };


    // We keep a sorted list of user that represent the current order of the
    // scoreboard. In particular we sort using these keys:
    // - the score in the current active column
    // - the global score
    // - the last name
    // - the first name
    // - the key
    self.user_list = new Array();


    // Compare two users. Returns -1 if "a < b" or +1 if "a >= b"
    // (where a < b means that a shoud go above b in the scoreboard)
    self.compare_users = function (a, b) {
        var sort_key = self.sort_key;
        if ((a[sort_key] > b[sort_key]) || ((a[sort_key] == b[sort_key]) &&
           ((a["global"] > b["global"]) || ((a["global"] == b["global"]) &&
           ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
           ((a["f_name"] < b["f_name"]) || ((a["f_name"] == b["f_name"]) &&
           (a["key"] <= b["key"]))))))))) {
            return -1;
        } else {
            return +1;
        }
    };


    // Suppose the scoreboard is correctly sorted except for the given user.
    // Move this user (up or down) to put it in their correct position.
    self.move_user = function (user) {
        var list = self.user_list;
        var compare = self.compare_users;

        var list_l = list.length;
        var i = parseInt(user["index"]);

        if (i > 0 && compare(user, list[i-1]) == -1) {
            // Move up

            while (i > 0 && compare(user, list[i-1]) == -1) {
                list[i] = list[i-1];
                list[i]["index"] = i;
                i -= 1;
            }
            list[i] = user;
            user["index"] = i;

            if (i == 0) {
                self.tbody_el.prepend(user["row"]);
            } else {
                self.tbody_el.children("tr.user[data-user=" + list[i-1]["key"] + "]").after(user["row"]);
            }
        } else if (i < list_l-1 && compare(list[i+1], user) == -1) {
            // Move down

            while (i < list_l-1 && compare(list[i+1], user) == -1) {
                list[i] = list[i+1];
                list[i]["index"] = i;
                i += 1;
            }
            list[i] = user;
            user["index"] = i;

            if (i == list_l-1) {
                self.tbody_el.append(user["row"]);
            } else {
                self.tbody_el.children("tr.user[data-user=" + list[i+1]["key"] + "]").before(user["row"]);
            }
        }
    };


    // Sort the scoreboard using the column with the given index.
    self.sort = function () {
        var list = self.user_list;

        list.sort(self.compare_users);

        var fragment = document.createDocumentFragment();
        for (var idx in list)
        {
            list[idx]["index"] = idx;
            fragment.appendChild(list[idx]["row"]);
        }

        self.tbody_el.append(fragment);
    };


    // This callback is called by the DataStore when a user is created.
    self.create_user = function (u_id, user) {
        var $row = $(self.make_row(user));
        $row.children("td[data-sort_key=" + self.sort_key + "]").addClass("sort_key");

        user["row"] = $row[0];
        user["index"] = self.user_list.length;
        self.user_list.push(user);

        self.tbody_el.append(row);
        // The row will be at the bottom (since it has a score of zero and thus
        // the maximum rank), but we may still need to sort it due to other
        // users having that score and the sort-by-name clause.
        self.move_user(user);
    };


    // This callback is called by the DataStore when a user is updated.
    // It updates only its basic information (first name, last name and team).
    self.update_user = function (u_id, old_user, user) {
        var $row = $(old_user["row"]);

        user["row"] = old_user["row"];
        user["index"] = old_user["index"];
        self.user_list.splice(old_user["index"], 1, user);
        delete old_user["row"];
        delete old_user["index"];

        $row.children("td.f_name").text(user["f_name"]);
        $row.children("td.l_name").text(user["l_name"]);

        if (user["team"]) {
            $row.children(".team").html("<img src=\"" + Config.get_flag_url(user["team"]) + "\" title=\"" + DataStore.teams[user["team"]]["name"] + "\" />");
        } else {
            $row.children(".team").text("");
        }
    };


    // This callback is called by the DataStore when a user is deleted.
    self.delete_user = function (u_id, old_user) {
        var $row = $(old_user["row"]);

        self.user_list.splice(old_user["index"], 1);
        delete old_user["row"];
        delete old_user["index"];

        $row.remove();
    };


    // This callback is called by the DataStore when a user changes score.
    self.score_handler = function (u_id, user, t_id, task, delta) {
        var $row = $(user["row"]);

        // TODO improve this method: avoid walking over all cells

        $row.children("td.score").each(function () {
            var $this = $(this);

            var score = user[$this.data("sort_key")];

            if ($this.hasClass("global")) {
                var max_score = DataStore.global_max_score;
                $this.text(round_to_str(score, DataStore.global_score_precision));
            } else if ($this.hasClass("contest")) {
                var contest = DataStore.contests[$this.data("contest")];
                var max_score = contest["max_score"];
                $this.text(round_to_str(score, contest["score_precision"]));
            } else if ($this.hasClass("task")) {
                var task = DataStore.tasks[$this.data("task")];
                var max_score = task["max_score"];
                $this.text(round_to_str(score, task["score_precision"]));
            }

            // TODO we could user a data-* attribute to store the score class

            var score_class = self.get_score_class(score, max_score);
            $this.removeClass("score_0 score_0_10 score_10_20 score_20_30 score_30_40 score_40_50 score_50_60 score_60_70 score_70_80 score_80_90 score_90_100 score_100");
            $this.addClass(score_class);
        });

        self.move_user(user);

        // Restart CSS animation
        $row.removeClass("score_up score_down");
        if (delta > 0) {
            $row.addClass("score_up");
        } else if (delta < 0) {
            $row.addClass("score_down");
        }
    };


    // This callback is called by the DataStore when a user changes rank.
    self.rank_handler = function (u_id, user) {
        var $row = $(user["row"]);

        $row.children("td.rank").text(user["rank"]);
    };


    self.select_handler = function (u_id, color) {
        var $row = $(DataStore.users[u_id]["row"]);

        // TODO we could user a data-* attribute to store the color

        if (color != 0) {
            $row.addClass("selected color" + color);
        } else {
            $row.removeClass("selected color1 color2 color3 color4 color5 color6 color7 color8");
        }
    };

    self.scroll_into_view = function (u_id) {
        var $row = $("tr.user[data-user=" + u_id + "]", self.tbody_el);
        var $frame = $("#InnerFrame");
        var scroll = $row.position().top + $frame.scrollTop() + $row.height() / 2 - $frame.height() / 2;
        $frame.scrollTop(scroll);
    };
};
