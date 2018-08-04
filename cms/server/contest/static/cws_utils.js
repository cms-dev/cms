/* Contest Management System
 * Copyright © 2012-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
 * Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 * Copyright © 2013 Vittorio Gambaletta <VittGam@VittGam.net>
 * Copyright © 2018 William Di Luigi <williamdiluigi@gmail.com>
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

CMS.CWSUtils = function(url_root, contest_root, contest_name, timestamp, timezoned_timestamp,
                        current_phase_begin, current_phase_end, phase) {
    this.url = CMS.CWSUtils.create_url_builder(url_root);
    this.contest_url = CMS.CWSUtils.create_url_builder(contest_root);
    this.contest_name = contest_name;
    this.last_notification = localStorage.getItem(this.contest_name + "_last_notification");
    if (this.last_notification !== null) {
        this.last_notification = parseFloat(this.last_notification);
    }
    this.server_timestamp = timestamp;
    this.server_timezoned_timestamp = timezoned_timestamp;
    this.client_timestamp = $.now() / 1000;
    this.current_phase_begin = current_phase_begin;
    this.current_phase_end = current_phase_end;
    this.phase = phase;
    this.remaining_div = null;
    this.unread_count = localStorage.getItem(this.contest_name + "_unread_count");
    this.unread_count = this.unread_count !== null ? parseInt(this.unread_count) : 0;

    // Ask permission for desktop notifications
    if ("Notification" in window) {
        Notification.requestPermission();
    }
};


CMS.CWSUtils.create_url_builder = function(url_root) {
    return function() {
        var url = url_root;
        for (let component of arguments) {
            if (url.substr(-1) != "/") {
                url += "/";
            }
            url += encodeURIComponent(component);
        }
        return url;
    };
};


CMS.CWSUtils.prototype.update_notifications = function(hush) {
    var self = this;
    $.get(
        this.contest_url("notifications"),
        this.last_notification !== null ? {"last_notification": this.last_notification} : {},
        function(data) {
            for (var i = 0; i < data.length; i += 1) {
                self.display_notification(
                    data[i].type,
                    data[i].timestamp,
                    data[i].subject,
                    data[i].text,
                    data[i].level,
                    hush);
                if (data[i].type != "notification") {
                    self.update_unread_count(1);
                    self.update_last_notification(data[i].timestamp);
                }
            }
        }, "json");
};


CMS.CWSUtils.prototype.update_stats = function(onLoading, onData) {
    var self = this;

    onLoading(true);

    $.get(
        this.contest_url("stats"),
        {},
        function(data) {
            onData(data);

            onLoading(false);
        },
        "json"
    );
};


CMS.CWSUtils.prototype.display_notification = function(type, timestamp,
                                                       subject, text,
                                                       level, hush) {
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

    // Trigger a desktop notification as well (but only if it's needed)
    if (type !== "notification" && !hush) {
        this.desktop_notification(type, timestamp, subject, text);
    }
};


CMS.CWSUtils.prototype.desktop_notification = function(type, timestamp,
                                                       subject, text) {
    // Check desktop notifications support
    if (!("Notification" in window)) {
        return;
    }

    // Ask again, if it was not explicitly denied
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
        Notification.requestPermission();
    }

    // Create notification
    if (Notification.permission === "granted") {
        new Notification(subject, {
            "body": text,
            "icon": this.url("static", "favicon.ico")
        });
    }
};


CMS.CWSUtils.prototype.update_unread_count = function(delta, value) {
    if (delta > 0) {
        this.unread_count += delta;
    }
    if (value !== undefined) {
        this.unread_count = value;
    }
    localStorage.setItem(this.contest_name + "_unread_count", this.unread_count.toString());
    $("#unread_count").text(
        $("#translation_unread").text().replace("%d", this.unread_count));
    $("#unread_count").toggleClass("no_unread", this.unread_count === 0);
};


CMS.CWSUtils.prototype.update_last_notification = function(timestamp) {
    if (this.last_notification === null || timestamp > this.last_notification) {
        this.last_notification = timestamp;
        localStorage.setItem(this.contest_name + "_last_notification", this.last_notification.toString());
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


CMS.CWSUtils.prototype.update_time = function(usaco_like_contest) {
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
            window.location.href = this.contest_url();
        }
        $("#countdown_label").text(
            $("#translation_until_contest_starts").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case -1:
        // Contest has already started but user is not competing yet,
        // either because they haven't started the per user time yet,
        // or because their start was delayed.
        if (usaco_like_contest) {
            $("#countdown_label").text(
                $("#translation_until_contest_ends").text());
        } else {
            $("#countdown_label").text(
                $("#translation_until_contest_starts").text());
        }
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case 0:
        // Contest is currently running.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.contest_url();
        }
        $("#countdown_label").text($("#translation_time_left").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +1:
        // User has already finished its time but contest hasn't
        // finished yet.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.contest_url();
        }
        $("#countdown_label").text(
            $("#translation_until_contest_ends").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +2:
        // Contest has already finished but analysis mode hasn't started yet.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.contest_url();
        }
        $("#countdown_label").text(
            $("#translation_until_analysis_starts").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +3:
        // Contest has already finished. Analysis mode is running.
        if (server_time >= this.current_phase_end) {
            window.location.href = this.contest_url();
        }
        $("#countdown_label").text(
            $("#translation_until_analysis_ends").text());
        $("#countdown").text(
            this.format_timedelta(this.current_phase_end - server_time));
        break;
    case +4:
        // Contest has already finished and analysis mode is either disabled
        // or finished.
        $("#countdown_box").addClass("hidden");
        break;
    }
};

/* Taken from https://developer.mozilla.org/en-US/docs/Web/API/Document/cookie#Using_relative_URLs_in_the_path_parameter */
CMS.CWSUtils.prototype.rel_to_abs = function(sRelPath) {
    var nUpLn, sDir = "", sPath = location.pathname.replace(/[^\/]*$/, sRelPath.replace(/(\/|^)(?:\.?\/+)+/g, "$1"));
    for (var nEnd, nStart = 0; nEnd = sPath.indexOf("/../", nStart), nEnd > -1; nStart = nEnd + nUpLn) {
        nUpLn = /^\/(?:\.\.\/)*/.exec(sPath.slice(nEnd))[0].length;
        sDir = (sDir + sPath.substring(nStart, nEnd)).replace(new RegExp("(?:\\\/+[^\\\/]*){0," + ((nUpLn - 1) / 3) + "}$"), "/");
    }
    return sDir + sPath.substr(nStart);
};

