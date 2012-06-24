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

        DataStore.score_events.add(self.score_handler);
        DataStore.rank_events.add(self.rank_handler);
        DataStore.select_events.add(self.update_select);
        self.update_score();
    };

    self.update_score = function () {
        var users_l = Object.keys(DataStore.users).length;
        for (var u_id in DataStore.users) {
            var user = DataStore.users[u_id];

            $("#" + u_id + "_lm").css("bottom", (100 * user["global"] / DataStore.global_max_score).toString() + "%");
            $("#" + u_id + "_rm").css("bottom", (100 - 100 * (user["rank"] - 1) / users_l).toString() + "%");
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

    self.score_handler = function (u_id, user) {
        $("#" + u_id + "_lm").css("bottom", (100 * user["global"] / DataStore.global_max_score).toString() + "%");
    };

    self.rank_handler = function (u_id, user) {
        var users_l = Object.keys(DataStore.users).length;
        $("#" + u_id + "_rm").css("bottom", (100 - 100 * (user["rank"] - 1) / users_l).toString() + "%");
    };

    /* TODO: When users get added/removed the total user count changes and all
       rank "markers" need to be adjusted!
     */
};
