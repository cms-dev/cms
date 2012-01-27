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

var Overview = new function () {
    var self = this;

    self.init = function () {
        var elem = document.getElementById("overview");

        var inner_html = " \
<div class=\"bar1\"></div> \
<div class=\"bar2\"></div>";

        for (var u_id in DataStore.users) {
            inner_html += " \
<div class=\"mark1\" id=\"" + u_id + "_lm\"></div> \
<div class=\"mark2\" id=\"" + u_id + "_rm\"></div>";
        }

        elem.innerHTML = inner_html;

        DataStore.add_select_handler(self.update_select);
        self.update_score();
    };

    self.update_score = function () {
        var users = new Array();

        for (var u_id in DataStore.users) {
            users.push([u_id, DataStore.get_score(u_id)]);
        }

        users.sort(function (a, b) {
            return b[1] - a[1];
        });

        var total_score = 0;
        for (var t_id in DataStore.tasks) {
            total_score += DataStore.tasks[t_id]["score"];
        }

        var prev_score = null;
        var rank = 0;
        var equal = 1;

        for (var idx in users) {
            var u_id = users[idx][0];
            var score = users[idx][1];

            if (score !== prev_score) {
                prev_score = score;
                rank += equal;
                equal = 1;
            } else {
                equal += 1;
            }

            $("#" + u_id + "_lm").css("bottom", (100 * score / total_score).toString() + "%");
            $("#" + u_id + "_rm").css("bottom", (100 - 100 * (rank - 1) / users.length).toString() + "%");
        }
    };

    self.update_select = function (u_id, flag) {
        if (flag) {
            $("#" + u_id + "_lm").addClass("selected");
            $("#" + u_id + "_rm").addClass("selected");
        } else {
            $("#" + u_id + "_lm").removeClass("selected");
            $("#" + u_id + "_rm").removeClass("selected");
        }
    };
};
