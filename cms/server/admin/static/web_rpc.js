/* Contest Management System
 * Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 * Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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


function get_cookie(name) {
    var r = document.cookie.match("(^|;)\\s*" + name + "=([^;]*)(;|$)");
    return r ? r[2] : void(0);
}

/**
 * Call a RPC method of a remote service, proxied by AWS.
 *
 * service: the name of the remote Service.
 * shard: the shard of the remote Service.
 * method: the name of the method.
 * args: the keyword arguments (as an Object).
 * callback: a function to call with the result of the request.
 * return: the XHR object.
 */
function cmsrpc_request(service, shard, method, args, callback) {
    var url = utils.url("rpc", service, shard, method);
    var jqxhr = $.ajax({
        type: "POST",
        url: url,
        data: JSON.stringify(args),
        contentType: "application/json",
        dataType: "json",
        headers: {"X-XSRFToken": get_cookie("_xsrf")}
    });

    jqxhr.done(function(data) {
        data["status"] = "ok";
        if (typeof callback !== "undefined") {
            callback(data);
        }
    });

    jqxhr.fail(function(jqxhr) {
        var data = {};
        if (jqxhr.status == 403) {
            data["status"] = "not authorized";
        } else if (jqxhr.status == 503) {
            data["status"] = "unconnected";
        } else {
            data["status"] = "fail";
        }
        if (typeof callback !== "undefined") {
            callback(data);
        }
    });

    return jqxhr;
}
