/* Contest Management System
 * Copyright © 2012-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
 * Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 * Copyright © 2013 Fabian Gundlach <320pointsguy@gmail.com>
 * Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
 * Copyright © 2018 Gregor Eesmaa <gregoreesmaa1@gmail.com>
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
 * Utility functions needed by AWS front-end.
 */

var CMS = CMS || {};

CMS.AWSUtils = function(url_root, timestamp,
                        contest_start, contest_stop,
                        analysis_start, analysis_stop,
                        phase) {
    this.url = CMS.AWSUtils.create_url_builder(url_root);
    this.first_date = new Date();
    this.last_notification = timestamp;
    this.timestamp = timestamp;
    this.contest_start = contest_start;
    this.contest_stop = contest_stop;
    this.analysis_start = analysis_start;
    this.analysis_stop = analysis_stop;
    this.phase = phase;
    this.file_asked_name = "";
    this.file_asked_url = "";

    // Ask permission for desktop notifications
    if ("Notification" in window) {
        Notification.requestPermission();
    }
};


CMS.AWSUtils.create_url_builder = function(url_root) {
    return function() {
        var url = url_root;
        for (var i = 0; i < arguments.length; ++i) {
            if (url.substr(-1) != "/") {
                url += "/";
            }
            url += encodeURIComponent(arguments[i]);
        }
        return url;
    };
};


/**
 * Displays a subpage over the current page with the specified
 * content.
 */
CMS.AWSUtils.prototype.display_subpage = function(elements) {
    // TODO: update jQuery to allow appending of arrays of elements.
    for (var i = 0; i < elements.length; ++i) {
        elements[i].appendTo($("#subpage_content"));
    }
    $("#subpage").show();
};


/**
 * Hides a subpage previously displayed.
 */
CMS.AWSUtils.prototype.hide_subpage = function() {
    $("#subpage").hide();
    $("#subpage_content").empty();
};


/**
 * This is called when we receive file content, or an error message.
 *
 * file_name (string): the name of the requested file
 * url (string): the url of the file
 * response (string): the file content
 * error (string): The error message, or null if the request is
 *     successful.
 */
CMS.AWSUtils.prototype.file_received = function(response, error) {
    var file_name = this.file_asked_name;
    var url = this.file_asked_url;
    var elements = [];
    if (error != null) {
        alert("File request failed.");
    } else {
        if (response.length > 100000) {
            elements.push($('<h1>').text(file_name));
            elements.push($('<a>').text("Download").prop("href", url));
            this.display_subpage(elements);
            return;
        }
        var pre_class = "";
        // TODO: add more languages.
        if (file_name.match(/.c(|pp)$/i)) {
            pre_class = "brush: cpp";
        } else if (file_name.match(/.pas$/i)) {
            pre_class = "brush: delphi";
        }
        elements.push($('<h1>').text(file_name));
        elements.push($('<a>').text("Download").prop("href", url));
        elements.push($('<pre>').text(response).prop("id", "source_container")
                      .prop("class", pre_class));

        this.display_subpage(elements);
        SyntaxHighlighter.highlight();
    }
};


/**
 * Displays a subpage with the content of the file at the specified
 * url.
 */
CMS.AWSUtils.prototype.show_file = function(file_name, url) {
    this.file_asked_name = file_name;
    this.file_asked_url = url;
    var file_received = this.bind_func(this, this.file_received);
    this.ajax_request(url, null, file_received);
};


/**
 * To be added to the onclick of an element named title_XXX. Hide/show
 * an element named XXX, and change the class of title_XXX between
 * toggling_on and toggling_off.
 */
CMS.AWSUtils.prototype.toggle_visibility = function() {
    var title = $(this);
    var item = $(this.id.replace("title_", "#").replace(".", "\\."));
    item.slideToggle("normal", function() {
        title.toggleClass("toggling_on toggling_off");
    });
};


/**
 * Display the notification to the user.
 *
 * type (string): can be "notification", "message", "question",
 *     "announcement".
 * timestamp (number): time of the notification.
 * subject (string): subject.
 * text (string): body of notification.
 */
