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

function format_time(time, full) {
    var h = Math.floor(time / 3600);
    var m = Math.floor((time % 3600) / 60);
    var s = Math.floor(time % 60);
    h = full && h < 10 ? "0" + h : "" + h;
    m = m < 10 ? "0" + m : "" + m;
    s = s < 10 ? "0" + s : "" + s;
    return (h + ":" + m + ":" + s);
};

function _get_time() {
    // Return the seconds since January 1, 1970 00:00:00 UTC
    return $.now() / 1000;
}

var TimeView = new function () {
    var self = this;

    // possible values:
    // - 0: elapsed time
    // - 1: remaining time
    // - 2: current (clock) time
    self.status = 0;

    self.init = function () {
        window.setInterval(function() {
            self.on_timer();
        }, 1000);
        self.on_timer();

        $("#TimeView_selector_elapsed").click(function () {
            self.status = 0;
            self.on_timer();
            $("#TimeView_selector").removeClass("open");
        });

        $("#TimeView_selector_remaining").click(function () {
            self.status = 1;
            self.on_timer();
            $("#TimeView_selector").removeClass("open");
        });

        $("#TimeView_selector_current").click(function () {
            self.status = 2;
            self.on_timer();
            $("#TimeView_selector").removeClass("open");
        });

        $("#TimeView_expand").click(function () {
            $("#TimeView_selector").toggleClass("open");
        });

        $("#TimeView_selector").click(function (event) {
            event.stopPropagation();
            return false;
        });

        $("body").on("click", function () {
            $("#TimeView_selector").removeClass("open");
        })
    };

    self.on_timer = function () {
        var cur_time = _get_time();
        var c = null;

        // contests are iterated sorted by begin time
        // and the first one that's still running is chosen
        for (var j in DataStore.contest_list) {
            var contest = DataStore.contest_list[j];
            if (cur_time <= contest['end']) {
                c = contest;
                break;
            }
        }

        if (c == null) {
            $("#TimeView_name").text();
        } else {
            $("#TimeView_name").text(c["name"]);
        }

        var date = new Date(cur_time * 1000);
        var today = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        var time = cur_time - today.getTime() / 1000;

        var full_time = false;

        if (c == null) {
            // no "next contest": always show the clock
            $("#TimeView").removeClass("elapsed remaining pre_cont cont");
            $("#TimeView").addClass("current post_cont");
            full_time = true;
        } else {
            if (cur_time < c['begin']) {
                // the next contest has yet to start: show remaining or clock
                $("#TimeView").removeClass("cont post_cont");
                $("#TimeView").addClass("pre_cont");
                if (self.status == 2) {
                    $("#TimeView").removeClass("elapsed remaining");
                    $("#TimeView").addClass("current");
                    full_time = true;
                } else {
                    $("#TimeView").removeClass("elapsed current");
                    $("#TimeView").addClass("remaining");
                    time = cur_time - c['begin'];
                }
            } else {
                // the next contest already started: all options available
                $("#TimeView").removeClass("pre_cont post_cont");
                $("#TimeView").addClass("cont");
                if (self.status == 2) {
                    $("#TimeView").removeClass("elapsed remaining");
                    $("#TimeView").addClass("current");
                    full_time = true;
                } else if (self.status == 1) {
                    $("#TimeView").removeClass("elapsed current");
                    $("#TimeView").addClass("remaining");
                    time = cur_time - c['end'];
                } else {
                    $("#TimeView").removeClass("remaining current");
                    $("#TimeView").addClass("elapsed");
                    time = cur_time - c['begin'];
                }
            }
        }

        var time_str = format_time(Math.abs(Math.floor(time)), full_time);
        if (time < 0) {
            time_str = '-' + time_str;
        }

        $("#TimeView_time").text(time_str);
    };
};
