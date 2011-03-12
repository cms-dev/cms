(function() {

    CMSUtils = function()
    {
    }

    CMSUtils.prototype =
    {

        bind_func: function(object, method)
        {
            return function()
            {
                return method.apply(object, arguments);
            };
        },

        ajax_request: function(url, par, cb)
        {
            var xmlhttp;
            if (window.XMLHttpRequest)
                xmlhttp=new XMLHttpRequest();
            else if (window.ActiveXObject)
                xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
            else
                alert("Your browser does not support XMLHTTP!");
            xmlhttp.onreadystatechange = function()
            {
                if (xmlhttp.readyState == 4)
                {
                    cb(xmlhttp.responseText);
                }
            }
            xmlhttp.open("GET", url + "?" + par, true);
            xmlhttp.send();
        },

        random_string: function(length)
        {
            var string = "";
            var letters =
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
            for(var i = 0; i < length; i++)
            {
                var idx = Math.floor(Math.random() * letters.length);
                string += letters.charAt(idx);
            }
            return string;
        },

    };
}());