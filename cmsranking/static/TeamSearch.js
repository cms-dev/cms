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

var TeamSearch = new function () {
    var self = this;

    self.init = function () {
        $("#team_search_input").focus(function () {
            self.show();
        });

        /* This event is very problematic:
           * the `input' event doesn't exists in IE (except in version 9, where
             it's buggy: it doesn't get fired when characters are deleted);
           * the `propertychange' event is the IE-equivalent event, but it's
             also buggy in IE9 (in the same way);
           * the `keypress' event provided by JQuery (which I suppose is
             supported on all major browser) gets fired too early, when the
             value of the input hasn't yet been updated (so we read the value
             it has _before_ the change);
           * The `change' event is a standard (and I think it's correctly
             supported almost everywhere) but it gets fired only when the
             element loses focus.
           Suggestions are welcome.
        */
        $("#team_search_input").bind("input", function () {
            self.update();
        });

        $("#team_search_bg").click(function (event) {
            if (event.target == event.currentTarget) {
                self.hide();
            }
        });

        $("#team_search_close").click(function () {
            self.hide();
        });

        self.t_head = document.getElementById('team_search_head');
        self.t_body = document.getElementById('team_search_body');

        self.open = false;

        self.generate();
        self.update();

        DataStore.select_events.add(self.select_handler);
    };

    self.generate = function () {
        self.sel = new Object();
        self.cnt = new Object();

        for (var t_id in DataStore.teams) {
            self.sel[t_id] = 0;
            self.cnt[t_id] = 0;
        }

        for (var u_id in DataStore.users) {
            var user = DataStore.users[u_id];
            if (user['team'] !== null) {
                self.cnt[user['team']] += 1;
            }
        }

        var inner_html = "";

        for (var i in DataStore.team_list) {
            var team = DataStore.team_list[i];
            var t_id = team["key"];
            inner_html += " \
<div class=\"item\" id=\"" + t_id + "\"> \
    <input type=\"checkbox\" id=\"" + t_id + "_check\" /> \
    <label for=\"" + t_id + "_check\"> \
        <img class=\"flag\" src=\"" + Config.get_flag_url(t_id) + "\" />" + team['name'] + " \
    </label> \
</div>";
        }
        self.t_body.innerHTML = inner_html;

        for (var t_id in DataStore.teams) {
            var elem = document.getElementById(t_id + "_check");
            $(elem).change(self.callback_factory(t_id, elem));
        }
    };

    self.select_handler = function (u_id, flag) {
        var user = DataStore.users[u_id];

        if (!user['team']) {
            return;
        }

        if (flag) {
            self.sel[user['team']] += 1;
        } else {
            self.sel[user['team']] -= 1;
        }

        var elem = document.getElementById(user['team'] + '_check');
        if (self.sel[user['team']] == self.cnt[user['team']]) {
            elem.checked = true;
            elem.indeterminate = false;
        } else if (self.sel[user['team']] > 0) {
            elem.checked = true;
            elem.indeterminate = true;
        } else {
            elem.checked = false;
            elem.indeterminate = false;
        }
    };

    self.show = function () {
        if (!self.open) {
            $("body").addClass("team_search");
            self.open = true;
        }
    };

    self.hide = function () {
        if (self.open) {
            $("body").removeClass("team_search");
            self.open = false;
        }
    };

    self.update = function () {
        var search_text = $("#team_search_input").val();

        if (search_text == "") {
            for (var t_id in DataStore.teams) {
                $("#" + t_id).removeClass("hidden");
            }
        } else {
            for (var t_id in DataStore.teams) {
                var team = DataStore.teams[t_id];
                if (team["name"].toLowerCase().indexOf(search_text.toLowerCase()) == -1) {
                    $("#" + t_id).addClass("hidden");
                } else {
                    $("#" + t_id).removeClass("hidden");
                }
            }
        }
    };

    self.callback_factory = function (t_id, elem) {
        var result = function () {
            var status = elem.checked;
            for (var u_id in DataStore.users) {
                var user = DataStore.users[u_id];
                if (user['team'] == t_id) {
                    DataStore.set_selected(u_id, status);
                }
            }
        };
        return result;
    };
};
