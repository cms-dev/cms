(function() {

    CMSAjaxRPC = function()
    {
        this.timeout_ids = new Object();
        this.utils = new CMSUtils();
    }

    CMSAjaxRPC.prototype =
    {

        wait_for_answer: function(cb, rid)
        {
            var f = this.utils.bind_func(this, this.got_answer)
            this.utils.ajax_request("rpc_answer",
                                    "__rid=" + rid,
                                    function(response)
                                    {
                                        f(response, cb, rid);
                                    }
                                   );
        },

        got_answer: function(response, cb, rid)
        {
            // DEBUG
            var span = document.getElementById("__raw");
            if (span)
                span.innerHTML += '<br/>&nbsp;&nbsp;' + rid +
                    ' - ' + response;
            // END DEBUG
            eval('response='+response);
            if (response['status'] != 'wait')
            {
                timeout_id = this.timeout_ids[rid];
                delete this.timeout_ids[rid];
                clearTimeout(timeout_id);
            }
            if (response['status'] == 'ok')
                cb(response);
        },

        request: function(service, shard, method, arguments, cb)
        {
            rid = this.utils.random_string(16);
            this.timeout_ids[rid] = setInterval(
                this.wait_for_answer.bind(this, cb, rid),
                2000);

            var f = this.utils.bind_func(this, this.got_answer)
            this.utils.ajax_request("rpc_request/" +
                                    service + "/" +
                                    shard + "/" +
                                    method + "/" +
                                    arguments,
                                    "__rid=" + rid,
                                    function(response)
                                    {
                                        this.got_answer(response, cb, rid);
                                    }
                                   );
        },

    };
}());