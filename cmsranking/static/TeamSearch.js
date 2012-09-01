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
        $("#TeamSearch_input").focus(function () {
            self.show();
        });

        $("#TeamSearch_bg").click(function (event) {
            if (event.target == event.currentTarget) {
                self.hide();
            }
        });

        $("#TeamSearch_close").click(function () {
            self.hide();
        });

        /** Update the list when the value in the search box changes */

        /* This event is very problematic:
           * The `change' event is a standard (and I think it's correctly
             supported almost everywhere) but it gets fired only when the
             element loses focus.
           * the `input' event does what we want but it doesn't exists in IE
             (except in version 9, where it's buggy: it doesn't get fired when
             characters are deleted);
           * the `propertychange' event is the IE-equivalent event, but it's
             also buggy in IE9 (in the same way);
           * the `keypress' event provided by JQuery (which isn't standard and
             thus may vary among browsers) seems to get fired too early, when
             the value of the input hasn't yet been updated (so we read the
             value _before_ it gets changed);
           * the `keydown' event seems to be more standard, but it has the same
             disadvantage as the `keypress': it's fired too early; in addition,
             it gets fired only once when the key is held down (while keypress
             is fire repeatedly, once for each new character).
           * the `keyup' event should solve the first issue of `keydown' but
             not the second: it's only fired at the end of a series of
             `keypress' events.
           * cutting text is another way to delete characters, thus we'll need
             to listen to `cut' events in IE9 to workaround the buggy `input'.
           Suggestions are welcome.
        */

        /* I decided to listen on `input' and `propertychange' since they
           should work everywhere except IE9. On IE9 some (conditional) code
           will also listen to the `keyup' and `cut' events and try to detect
           when some text is deleted.
         */

        $("#TeamSearch_input").on("input", function () {
            self.update();
        });

        $("#TeamSearch_input").on("propertychange", function () {
            self.update();
        });

/*@cc_on
    @if (@_jscript_version == 9)

        $("#TeamSearch_input").keyup(function (event) {
            switch (event.which) {
                case 8:  // backspace
                case 46:  // delete
                    self.update();
            }
        });

        $("#TeamSearch_input").on("cut", function () {
            self.update();
        });

    @end
@*/

        self.body = $('#TeamSearch_body');

        self.generate();
        self.update();

        DataStore.select_events.add(self.select_handler);
    };

    self.generate = function () {
        self.sel = new Object();
        self.cnt = new Object();

        for (var t_id in DataStore.teams) {
            self.sel[t_id] = 0;
            self.cnt[t_id] = DataStore.teams[t_id]["users"].length;
        }

        var inner_html = "";

        // We're iterating on the team_list (instead of teams) to get the teams
        // in lexicographic order of name
        for (var i in DataStore.team_list) {
            var team = DataStore.team_list[i];
            var t_id = team["key"];
            inner_html += " \
<div class=\"item\" data-team=\"" + t_id + "\"> \
    <label> \
        <input type=\"checkbox\"/> \
        <img class=\"flag\" src=\"" + Config.get_flag_url(t_id) + "\" /> " + team['name'] + " \
    </label> \
</div>";
        }

        self.body.html(inner_html);

        self.body.on("change", "input[type=checkbox]", function () {
            var $this = $(this);

            var users = DataStore.teams[$this.parent().parent().data("team")]["users"];
            var status = $this.prop("checked");

            for (var i in users) {
                DataStore.set_selected(users[i]["key"], status);
            }
        });
    };

    self.select_handler = function (u_id, flag) {
        var user = DataStore.users[u_id];
        var t_id = user['team'];

        if (!t_id) {
            return;
        }

        if (flag) {
            self.sel[t_id] += 1;
        } else {
            self.sel[t_id] -= 1;
        }

        var $elem = $("div.item[data-team=" + t_id + "] input[type=checkbox]", self.body);
        if (self.sel[t_id] == self.cnt[t_id]) {
            $elem.prop("checked", true);
            $elem.prop("indeterminate", false);
        } else if (self.sel[t_id] > 0) {
            $elem.prop("checked", true);
            $elem.prop("indeterminate", true);
        } else {
            $elem.prop("checked", false);
            $elem.prop("indeterminate", false);
        }
    };

    self.show = function () {
        $("#TeamSearch_bg").addClass("open");
    };

    self.hide = function () {
        $("#TeamSearch_bg").removeClass("open");
    };

    self.update = function () {
        var search_text = $("#TeamSearch_input").val();

        if (search_text == "") {
            $('div.item', self.t_body).removeClass("hidden");
        } else {
            // FIXME We could store the lowercased name of the team on the divs
            // and then just use a query like [attribute*="value"] (with value
            // set to the lowercased search_text) and add the class to that.
            // (We would need another query to get the complementary set).
            for (var t_id in DataStore.teams) {
                var team = DataStore.teams[t_id];
                if (team["name"].toLowerCase().indexOf(search_text.toLowerCase()) == -1) {
                    $("div.item[data-team=" + t_id + "]", self.body).addClass("hidden");
                } else {
                    $("div.item[data-team=" + t_id + "]", self.body).removeClass("hidden");
                }
            }
        }
    };
};
