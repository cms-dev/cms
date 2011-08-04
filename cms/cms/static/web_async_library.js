/**
 * This module defines a way to ask the server to execute a remote RPC
 * call, and to get the result back using polling.
 */

(function() {

    CMSAjaxRPC = function()
    {
        this.timeout_ids = new Object();
        this.utils = new CMSUtils();
    }

    CMSAjaxRPC.prototype =
    {

        /**
         * This is called every x millisecs and ask the server if the
         * answer to a request has arrived.
         *
         * cb (function): the callback provided by the user
         * rid (string): the id of the request
         */
        __wait_for_answer: function(cb, rid)
        {
            var f = this.utils.bind_func(this, this.__got_answer)
            this.utils.ajax_request("rpc_answer",
                                    "__rid=" + rid,
                                    function(response)
                                    {
                                        f(response, cb, rid);
                                    }
                                   );
        },

        /**
         * This is called when we have a (maybe partial) answer to a
         * request. If the answer is definitive, we call the callback
         * provided by the user.
         *
         * response (dict): the (partial) answer from the server
         * cb (function): the callback provided by the user
         * rid (string): the id of the request
         */
        __got_answer: function(response, cb, rid)
        {
            // DEBUG
            var span = document.getElementById("__raw");
            if (span)
                span.innerHTML += '<br/>&nbsp;&nbsp;' + rid +
                    ' - ' + response;
            // END DEBUG
            response = JSON.parse(response);
            if (response['status'] != 'wait')
            {
                timeout_id = this.timeout_ids[rid];
                delete this.timeout_ids[rid];
                clearTimeout(timeout_id);
            }
            if (response['status'] == 'ok')
                cb(response);
        },

        /**
         * Ask the server to execute a remote RPC method.
         *
         * service (string): name of the remote service
         * shard (int): shard number of the remote service
         * method (string): name of the requested method
         * arguments (dict): the dict of arguments to pass to method
         * cb (function): a function that is going to be called with
         *                the result of the request
         */
        request: function(service, shard, method, arguments, cb)
        {
            rid = this.utils.random_string(16);
            this.timeout_ids[rid] = setInterval(
                this.__wait_for_answer.bind(this, cb, rid),
                2000);

            var f = this.utils.bind_func(this, this.__got_answer)
            var args = "";
            for (var i in arguments)
            {
                var a = JSON.stringify(arguments[i]).replace("%", "%25");
                a = a.replace("&", "%26");
                args += "&" + i + "=" + a;
            }
            this.utils.ajax_request("rpc_request/" +
                                    service + "/" +
                                    shard + "/" +
                                    method,
                                    "__rid=" + rid + args,
                                    function(response)
                                    {
                                        f(response, cb, rid);
                                    }
                                   );
        },

    };
}());
