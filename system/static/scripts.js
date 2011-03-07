
function Utilities(timestamp, contest_start, contest_stop, phase)
{

    this.last_notification = timestamp;
    this.timestamp = timestamp;
    this.contest_start = contest_start;
    this.contest_stop = contest_stop;
    this.phase = phase

    this.getXMLHTTP = function()
    {
        var xmlhttp;
        if (window.XMLHttpRequest) { xmlhttp=new XMLHttpRequest(); }
        else if (window.ActiveXObject) { xmlhttp=new ActiveXObject("Microsoft.XMLHTTP"); }
        return xmlhttp;
    }

    this.setVisibility = function(item_id)
    {
        var item = document.getElementById(item_id);
        var toggler = document.getElementById(item_id+"_toggle")

        item.style.display = "block"
        toggler.innerHTML = "-"

    }

    this.toggleVisibility = function(item_id)
    {
        var item = document.getElementById(item_id);
        var toggler = document.getElementById(item_id+"_toggle")
        if (item.style.display != "none")
        {
            item.style.display = "none"
            toggler.innerHTML = "+"
        }
        else
        {
            item.style.display = "block"
            toggler.innerHTML = "-"
        }
    }

    this.popupQuestion = function()
    {
        document.getElementById("popup_question_background").style.display="block";
        document.getElementById("popup_question_container").style.display="block";
        return false;
    }

    this.closePopupQuestion = function()
    {
        document.getElementById("popup_question_container").style.display="none";
        document.getElementById("popup_question_background").style.display="none";
        return false;
    }
    var caller = this;
    this.notifications = function()
    {
        xmlhttp = this.getXMLHTTP();
        xmlhttp.onreadystatechange = function()
        {
          if(xmlhttp.readyState==4)
            if(xmlhttp.status==200)
            {

                if(xmlhttp.responseXML)
                {
                    var root = xmlhttp.responseXML;
                    var announcements = root.getElementsByTagName("announcement");
                    var messages = root.getElementsByTagName("message");
                    caller.last_notification = parseFloat(root.getElementsByTagName("requestdate")[0].firstChild.nodeValue);
                    notification = "";
                    
                    if( announcements.length != 0)
                    {
                        var announcement_subject = announcements[0].firstChild.nodeValue;
                        notification += "Announcement: " + announcement_subject ;
                    }
                    else if( messages.length != 0)
                    {
                        var message_subject = messages[0].firstChild.nodeValue;
                        notification += "Message: " + message_subject;
                    }
                    if(notification != "")
                    {
                        document.getElementById("notification_content").innerHTML = notification;
                        document.getElementById("notification").style.display="block";
                        document.getElementById("global").style.marginTop="40px";
                    }

                }
                else
                {
                    //alert(xmlhttp.responseText);
                }
            }
            else
            {
                //alert(xmlhttp.status);
            }
        }
      var params = "lastrequest="+caller.last_notification;
      xmlhttp.open("POST", "/notifications", true);
      xmlhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      xmlhttp.send(params);
      return xmlhttp;
    }

    this.hideNotification = function(item)
    {
        item.parentNode.style.display="none";
        document.getElementById("global").style.marginTop="0";
    }

    this.getTime = function()
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
        window.location.href = "/";

      countdown = nowsec_to_end;

      if ( this.phase == -1 )
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
      
      if (document.getElementById("remaining"))
        document.getElementById("remaining").innerHTML = hoursR+":"+m+":"+s;;
    }
}