CMS.CWSUtils.prototype.switch_lang = function() {
    var cookie_path = this.rel_to_abs(this.contest_url() + "/").slice(0, -1) || "/";
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

CMS.CWSUtils.filter_languages = function(options, inputs) {
    var exts = [];
    for (var i = 0; i < inputs.length; i++) {
        exts.push('.' + inputs[i].value.match(/[^.]*$/)[0]);
    }
    // Find all languages that should be enabled.
    var enabled = {};
    var anyEnabled = false;
    for (var lang in LANGUAGES) {
        for (i = 0; i < exts.length; i++) {
            if (LANGUAGES[lang][exts[i]]) {
                enabled[lang] = true;
                anyEnabled = true;
                break;
            }
        }
    }
    // If no language matches the extension, enable all and let the user
    // select.
    if (!anyEnabled) {
        options.removeAttr('disabled');
        return;
    }

    // Otherwise, disable all languages that do not match the extension.
    var isSelectedDisabled = false;
    options.each(function(i, option) {
        if (enabled[option.value]) {
            $(option).removeAttr('disabled');
        } else {
            $(option).attr('disabled', 'disabled');
            if (option.selected) {
                isSelectedDisabled = true;
            }
        }
    });
    // Else, if the current selected is disabled, select one that is enabled.
    if (isSelectedDisabled) {
        for (i = 0; i < options.length; i++) {
            if ($(options[i]).attr('disabled') != 'disabled') {
                options[i].selected = true;
                break;
            }
        }
    }
};

