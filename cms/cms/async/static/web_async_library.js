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

        __delete_request: function(rid) {
            if(rid != null) {
                timeout_id = this.timeout_ids[rid];
                delete this.timeout_ids[rid];
                clearTimeout(timeout_id);
            }
        },

        /**
         * This is called every x millisecs and ask the server if the
         * answer to a request has arrived.
         *
         * cb (function): the callback provided by the user
         * rid (string): the id of the request
         */
        __wait_for_answer: function(cb, rid)
        {
            var got_answer = this.__got_answer.bind(this, cb, rid)
            this.utils.ajax_request(url_root + "/rpc_answer", "__rid=" + rid, got_answer);
        },

        /**
         * This is called when we have a (maybe partial) answer to a
         * request. If the answer is definitive, we call the callback
         * provided by the user.
         *
         * cb (function): the callback provided by the user
         * rid (string): the id of the request
         * response (string): the (partial) answer from the server, as
         *                    a JSON string
         */
        __got_answer: function(cb, rid, response, error)
        {
            if(error != null)
            {
                this.__delete_request(rid);
                if (cb != undefined)
                    cb({'status': 'fail'}, 'fail');
            }
            else
            {
                try
                {
                    response = JSON.parse(response);
                    if (response['status'] != 'wait')
                    {
                        this.__delete_request(rid);
                    }
                    else
                    {
                        this.timeout_ids[rid] = setTimeout(
                            this.__wait_for_answer.bind(this, cb, rid),
                            1000);
                    }

                    if (cb != undefined)
                    {
                        if (response['status'] == 'ok')
                            cb(response, null);
                        else if (response['status'] != 'wait')
                            cb(response, response['status']);
                    }
                }
                catch(e)
                {
                    console.log(e);
                    this.__delete_request(rid);
                    if (cb != undefined)
                        cb(null, response);
                }
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
        request: function(service, shard, method, arguments, cb, sync)
        {
            var got_answer;
            var rid;
            if(sync == true)
            {
                got_answer = this.__got_sync_answer.bind(this, cb, null)
            }
            else
            {
                rid = this.utils.random_string(16);
                got_answer = this.__got_answer.bind(this, cb, rid);
            }

            var args;
            var base_url;
            if(sync == true)
            {
                base_url = "/sync_rpc_request/";
                args = "";
            }
            else
            {
                base_url = "/rpc_request/";
                args = "__rid=" + rid;
            }

            for (var i in arguments)
            {
                var a = JSON.stringify(arguments[i]).replace("%", "%25");
                a = a.replace("&", "%26");
                args += "&" + i + "=" + a;
            }

            this.utils.ajax_request(url_root + base_url +
                                    service + "/" +
                                    shard + "/" +
                                    method,
                                    args,
                                    got_answer
                                   );
        },

    };
}());
