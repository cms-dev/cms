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
         * This is called when we have a (maybe partial) answer to a
         * request. If the answer is definitive, we call the callback
         * provided by the user.
         *
         * response (dict): the (partial) answer from the server
         * cb (function): the callback provided by the user
         * rid (string): the id of the request
         */
        __got_answer: function(response, cb)
        {
            // DEBUG
            var span = document.getElementById("__raw");
            if (span)
                span.innerHTML += '<br/>&nbsp;&nbsp;'+ response;
            // END DEBUG
            try
            {
                response = JSON.parse(response);
                if (response['status'] == 'ok')
                    cb(response, null);
                else if (response['status'] != 'wait')
                    cb(response, response['status']);
            }
            catch(e)
            {
                cb(null, response);
            }
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

            var f = this.utils.bind_func(this, this.__got_answer)
            var args = "";
            for (var i in arguments)
            {
                var a = JSON.stringify(arguments[i]).replace("%", "%25");
                a = a.replace("&", "%26");
                args += "&" + i + "=" + a;
            }
            this.utils.ajax_request("sync_rpc_request/" +
                                    service + "/" +
                                    shard + "/" +
                                    method,
                                    args,
                                    function(response)
                                    {
                                        f(response, cb);
                                    }
                                   );
        },

    };
}());
