/* Contest Management System
 * Copyright © 2012-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
 * Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 * Copyright © 2013 Vittorio Gambaletta <VittGam@VittGam.net>
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

"use strict";

/**
 * Utility functions needed by CWS front-end.
 */

var CMS = CMS || {};

CMS.CWSUtils = function(url_root, timestamp, timezoned_timestamp,
                        current_phase_begin, current_phase_end, phase) {
    this.url_root = url_root;
    this.last_notification = timestamp;
    this.server_timestamp = timestamp;
    this.server_timezoned_timestamp = timezoned_timestamp;
    this.client_timestamp = $.now() / 1000;
    this.current_phase_begin = current_phase_begin;
    this.current_phase_end = current_phase_end;
    this.phase = phase;
    this.remaining_div = null;
    this.unread_count = 0;
};


CMS.CWSUtils.prototype.update_notifications = function() {
    var self = this;
    $.get(
        this.url_root + "/notifications",
        {"last_notification": this.last_notification},
        function(data) {
            var counter = 0;
            for (var i = 0; i < data.length; i += 1) {
                self.display_notification(
                    data[i].type,
                    data[i].timestamp,
                    data[i].subject,
                    data[i].text,
                    data[i].level);
                if (data[i].type != "notification") {
                    counter += 1;
                }
            }
            self.update_unread_counts(counter);
        }, "json");
};


CMS.CWSUtils.prototype.display_notification = function(
    type, timestamp, subject, text, level) {
    if (this.last_notification < timestamp) {
        this.last_notification = timestamp;
    }

    // TODO somehow display timestamp, subject and text

    var alert = $('<div class="alert alert-block notification">' +
                  '<a class="close" data-dismiss="alert" href="#">×</a>' +
                  '<h4 class="alert-heading"></h4>' +
                  '</div>');

    if (type == "message") {
        alert.children("h4").text($("#translation_new_message").text());
    } else if (type == "announcement") {
        alert.children("h4").text($("#translation_new_announcement").text());
    } else if (type == "question") {
        alert.children("h4").text($("#translation_new_answer").text());
    } else if (type == "notification") {
        alert.children("h4").text(subject);
        alert.append($("<span>" + text + "</span>"));
    }

    // The "warning" level is the default, so no check needed.
    if (level == "error") {
        alert.addClass("alert-error");
    } else if (level == "success") {
        alert.addClass("alert-success");
    }

    $("#notifications").prepend(alert);
};


CMS.CWSUtils.prototype.update_unread_counts = function(counter) {
    if (counter > 0) {
        this.unread_count += counter;
        $("#unread_count").text(
            $("#translation_unread").text().replace("%d", this.unread_count));
        $("#unread_count").removeClass("no_unread");
    }
};


/**
 * Return a string representation of the number with two digits.
 *
 * n (int): a number with one or two digits.
 * return (string): n as a string with two digits, maybe with a
 *     leading 0.
 */
CMS.CWSUtils.prototype.two_digits = function(n) {
    if (n < 10) {
        return "0" + n;
    } else {
        return "" + n;
    }
};


/**
 * Return the time of the given timestamp as "HH:MM:SS" in UTC.
 *
 * timestamp (float): a UNIX timestamp.
 * return (string): hours, minutes and seconds, zero-padded to two
 *     digits and colon-separated, of timestamp in UTC timezone.
 */
CMS.CWSUtils.prototype.format_time = function(timestamp) {
    var date = new Date(timestamp * 1000);
    return this.two_digits(date.getUTCHours()) + ":"
        + this.two_digits(date.getUTCMinutes()) + ":"
        + this.two_digits(date.getUTCSeconds());
};


CMS.CWSUtils.prototype.format_timedelta = function(timedelta) {
    // A negative time delta does not make sense, let's show zero to the user.
    if (timedelta < 0) {
        timedelta = 0;
    }

    var hours = Math.floor(timedelta / 3600);
    timedelta %= 3600;
    var minutes = Math.floor(timedelta / 60);
    timedelta %= 60;
    var seconds = Math.floor(timedelta);

    return this.two_digits(hours) + ":"
        + this.two_digits(minutes) + ":"
        + this.two_digits(seconds);
};


CMS.CWSUtils.prototype.update_time = function() {
    var now = $.now() / 1000;

    // FIXME This may cause some problems around DST boundaries, as it
    // is not adjusted because we consider it to be in UTC timezone.
    var server_timezoned_time = now - this.client_timestamp + this.server_timezoned_timestamp;
    $("#server_time").text(this.format_time(server_timezoned_time));

    var server_time = now - this.client_timestamp + this.server_timestamp;

    // TODO consider possible null values of this.current_phase_begin
    // and this.current_phase_end (they mean -inf and +inf
    // respectively)

    switch (this.phase) {
    case -2:
        // Contest hasn't started yet.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.url_root + "/";
        }
        $("#countdown_label").text(
            $("#translation_until_contest_starts").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case -1:
        // Contest has already started but user hasn't started its
        // time yet.
        $("#countdown_label").text(
            $("#translation_until_contest_ends").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case 0:
        // Contest is currently running.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.url_root + "/";
        }
        $("#countdown_label").text($("#translation_time_left").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +1:
        // User has already finished its time but contest hasn't
        // finished yet.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.url_root + "/";
        }
        $("#countdown_label").text(
            $("#translation_until_contest_ends").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +2:
        // Contest has already finished.
        $("#countdown_box").addClass("hidden");
        break;
    }
};

CMS.CWSUtils.prototype.switch_lang = function() {
    var cookie_path = this.url_root + "/";
    var lang = $("#lang").val();
    if (lang === "") {
        document.cookie = "language="
            + "; expires=Thu, 01 Jan 1970 00:00:00 GMT"
            + "; path=" + cookie_path;
    } else {
        var expires = new Date();
        expires.setFullYear(expires.getFullYear() + 1);
        document.cookie = "language=" + lang
            + "; expires=" + expires.toUTCString()
            + "; path=" + cookie_path;
    }
    location.reload();
};
