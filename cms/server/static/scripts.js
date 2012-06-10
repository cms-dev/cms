/**
 * Utility functions related to the front-end.
 */

(function() {

    Utils = function(timestamp, contest_start, contest_stop, phase)
    {
        this.last_notification = timestamp;
        this.timestamp = timestamp;
        this.contest_start = contest_start;
        this.contest_stop = contest_stop;
        this.phase = phase;
        this.remaining_div = null;
        this.file_asked_name = "";
        this.file_asked_url = "";
    }

    Utils.prototype =
    {
        /**
         * Displays a subpage over the current page with the
         * specified content.
         */
        display_subpage: function(content)
        {
            var subpage = document.getElementById("subpage");
            var subcontent = document.getElementById("subpage_content");
            subpage.style.display = "block";
            subcontent.innerHTML = content;
        },

        /**
         * Hides a subpage previously displayed.
         */
        hide_subpage: function()
        {
            var subpage = document.getElementById("subpage");
            subpage.style.display="none";
        },

        /**
         * This is called when we receive file content, or an error message.
         *
         * file_name (string): the name of the requested file
         * url (string): the url of the file
         * response (string): the file content
         * error (string): The error message, or null if the request
                           is successful.
         */
        __file_received: function(response, error)
        {
            file_name = this.file_asked_name;
            url = this.file_asked_url;
            var page="";
            if(error != null)
            {
                alert("File request failed.");
            }
            else
            {
                if(response.length > 100000)
                {
                    page = "<h1>" + file_name + "</h1>" +
                                "<a href=\"" + url + "\">Download</a>";

                    utils.display_subpage(page);
                    return;
                }
                var escaped_response = utils.escape_html(response)
                var pre_class="";
                if(file_name.match(/.c(|pp)$/i))
                {
                  pre_class = "brush: cpp";
                }
                else if (file_name.match(/.pas$/i))
                {
                  pre_class = "brush: delphi";
                }
                page = "<h1>" + file_name + "</h1>" +
                            "<a href=\"" + url + "\">Download</a>" +
                            "<pre id=\"source_container\" class=\"" + pre_class + "\">" +
                            escaped_response + "</pre>";

                utils.display_subpage(page);
                SyntaxHighlighter.highlight()
            }
        },

        /**
        * Displays a subpage with the content of the file at the
        * specified url.
        */
        show_file: function(file_name, url)
        {
            this.file_asked_filename = file_name;
            this.file_asked_url = url;
            var file_received = cmsutils.bind_func(this,
                                                   this.__file_received);
            cmsutils.ajax_request(url, null, file_received);
        },

        /**
         * To be added to the onclick of an element named
         * title_XXX. Hide/show an element named XXX, and change the
         * class of title_XXX between toggling_on and toggling_off
         */
        toggle_visibility: function()
        {
            var title = $(this);
            var item = $(this.id.replace("title_", "#").replace(".", "\\."));
            item.slideToggle("normal", function() {title.toggleClass("toggling_on toggling_off")});
        },

        /**
         * Display the notification to the user.
         *
         * type (string): can be "notification", "message", "question",
         *                "announcement".
         * timestamp (int): time of the notification.
         * subject (string): subject.
         * text (string): body of notification.
         */
        display_notification: function(type, timestamp, subject, text)
        {
            if (this.last_notification < timestamp)
                this.last_notification = timestamp;
            var div = document.getElementById("notifications");
            var s = '<div class="notification notification_type_' + type + '">' +
                '<div class="notification_close" ' +
                'onclick="utils.close_notification(this);">&times;' +
                '</div><div class="notification_msg">' +
                '<div class="notification_timestamp">' +
                this.format_time_or_date(timestamp) +
                '</div>';

            s += '<div class="notification_subject">'
            if (type == "message")
                s += 'Private message. ';
            else if (type == "announcement")
                s += 'Announcement. ';
            else if (type == "question")
                s += 'Reply to your question. ';
            else if (type == "new_question")
                s += '<a href="' + url_root + '/questions/1">New question</a>: ';

            s += utils.escape_html(subject) + '</div>';
            s += '<div class="notification_text">';
            s += utils.escape_html(text);
            s += '</div></div></div>';
            div.innerHTML += s;
        },

        /**
         * Update the number of unread private and public messages in
         * the span next to the title of the sections "overview" and
         * "communication"
         *
         * delta_public (int): how many public unreads to add.
         * delta_private (int): how many public unreads to add.
         */
        update_unread_counts: function(delta_public, delta_private)
        {
            var unread_public = document.getElementById("unread_public")
            var unread_private = document.getElementById("unread_private")
            var msgs_public = "";
            var msgs_private = "";
            if (unread_public)
            {
                var msg_public = parseInt(unread_public.innerHTML);
                msgs_public += delta_public;
                unread_public.innerHTML = msgs_public;
                if (msgs_public > 0)
                    unread_public.style.display = "inline-block"
                else
                    unread_public.style.display = "none"
            }
            if (unread_private)
            {
                msg_private = parseInt(unread_private.innerHTML);
                msgs_private += delta_private;
                unread_private.innerHTML = msgs_private;
                if (msgs_private > 0)
                    unread_private.style.display = "inline-block"
                else
                    unread_private.style.display = "none"
            }
        },

        /**
         * Ask CWS (via ajax, not rpc) to send to the user the new
         * notifications.
         */
        update_notifications: function()
        {
            display_notification = cmsutils.bind_func(this,
                                                      this.display_notification);
            update_unread_counts = cmsutils.bind_func(this,
                                                      this.update_unread_counts);
            cmsutils.ajax_request(url_root + "/notifications",
                                  "last_notification=" + this.last_notification,
                                  function(response, error)
                                  {
                                      if(error == null)
                                      {
                                          response = JSON.parse(response);
                                          var msgs_public = 0;
                                          var msgs_private = 0;
                                          for (var i = 0; i < response.length; i++)
                                          {
                                              display_notification(
                                                  response[i].type,
                                                  parseInt(response[i].timestamp),
                                                  response[i].subject,
                                                  response[i].text);
                                              if (response[i].type == "announcement")
                                                  msgs_public++;
                                              else if (response[i].type == "question" || response[i].type == "message")
                                                  msgs_private++;
                                          }
                                          update_unread_counts(msgs_public, msgs_private);
                                      }
                                  });
        },

        /**
         * For the close button of a notification.
         */
        close_notification: function(item)
        {
            var bubble = item.parentNode;
            if (bubble.className.indexOf("notification_type_announcement") != -1)
                this.update_unread_counts(-1, 0);
            else if (bubble.className.indexOf("notification_type_question") != -1 || bubble.className.indexOf("notification_type_message") != -1)
                this.update_unread_counts(0, -1);
            bubble.parentNode.removeChild(item.parentNode);
        },

        /**
         * Update the remaining time showed in the "remaining" div.
         */
        get_time: function()
        {
            if (this.contest_stop != null)
                var sec_to_end = this.contest_stop - this.timestamp ;
            else
                var sec_to_end = Infinity;

            if (this.contest_start != null)
                var sec_to_start = this.contest_start - this.timestamp;
            else
                var sec_to_start = -Infinity;

            var now = new Date();

            var nowsec_to_end = sec_to_end - (now - firstDate) / 1000;
            var nowsec_to_start = sec_to_start - (now - firstDate) / 1000;
            if ((nowsec_to_end <= 0 && this.phase == 0 ) ||
                (nowsec_to_start <= 0 && this.phase == -1 ))
                window.location.href = url_root + "/";

            countdown = nowsec_to_end;

            if (this.phase == -1)
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

            if (this.remaining_div == null)
                this.remaining_div = document.getElementById("remaining");
            if (this.remaining_div != null)
                this.remaining_div.innerHTML = hoursR + ":" + m + ":" + s;
        },

        /**
         * Check the status returned by an RPC call and display the
         * error if necessary, otherwise redirect to another page.
         *
         * url (string): the destination page if response is ok.
         * response (dict): the response returned by the RPC.
         */
        redirect_if_ok: function(url, response)
        {
            var msg = this.standard_response(response);
            if (msg != "")
                alert('Unable to invalidate (' + msg + ').');
            else
                location.href = url;
        },

        /**
         * Represent in a nice looking way a couple (job_type,
         * submission_id) coming from the backend.
         *
         * job (array): a couple (job_type, submission_id)
         * returns (string): nice representation of job
         */
        repr_job: function(job)
        {
            var job_type = "???";
            if (job == null)
                return "N/A";
            else if (job == "disabled")
                return "Worker disabled";
            else if (job[0] == 'compile')
                job_type = 'Compiling';
            else if (job[0] == 'evaluate')
                job_type = 'Evaluating';
            return job_type + ' submission <a href="' + url_root + '/submission/' + job[1] + '">' + job[1] + '</a>';
        },

        /**
         * Format time as hours, minutes and seconds ago.
         *
         * time (int): a unix time.
         * returns (string): nice representation of time as "x time
         *                   ago"
         */
        repr_time_ago: function(time)
        {
            if (time == null)
                return "N/A";
            var diff = datetime = parseInt((new Date()).getTime()/1000 - time);
            var res = "";

            var s = diff % 60;
            diff = diff - s;
            res = s + " second(s)";
            if (diff == 0)
                return res;
            diff /= 60;

            var m = diff % 60;
            diff -= m;
            res = m + " minute(s), " + res;
            if (diff == 0)
                return res;
            diff /= 60;

            var h = diff;
            res = h + " hour(s), " + res;
            return res;
        },

        /**
         * Format time as hours, minutes and seconds ago.
         *
         * time (int): a unix time.
         * returns (string): nice representation of time as "x time
         *                   ago"
         */
        repr_time_ago_2: function(time)
        {
            if (time == null)
                return "N/A";
            var diff = datetime = parseInt((new Date()).getTime()/1000 - time);
            var res = "";

            var s = diff % 60;
            diff = diff - s;
            if (s < 10 && diff > 0)
                res = "0" + s;
            else
                res = "" + s;
            if (diff == 0)
                return res;
            diff /= 60;

            var m = diff % 60;
            diff -= m;
            if (m < 10 && diff > 0)
                res = "0" + m + ":" + res;
            else
                res = m + ":" + res;
            if (diff == 0)
                return res;
            diff /= 60;

            var h = diff;
            res = h + ":" + res;
            return res;
        },

        /**
         * Return timestamp formatted as HH:MM:SS.
         *
         * timestamp (int): unix time.
         * return (string): timestamp formatted as above.
         */
        format_time: function(timestamp)
        {
            var date = new Date(timestamp * 1000);
            var hours = date.getHours();
            if (hours < 10)
                hours = "0" + hours;
            var minutes = date.getMinutes();
            if (minutes < 10)
                minutes = "0" + minutes;
            var seconds = date.getSeconds();
            if (seconds < 10)
                seconds = "0" + seconds;
            return hours + ":" + minutes + ":" + seconds;

        },

        /**
         * Return timestamp formatted as dd/mm/yyyy HH:MM:SS.
         *
         * timestamp (int): unix time.
         * return (string): timestamp formatted as above.
         */
        format_datetime: function(timestamp)
        {
            var time = this.format_time(timestamp);
            var date = new Date(timestamp * 1000);
            var days = date.getDate();
            if (days < 10)
                days = "0" + days;
            var months = date.getMonth() + 1; // months are 0-11
            if (months < 10)
                months = "0" + months;
            var years = date.getFullYear();
            return time + ", " + days + "/" + months + "/" + years;

        },

        /**
         * Return timestamp formatted as HH:MM:SS if the date is the
         * same date as today, as a complete date + time if the date
         * is different.
         *
         * timestamp (int): unix time.
         * return (string): timestamp formatted as above.
         */
        format_time_or_date: function(timestamp)
        {
            var today = (new Date()).toDateString();
            var date = new Date(timestamp * 1000);
            if (today == date.toDateString())
                return this.format_time(timestamp);
            else
                return this.format_datetime(timestamp);
        },

        /**
         * If the response is for a standard error (unconnected, ...)
         * then return an appropriate message, otherwise return "".
         *
         * response (object): an rpc response.
         * return (string): appropriate message or "".
         */
        standard_response: function(response)
        {
            if (response['status'] != 'ok')
            {
                var msg = "Unexpected reply `" + response['status'] + "'. This should not happen.";
                if (response['status'] == 'unconnected')
                    msg = 'Service not connected.'
                else if (response['status'] == 'not authorized')
                    msg = "You are not authorized to call this method.";
                else if (response['status'] == 'fail')
                    msg = "Call to service failed.";
                return msg;
            }
            return "";
        },

        switch_contest: function()
        {
            var select = document.getElementById("contest_selection_select")
            var value = select.options[select.selectedIndex].value
            if (value == "null")
                window.location = url_root + "/";
            else
                window.location = url_root + "/contest/" + value;
        },

        show_page: function(item, page)
        {
            var elements_per_page = 5;
            var container = document.getElementById("paged_content_" + item);
            var npages = Math.ceil(container.children.length / elements_per_page);
            var final_page = Math.min(page, npages) - 1;
            for(var i = 0; i < container.children.length; i++)
            {
                if(i>= elements_per_page * final_page
                    && i < elements_per_page * (final_page + 1))
                {
                    container.children[i].style.display="block";
                }
                else
                {
                    container.children[i].style.display="none";
                }
            }

            var selector = document.getElementById("page_selector_"+item);
            selector.innerHTML = "Pages: ";
            for( var i = 1; i <= npages; i++)
            {
                if (i != page)
                {
                    selector.innerHTML +=
                        "<a href=\"#\" onclick=\" " +
                        "utils.show_page('questions', "+ i + "); " +
                        "return false;\">" + i + "</a>&nbsp;";
                }
                else
                {
                    selector.innerHTML += (i + "&nbsp;");
                }
            }
        },

        escape_jquery_selectors: function (myid)
        {
            return '#' + myid.replace(/(:|\.)/g,'\\$1');
        },

        /**
         * Escape the input string so that it is suitable for rendering in
         * a HTML page.
         */
        escape_html: function(data)
        {
            return data
                .replace(/&/g,"&amp;")
                .replace(/</g,"&lt;")
                .replace(/>/g,"&gt;")
                .replace(/"/g,"&quot;");
        }

    };
}());
