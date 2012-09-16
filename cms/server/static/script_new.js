/**
 * Utility functions related to the front-end.
 */

var Utils = new function () {
    var self = this;

    self.init = function (timestamp, contest_start, contest_stop, current_phase_end, phase) {
        self.last_notification = timestamp;
        self.server_timestamp = timestamp;
        self.client_timestamp = $.now() / 1000;
        self.contest_start = contest_start;
        self.contest_stop = contest_stop;
        self.current_phase_end = current_phase_end;
        self.phase = phase;
        self.remaining_div = null;
        self.unread_count = 0;
    };

    self.update_notifications = function () {
        $.get(
            url_root + "/notifications",
            {"last_notification": self.last_notification},
            function (data) {
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

    self.display_notification = function (type, timestamp, subject, text, level) {
        if (self.last_notification < timestamp)
            self.last_notification = timestamp;

        // TODO somehow display timestamp, subject and text

        var alert = $('<div class="alert alert-block notification">' +
                      '<a class="close" data-dismiss="alert" href="#">×</a>' +
                      '<h4 class="alert-heading"></h4>' +
                      '</div>');

        if (type == "message") {
            alert.children("h4").text("New message");
        } else if (type == "announcement") {
            alert.children("h4").text("New announcement");
        } else if (type == "question") {
            alert.children("h4").text("New answer");
        } else if (type == "notification") {
            alert.children("h4").text(subject);
            alert.append($("<span>" + text + "</span>"));
        }

        // the "warning" level is the default, so no check needed
        if (level == "error") {
            alert.addClass("alert-error");
        } else if (level == "success") {
            alert.addClass("alert-success");
        }

        $("#notifications").prepend(alert);
    };

    self.update_unread_counts = function (counter) {
        if (counter > 0) {
            self.unread_count += counter;
            $("#unread_count").text(self.unread_count + " unread");
            $("#unread_count").removeClass("no_unread");
        }
    };

    self.format_iso_date = function (timestamp) {
        var date = new Date(timestamp * 1000);
        var result = date.getFullYear() + "-";
        if (date.getMonth() < 9)
            result += "0";
        result += (date.getMonth() + 1) + "-";
        if (date.getDate() < 10)
            result += "0";
        result += date.getDate();
        return result;
    };

    self.format_time = function (timestamp) {
        var date = new Date(timestamp * 1000);
        var result = "";
        if (date.getHours() < 10)
            result += "0";
        result += date.getHours() + ":"
        if (date.getMinutes() < 10)
            result += "0";
        result += date.getMinutes() + ":"
        if (date.getSeconds() < 10)
            result += "0";
        result += date.getSeconds();
        return result;
    };

    self.format_iso_datetime = function (timestamp) {
        /* the result value differs from Date.toISOString() because if uses
           " " as a date/time separator (instead of "T") and because it stops
           at the seconds (and not at milliseconds) */
        return self.format_iso_date(timestamp) + " " + self.format_time(timestamp);
    };

    self.format_timedelta = function (timedelta) {
        var hours = Math.floor(timedelta / 3600);
        timedelta %= 3600;
        var minutes = Math.floor(timedelta / 60);
        timedelta %= 60;
        var seconds = Math.floor(timedelta);
        var result = "";
        if (hours < 10)
            result += "0";
        result += hours + ":"
        if (minutes < 10)
            result += "0";
        result += minutes + ":"
        if (seconds < 10)
            result += "0";
        result += seconds;
        return result;
    }

    self.update_time = function () {
        var now = $.now() / 1000;

        var server_time = now - self.client_timestamp + self.server_timestamp;
        $("#server_time").text(self.format_time(server_time));

        // TODO consider possible null values of contest.start and contest.stop (they mean -inf and +inf)
        // FIXME use server_time instead of now
        // FIXME localize strings

        switch (self.phase) {
        case -2:
            // contest hasn't started yet
            if (now >= self.current_phase_end) {
                window.location.href = url_root + "/";
            }
            $("#countdown_label").text("Until contest starts:");
            $("#countdown").text(self.format_timedelta(self.current_phase_end - now));
            break;
        case -1:
            // contest has already started but user hasn't started its time yet
            $("#countdown_label").text("Until contest ends:");
            $("#countdown").text(self.format_timedelta(self.current_phase_end - now));
            break;
        case 0:
            // contest is currently running
            if (now >= self.current_phase_end) {
                window.location.href = url_root + "/";
            }
            $("#countdown_label").text("Time left:");
            $("#countdown").text(self.format_timedelta(self.current_phase_end - now));
            break;
        case +1:
            // user has already finished its time but contest hasn't finished yet
            if (now >= self.current_phase_end) {
                window.location.href = url_root + "/";
            }
            $("#countdown_label").text("Until contest ends:");
            $("#countdown").text(self.format_timedelta(self.current_phase_end - now));
            break;
        case +2:
            // contest has already finished
            $("#countdown_box").addClass("hidden");
            break;
        }
    };
};