CMS.AWSUtils.prototype.display_notification = function(type, timestamp,
                                                       subject, text,
                                                       contest_id) {
    if (this.last_notification < timestamp) {
        this.last_notification = timestamp;
    }
    var timestamp_int = parseInt(timestamp);
    var subject_string = $('<span>');
    if (type == "message") {
        subject_string = $("<span>").text("Private message. ");
    } else if (type == "announcement") {
        subject_string = $("<span>").text("Announcement. ");
    } else if (type == "question") {
        subject_string = $("<span>").text("Reply to your question. ");
    } else if (type == "new_question") {
        subject_string = $("<a>").text("New question: ")
            .prop("href", this.url("contest", contest_id, "questions"));
    }

    var self = this;
    var outer = $("#notifications");
    var timestamp_div = $("<div>")
        .addClass("notification_timestamp")
        .text(timestamp_int != 0 ? this.format_time_or_date(timestamp_int) : "");
    var subject_div = $("<div>")
        .addClass("notification_subject")
        .append(subject_string);
    var close_div = $('<div>').html("&times;").addClass("notification_close")
        .click(function() { self.close_notification(this); });
    var inner =
        $('<div>').addClass("notification").addClass("notification_type_" + type)
            .append(close_div)
            .append($('<div>').addClass("notification_msg")
                    .append(timestamp_div)
                    .append(subject_div.append($("<span>").text(subject)))
                    .append($("<div>").addClass("notification_text").text(text))
                   );
    outer.append(inner);

    // Trigger a desktop notification as well (but only if it's needed)
    if (type !== "notification") {
        this.desktop_notification(type, timestamp, subject, text);
    }
};


