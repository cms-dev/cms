/**
 * Utility functions related to the front-end.
 */

var Utils = new function () {
    var self = this;

    self.init = function (timestamp, contest_start, contest_stop, phase) {
        self.last_notification = timestamp;
        self.timestamp = timestamp;
        self.contest_start = contest_start;
        self.contest_stop = contest_stop;
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
                      data[i].text);
                  counter += 1;
                }
                self.update_unread_counts(counter);
            }, "json");
    };

    self.display_notification = function (type, timestamp, subject, text) {
        if (self.last_notification < timestamp)
            self.last_notification = timestamp;

        // TODO somehow display timestamp, subject and text

        var alert = $('<div class="alert alert-block" style="position:absolute;right:20px;width:160px">' +
                      '<a class="close" data-dismiss="alert" href="#">×</a>' +
                      '<h4 class="alert-heading"></h4>' +
                      '</div>');

        if (type == "message") {
            alert.children("h4").text("New message");
        } else if (type == "announcement") {
            alert.children("h4").text("New announcement");
        } else if (type == "question") {
            alert.children("h4").text("New answer");
        }

        $("#notifications").append(alert);
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
        return date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate();
    };

    self.format_iso_time = function (timestamp) {
        var date = new Date(timestamp * 1000);
        if (date.getHours() < 10)
            return "0" + date.getHours() + ":" + date.getMinutes() + ":" + date.getSeconds();
        else
            return date.getHours() + ":" + date.getMinutes() + ":" + date.getSeconds();
    };

    self.format_iso_datetime = function (timestamp) {
        /* the result value differs from Date.toISOString() because if uses
           " " as a date/time separator (instead of "T") and because it stops
           at the seconds (and not at milliseconds) */
        return self.format_iso_date(timestamp) + " " + self.format_iso_time(timestamp);
    };

    self.get_time = function () {
        if (self.contest_stop != null)
            var sec_to_end = self.contest_stop - self.timestamp ;
        else
            var sec_to_end = Infinity;

        if (self.contest_start != null)
            var sec_to_start = self.contest_start - self.timestamp;
        else
            var sec_to_start = -Infinity;

        var now = new Date();

        var nowsec_to_end = sec_to_end - (now - firstDate) / 1000;
        var nowsec_to_start = sec_to_start - (now - firstDate) / 1000;
        if ((nowsec_to_end <= 0 && self.phase == 0 ) ||
            (nowsec_to_start <= 0 && self.phase == -1 ))
            window.location.href = url_root + "/";

        countdown = nowsec_to_end;

        if (self.phase == -1)
            countdown = nowsec_to_start;

        var hours = countdown / 60 / 60;
        var hoursR = Math.floor(hours);
        var minutes = countdown / 60 - (60*hoursR);
        var minutesR = Math.floor(minutes);
        var seconds = countdown - (60*60*hoursR) - (60*minutesR);
        var secondsR = Math.floor(seconds);
        if (minutesR < 10) m = "0" + minutesR;
        else m = minutesR;
        if (secondsR < 10) s = "0" + secondsR;
        else s = secondsR;

        if (self.remaining_div == null)
            self.remaining_div = $("#remaining");
        if (self.remaining_div != null)
            self.remaining_div.text(hoursR + ":" + m + ":" + s);
    };
};