CMS.AWSUtils.prototype.desktop_notification = function(type, timestamp,
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


/**
 * Update the number of unread private and public messages in the span
 * next to the title of the sections "overview" and "communication".
 *
 * delta_public (int): how many public unreads to add.
 * delta_private (int): how many public unreads to add.
 */
CMS.AWSUtils.prototype.update_unread_counts = function(delta_public, delta_private) {
    var unread_public = $("#unread_public");
    var unread_private = $("#unread_private");
    if (unread_public) {
        var msgs_public = parseInt(unread_public.text());
        msgs_public += delta_public;
        unread_public.text(msgs_public);
        if (msgs_public > 0) {
            unread_public.show();
        } else {
            unread_public.hide();
        }
    }
    if (unread_private) {
        var msgs_private = parseInt(unread_private.text());
        msgs_private += delta_private;
        unread_private.text(msgs_private);
        if (msgs_private > 0) {
            unread_private.show();
        } else {
            unread_private.hide();
        }
    }
};


/**
 * Ask CWS (via ajax, not rpc) to send to the user the new
 * notifications.
 */
CMS.AWSUtils.prototype.update_notifications = function() {
    var display_notification = this.bind_func(this, this.display_notification);
    var update_unread_counts = this.bind_func(this, this.update_unread_counts);
    this.ajax_request(
        this.url("notifications"),
        "last_notification=" + this.last_notification,
        function(response, error) {
            if (error == null) {
                response = JSON.parse(response);
                var msgs_public = 0;
                var msgs_private = 0;
                for (var i = 0; i < response.length; i++) {
                    display_notification(
                        response[i].type,
                        response[i].timestamp,
                        response[i].subject,
                        response[i].text,
                        response[i].contest_id);
                    if (response[i].type == "announcement") {
                        msgs_public++;
                    } else if (response[i].type == "question"
                               || response[i].type == "message") {
                        msgs_private++;
                    }
                }
                update_unread_counts(msgs_public, msgs_private);
            }
        });
};


/**
 * For the close button of a notification.
 */
CMS.AWSUtils.prototype.close_notification = function(item) {
    var bubble = item.parentNode;
    if (bubble.className.indexOf("notification_type_announcement") != -1) {
        this.update_unread_counts(-1, 0);
    } else if (bubble.className.indexOf("notification_type_question") != -1
               || bubble.className.indexOf("notification_type_message") != -1) {
        this.update_unread_counts(0, -1);
    }
    bubble.parentNode.removeChild(item.parentNode);
};


/**
 * Provides table row comparator for specified column and order.
 */
function get_table_row_comparator(column_idx, numeric, ascending) {
    return function(a, b) {
        var valA = $(a).children("td").eq(column_idx).text();
        var valB = $(b).children("td").eq(column_idx).text();
        var result = numeric
            ? Number(valA) - Number(valB)
            : valA.localeCompare(valB);
        return ascending ? -result : result;
    }
}


/**
 * Sorts specified table by specified column in specified order.
 */
CMS.AWSUtils.sort_table = function(table, column_idx, ascending) {
    var initial_column_idx = table.data("initial_sort_column_idx");
    var ranks_column = table.data("ranks_column");
    column_idx += ranks_column ? 1 : 0;
    var table_rows = table
        .children("tbody")
        .children("tr");
    var column_header = table
        .children("thead")
        .children("tr")
        .children("th")
        .eq(column_idx);
    var settings = (column_header.attr("data-sort-settings") || "").split(" ");

    var numeric = settings.indexOf("numeric") >= 0;

    // If specified, flip column's natural order, e.g. due to meaning of values.
    if (settings.indexOf("reversed") >= 0) {
        ascending = !ascending;
    }

    // Normalize column index, converting negative to positive from the end.
    column_idx = column_header.index();

    // Reassign arrows to headers
    table.find(".column-sort").html("&varr;");
    column_header.find(".column-sort").html(ascending ? "&uarr;" : "&darr;");

    // Do the sorting, by initial column and then by selected column.
    table_rows
        .sort(get_table_row_comparator(initial_column_idx, numeric, ascending))
        .sort(get_table_row_comparator(column_idx, numeric, ascending))
        .each(function(idx, row) {
            table.children("tbody").append(row)
        });

    if (ranks_column) {
        table_rows.each(function(idx, row) {
            $(row).children("td").first().text(idx + 1)
        });
    }
};


/**
 * Makes table sortable, adding ranks column and sorting buttons in header.
 */
CMS.AWSUtils.init_table_sort = function(table, ranks_column,
                                        initial_column_idx,
                                        initial_ascending) {
    table.addClass("sortable");
    var table_column_headers = table
        .children("thead")
        .children("tr");
    var table_rows = table
        .children("tbody")
        .children("tr");

    // Normalize column index, converting negative to positive from the end.
    initial_column_idx = table_column_headers
        .children("th")
        .eq(initial_column_idx)
        .index();

    table.data("ranks_column", ranks_column);
    table.data("initial_sort_column_idx", initial_column_idx);

    // Declaring sort settings.
    var previous_column_idx = initial_column_idx;
    var ascending = initial_ascending;

    // Add sorting indicators to column headers
    table_column_headers
        .children("th")
        .each(function(column_idx, header) {
            $("<a/>", {
                href: "#",
                class: "column-sort",
                click: function() {
                    ascending = !ascending && previous_column_idx == column_idx;
                    previous_column_idx = column_idx;
                    CMS.AWSUtils.sort_table(table, column_idx, ascending);
                }
            }).appendTo(header);
        });

    // Add ranks column
    if (ranks_column) {
        table_column_headers.prepend("<th>#</th>");
        table_rows.prepend("<td></td>");
    }

    // Do initial sorting
    CMS.AWSUtils.sort_table(table, initial_column_idx, initial_ascending);
};


/**
 * Return a string representation of the number with two digits.
 *
 * n (int): a number with one or two digits.
 * return (string): n as a string with two digits, maybe with a
 *     leading 0.
 */
CMS.AWSUtils.prototype.two_digits = function(n) {
    if (n < 10) {
        return "0" + n;
    } else {
        return "" + n;
    }
};


/**
 * Update the remaining time showed in the "remaining" div.
 *
 * timer (int): handle for the timer that called this function, or -1 if none
 */
CMS.AWSUtils.prototype.update_remaining_time = function(timer = -1) {
    // We assume this.phase always is the correct phase (since this
    // method also refreshes the page when the phase changes).
    var relevant_timestamp = null;
    var text = null;
    if (this.phase === -1) {
        relevant_timestamp = this.contest_start;
        text = "To start of contest: "
    } else if (this.phase === 0) {
        relevant_timestamp = this.contest_stop;
        text = "To end of contest: "
    } else if (this.phase === 1) {
        relevant_timestamp = this.analysis_start;
        text = "To start of analysis: "
    } else if (this.phase === 2) {
        relevant_timestamp = this.analysis_stop;
        text = "To end of analysis: "
    }

    // We are in phase 3, nothing to show.
    if (relevant_timestamp === null) {
        return;
    }

    // Compute actual seconds to next phase value, and if negative we
    // refresh to update the phase.
    var now = new Date();
    var countdown_sec =
        relevant_timestamp - this.timestamp - (now - this.first_date) / 1000;
    if (countdown_sec <= 0) {
        clearInterval(timer);
        location.reload();
    }

    $("#remaining_text").text(text);
    $("#remaining_value").text(this.format_countdown(countdown_sec));
};


/**
 * Check the status returned by an RPC call and display the error if
 * necessary, otherwise redirect to another page.
 *
 * url (string): the destination page if response is ok.
 * response (dict): the response returned by the RPC.
 */
CMS.AWSUtils.prototype.redirect_if_ok = function(url, response) {
    var msg = this.standard_response(response);
    if (msg != "") {
        alert('Unable to invalidate (' + msg + ').');
    } else {
        location.href = url;
    }
};


/**
 * Represent in a nice looking way a couple (job_type, submission_id)
 * coming from the backend.
 *
 * job (array): a tuple (job_type, submission_id, dataset_id)
 * returns (string): nice representation of job
 */
CMS.AWSUtils.prototype.repr_job = function(job) {
    var job_type = "???";
    var object_type = "???";
    if (job == null) {
        return "N/A";
    } else if (job == "disabled") {
        return "Worker disabled";
    } else if (job["type"] == 'compile') {
        job_type = 'Compiling';
        object_type = 'submission';
    } else if (job["type"] == 'evaluate') {
        job_type = 'Evaluating';
        object_type = 'submission';
    } else if (job["type"] == 'compile_test') {
        job_type = 'Compiling';
        object_type = 'user_test';
    } else if (job["type"] == 'evaluate_test') {
        job_type = 'Evaluating';
        object_type = 'user_test';
    }

    if (object_type == 'submission') {
        return job_type
            + ' the <a href="' + this.url("submission", job["object_id"], job["dataset_id"]) + '">result</a>'
            + ' of <a href="' + this.url("submission", job["object_id"]) + '">submission ' + job["object_id"] + '</a>'
            + ' on <a href="' + this.url("dataset", job["dataset_id"]) + '">dataset ' + job["dataset_id"] + '</a>'
            + (job_type == 'Evaluating' && job["multiplicity"]
               ? " [" + job["multiplicity"] + " time(s) in queue]"
               : "")
            + (job["testcase_codename"]
               ? " [testcase: `" + job["testcase_codename"] + "']"
               : "");
    } else {
        return job_type
            + ' the result'
            + ' of user_test ' + job["object_id"]
            + ' on <a href="' + this.url("dataset", job["dataset_id"]) + '">dataset ' + job["dataset_id"] + '</a>';
    }
};


/**
 * Format time as hours, minutes and seconds ago.
 *
 * time (int): a unix time.
 * returns (string): representation of time as "[[H hour(s), ]M
 *     minute(s), ]S second(s)".
 */
CMS.AWSUtils.prototype.repr_time_ago = function(time) {
    if (time == null) {
        return "N/A";
    }
    var diff = parseInt((new Date()).getTime() / 1000 - time);
    var res = "";

    var s = diff % 60;
    diff = diff - s;
    res = s + " second(s)";
    if (diff == 0) {
        return res;
    }
    diff /= 60;

    var m = diff % 60;
    diff -= m;
    res = m + " minute(s), " + res;
    if (diff == 0) {
        return res;
    }
    diff /= 60;

    var h = diff;
    res = h + " hour(s), " + res;
    return res;
};


/**
 * Format time as hours, minutes and seconds ago.
 *
 * time (int): a unix time.
 * returns (string): representation of time as "[[HH:]MM:]SS]".
 */
CMS.AWSUtils.prototype.repr_time_ago_short = function(time) {
    if (time == null) {
        return "N/A";
    }
    var diff = parseInt((new Date()).getTime() / 1000 - time);
    var res = "";

    var s = diff % 60;
    diff = diff - s;
    if (diff > 0) {
        res = this.two_digits(s);
    } else {
        return "" + s;
    }
    diff /= 60;

    var m = diff % 60;
    diff -= m;
    if (diff > 0) {
        res = this.two_digits(m) + ":" + res;
    } else {
        return m + ":" + res;
    }
    diff /= 60;

    var h = diff;
    res = h + ":" + res;
    return res;
};


/**
 * Return timestamp formatted as HH:MM:SS.
 *
 * timestamp (int): unix time.
 * return (string): timestamp formatted as above.
 */
CMS.AWSUtils.prototype.format_time = function(timestamp) {
    var date = new Date(timestamp * 1000);
    var hours = this.two_digits(date.getHours());
    var minutes = this.two_digits(date.getMinutes());
    var seconds = this.two_digits(date.getSeconds());
    return hours + ":" + minutes + ":" + seconds;
};


/**
 * Return the time difference formatted as HHHH:MM:SS.
 *
 * timestamp (int): a time delta in s.
 * return (string): timestamp formatted as above.
 */
CMS.AWSUtils.prototype.format_countdown = function(countdown) {
    var hours = countdown / 60 / 60;
    var hours_rounded = Math.floor(hours);
    var minutes = countdown / 60 - (60 * hours_rounded);
    var minutes_rounded = Math.floor(minutes);
    var seconds = countdown - (60 * 60 * hours_rounded)
        - (60 * minutes_rounded);
    var seconds_rounded = Math.floor(seconds);
    return hours_rounded + ":" + this.two_digits(minutes_rounded) + ":"
        + this.two_digits(seconds_rounded);
};


/**
 * Return timestamp formatted as HH:MM:SS, dd/mm/yyyy.
 *
 * timestamp (int): unix time.
 * return (string): timestamp formatted as above.
 */
CMS.AWSUtils.prototype.format_datetime = function(timestamp) {
    var time = this.format_time(timestamp);
    var date = new Date(timestamp * 1000);
    var days = this.two_digits(date.getDate());
    var months = this.two_digits(date.getMonth() + 1); // months are 0-11
    var years = date.getFullYear();
    return time + ", " + days + "/" + months + "/" + years;
};


/**
 * Return timestamp formatted as HH:MM:SS if the date is the same date
 * as today, as a complete date + time if the date is different.
 *
 * timestamp (int): unix time.
 * return (string): timestamp formatted as above.
 */
CMS.AWSUtils.prototype.format_time_or_date = function(timestamp) {
    var today = (new Date()).toDateString();
    var date = new Date(timestamp * 1000);
    if (today == date.toDateString()) {
        return this.format_time(timestamp);
    } else {
        return this.format_datetime(timestamp);
    }
};


/**
 * If the response is for a standard error (unconnected, ...)  then
 * return an appropriate message, otherwise return "".
 *
 * response (object): an rpc response.
 * return (string): appropriate message or "".
 */
CMS.AWSUtils.prototype.standard_response = function(response) {
    if (response['status'] != 'ok') {
        var msg = "Unexpected reply `" + response['status']
            + "'. This should not happen.";
        if (response['status'] == 'unconnected') {
            msg = 'Service not connected.';
        } else if (response['status'] == 'not authorized') {
            msg = "You are not authorized to call this method.";
        } else if (response['status'] == 'fail') {
            msg = "Call to service failed.";
        }
        return msg;
    }
    return "";
};


CMS.AWSUtils.prototype.show_page = function(item, page, elements_per_page) {
    elements_per_page = elements_per_page || 5;

    var children = $("#paged_content_" + item).children();
    var npages = Math.ceil(children.length / elements_per_page);
    var final_page = Math.min(page, npages) - 1;
    children.each(function(i, child) {
        if (i >= elements_per_page * final_page
            && i < elements_per_page * (final_page + 1)) {
            $(child).show();
        } else {
            $(child).hide();
        }
    });

    var self = this;
    var selector = $("#page_selector_" + item);
    selector.empty();
    selector.append("Pages: ");
    for (var i = 1; i <= npages; i++) {
        if (i != page) {
            selector.append($("<a>").text(i + " ")
                            .click(function(j) {
                                return function() {
                                    self.show_page(item, j, elements_per_page);
                                    return false;
                                };
                            }(i)));
        } else {
            selector.append(i + " ");
        }
    }
};


/**
 * Returns a function binded to an object - useful in case we need to
 * send callback that needs to access to the "this" object.
 *
 * Example:
 * var f = this.utils.bind_func(this, this.cb);
 * function_that_needs_a_cb(function(data) { f(data); });
 *
 * object (object): the object to bind to
 * method (function): the function to bind
 * returns (function): the binded function
 */
CMS.AWSUtils.prototype.bind_func = function(object, method) {
    return function() {
        return method.apply(object, arguments);
    };
};


/**
 * Perform an AJAX GET request.
 *
 * url (string): the url of the resource.
 * args (string|null): the arguments already encoded.
 * callback (function): the function to call with the response.
 */
CMS.AWSUtils.prototype.ajax_request = function(url, args, callback) {
    if (args != null) {
        url = url + "?" + args;
    }
    var jqxhr = $.get(url);
    jqxhr.done(function(data) {
        callback(data, null);
    });
    jqxhr.fail(function() {
        callback(null, jqxhr.status);
    });
};


/**
 * Sends a request and on success redirect to the page
 * specified in the response, if present.
 */
CMS.AWSUtils.ajax_edit_request = function(type, url) {
    var settings = {
        "type": type,
        headers: {"X-XSRFToken": get_cookie("_xsrf")}
    };
    settings["success"] = function(data_redirect_url) {
        if (data_redirect_url) {
            window.location.replace(data_redirect_url);
        }
    };
    $.ajax(url, settings);
};


/**
 * Sends a delete request and on success redirect to the page
 * specified in the response, if present.
 */
CMS.AWSUtils.ajax_delete = function(url) {
    CMS.AWSUtils.ajax_edit_request("DELETE", url);
};


/**
 * Sends a post request and on success. See AWSUtils.ajax_request
 * for more details.
 */
CMS.AWSUtils.ajax_post = function(url) {
    CMS.AWSUtils.ajax_edit_request("POST", url);
};
