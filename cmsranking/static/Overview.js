/* Programming contest management system
 * Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

var Overview = new function () {
    var self = this;

    self.PAD_T = 20;
    self.PAD_B = 10;
    self.PAD_L = 10;
    self.PAD_R = 10;

    self.init = function () {
        var $elem = $("#Overview");

        self.width = $elem.width();
        self.height = $elem.height();

        self.paper = Raphael($elem[0], self.width, self.height);

        self.create_score_chart();

        self.update_score_axis();
        self.update_rank_axis();


        $(window).resize(function () {
            self.width = $elem.width();
            self.height = $elem.height();

            self.paper.setSize(self.width, self.height);

            self.update_score_chart(0);

            self.update_score_axis();
            self.update_rank_axis();

            self.update_markers(0);
        });


        DataStore.user_update.add(function (key, old_data, data) {
            if (old_data["markers"]) {
                data["markers"] = old_data["markers"];
                delete old_data["markers"];
            }
            if (old_data["marker_c_anim"]) {
                data["marker_c_anim"] = old_data["marker_c_anim"];
                delete old_data["marker_c_anim"];
            }
            if (old_data["marker_u_anim"]) {
                data["marker_u_anim"] = old_data["marker_u_anim"];
                delete old_data["marker_u_anim"];
            }
            if ($.inArray(old_data, self.user_list) != -1) {
                self.user_list.splice($.inArray(old_data, self.user_list), 1, data);
            }
        });

        DataStore.score_events.add(self.score_handler);
        DataStore.rank_events.add(self.rank_handler);
        DataStore.select_events.add(self.select_handler);


        // HEADERS ("Score" and "Rank")
        self.paper.setStart();
        self.paper.text(4, 10, "Score").attr("text-anchor", "start");
        self.paper.text(self.width - 4, 10, "Rank").attr("text-anchor", "end");
        var set = self.paper.setFinish();
        set.attr({"font-size": "12px", "fill": "#000000", "stroke": "none", "font-family": "sans-serif", "opacity": 0});

        $elem.mouseenter(function () {
            set.animate({"opacity": 1}, 1000);
        });

        $elem.mouseleave(function () {
            set.animate({"opacity": 0}, 1000);
        });


        // Load initial data.
        $.each(DataStore.users, function (u_id, user) {
            if (user["selected"] > 0)
            {
                self.user_list.push(user);
            }
        });
        self.user_list.sort(self.compare_users);
        self.update_markers(0);
    };


    /** SCORE & RANK AXIS */

    self.update_score_axis = function () {
        var d = Raphael.format("M {1},{3} L {1},{7} M {0},{4} L {2},{4} M {0},{5} L {2},{5} M {0},{6} L {2},{6}",
                               self.PAD_L - 4,
                               self.PAD_L,
                               self.PAD_L + 4,
                               self.PAD_T,
                               self.PAD_T + (self.height - self.PAD_T - self.PAD_B) * 0.25,
                               self.PAD_T + (self.height - self.PAD_T - self.PAD_B) * 0.50,
                               self.PAD_T + (self.height - self.PAD_T - self.PAD_B) * 0.75,
                               self.height - self.PAD_B);

        if (self.score_axis) {
            self.score_axis.attr("path", d);
        } else {
            self.score_axis = self.paper.path(d).attr(
                {"fill": "none", "stroke": "#b8b8b8", "stroke-width": 3, "stroke-linecap": "round"});
        }
    };


    self.update_rank_axis = function () {
        var d = Raphael.format("M {1},{3} L {1},{4} M {0},{3} L {2},{3} M {0},{4} L {2},{4}",
                               self.width - self.PAD_R - 4,
                               self.width - self.PAD_R,
                               self.width - self.PAD_R + 4,
                               self.PAD_T,
                               self.height - self.PAD_B);

        var ranks = [
            { color: "#ffd700", ratio: 1/12 },
            { color: "#c0c0c0", ratio: 2/12 },
            { color: "#cd7f32", ratio: 3/12 },
            { color: "#000000", ratio: 6/12 }
        ];
        var stops = [];
        var base = 0;
        for (var i = 0; i < ranks.length; i++) {
            stops.push(ranks[i].color + ":" + (base + (ranks[i].ratio / 3)) * 100);
            stops.push(ranks[i].color + ":" + (base + (ranks[i].ratio / 3 * 2)) * 100);
            base += ranks[i].ratio;
        }
        stops = stops.join("-");

        if (self.rank_axis) {
            self.rank_axis.attr("path", d);
        } else {
            // Since raphael does not support gradients for stroke, we set the fill attr to it,
            // then move the value to stroke.
            self.rank_axis = self.paper.path(d).attr({
                "fill": "270-" + stops,
                "stroke-width": 3,
                "stroke-linecap": "round"
            });
            self.rank_axis.node.setAttribute("stroke", self.rank_axis.node.getAttribute("fill"));
            self.rank_axis.node.setAttribute("fill", "none");
        }
    };


    /** SCORE CHART */

    self.SCORE_STEPS = 15;

    // scores[0] contains the number of users with a score of zero
    // scores[i] (with i in [1..SCORE_STEPS]) contains the number of users with
    //     a score in the half-open interval [i * (max_score / SCORE_STEPS),
    //     (i+1) * (max_score / SCORE_STEPS)). for i == 0 the interval is open
    // scores[SCORE_STEPS+1] contins the number of user with the max_score
    // see also self.get_score_class()
    self.scores = new Array();

    for (var i = 0; i <= self.SCORE_STEPS + 1; i += 1) {
        self.scores.push(0);
    }


    self.make_path_for_score_chart = function () {
        // For each element of self.scores, we convert the number it contains
        // to a distance from the score axis and then create a smooth path that
        // passes on all those points.
        // To convert the number of users to a distance we use the following
        // formula (a parabola, open down):  d(x) = a * x^2 + b * x + c
        // with a, b and c parameters chosen such that:
        // - d(0) = 0;        - d'(0) = 3/2;
        // - d(max_users) = 3/4 * width (excluding padding);

        var max_users = DataStore.user_count;
        var a = (3/4 * (self.width - self.PAD_R - self.PAD_L) - 3/2 * max_users) / (max_users * max_users);
        var b = 3/2;
        var c = 0;

        var s_path = "";
        for (var i = 0; i <= self.SCORE_STEPS + 1; i += 1) {
            var x = self.PAD_L + a * self.scores[i] * self.scores[i] + b * self.scores[i] + c;
            var y = self.height - self.PAD_B - i * (self.height - self.PAD_T - self.PAD_B) / (self.SCORE_STEPS + 1);
            if (i == 0) {
                s_path += Raphael.format("M {0},{1} R", x, y);
            } else {
                s_path += Raphael.format(" {0},{1}", x, y);
            }
        }

        return s_path;
    };


    self.recompute = function () {
        // Recompute self.scores
        for (var i = 0; i <= self.SCORE_STEPS + 1; i += 1) {
            self.scores[i] = 0;
        }

        var users = DataStore.users;
        var max_score = DataStore.global_max_score;

        for (var u_id in users) {
            self.scores[self.get_score_class(users[u_id]["global"], max_score)] += 1;
        }
    };


    self.create_score_chart = function () {
        self.recompute();
        var s_path = self.make_path_for_score_chart();
        self.score_line = self.paper.path(s_path).attr({"fill": "none", "stroke": "#cccccc", "stroke-width": 2, "stroke-linecap": "round"});
        s_path += Raphael.format(" L {0},{1} {0},{2} Z", self.PAD_L, self.PAD_T, self.height - self.PAD_B);
        self.score_back = self.paper.path(s_path).attr({"fill": "0-#E4E4E4-#DADADB", "stroke": "none"});
        self.score_back.toBack();
    };


    self.update_score_chart = function (t) {
        var s_path = self.make_path_for_score_chart();
        self.score_line.animate({'path': s_path}, t);
        s_path += Raphael.format(" L {0},{1} {0},{2} Z", self.PAD_L, self.PAD_T, self.height - self.PAD_B);
        self.score_back.animate({'path': s_path}, t);
    };


    self.get_score_class = function (score, max_score) {
        if (score <= 0) {
            return 0;
        } else if (score >= max_score) {
            return self.SCORE_STEPS + 1;
        } else {
            return parseInt(score / max_score * self.SCORE_STEPS) + 1;
        }
    };


    /** MARKERS */


    // We keep a sorted list of user that represent the current order of the
    // selected users in the overview. In particular we sort using these keys:
    // - the global score
    // - the last name
    // - the first name
    // - the key
    self.user_list = new Array();


    // Compare two users. Returns -1 if "a < b" or +1 if "a >= b"
    // (where a < b means that a shoud go above b in the overview)
    self.compare_users = function (a, b) {
        if ((a["global"] > b["global"]) || ((a["global"] == b["global"]) &&
           ((a["l_name"] < b["l_name"]) || ((a["l_name"] == b["l_name"]) &&
           ((a["f_name"] < b["f_name"]) || ((a["f_name"] == b["f_name"]) &&
           (a["key"] <= b["key"]))))))) {
            return -1;
        } else {
            return +1;
        }
    };

    self.MARKER_PADDING = 2;
    self.MARKER_RADIUS = 2.5;
    self.MARKER_LABEL_WIDTH = 50;
    self.MARKER_LABEL_HEIGHT = 20;
    self.MARKER_ARROW_WIDTH = 20;
    self.MARKER_STROKE_WIDTH = 2;

    self.make_path_for_marker = function (s_h, u_h, r_h) {
        // The path is composed of a label (whose vertical center is at u_h,
        // self.MARKER_LABEL_WIDTH wide and self.MARKER_LABEL_HEIGHT high),
        // made of two horizontal (H) lines (for top and bottom), delimited on
        // the right by two straight lines (L) forming an arrow (which is
        // self.MARKER_ARROW_WIDTH wide), with its center at an height of r_h.
        // On the left two cubic bezier curves (C) start tangentially from the
        // label and end, still tangentially, on an elliptic arc (A), with its
        // center at an height of s_h and a radius of self.MARKER_RADIUS.
        // The path starts just above the arc, with the first cubic bezier.

        // TODO Most of these values are constants, no need to recompute
        // everything again every time.

        return Raphael.format("M {0},{5} C {1},{5} {1},{6} {2},{6} H {3} L {4},{7} {3},{8} H {2} C {1},{8} {1},{9} {0},{9} A {10},{10} 0 0,1 {0},{5} Z",
                              self.PAD_L,
                              (self.PAD_L + self.width - self.PAD_R - self.MARKER_ARROW_WIDTH - self.MARKER_LABEL_WIDTH) / 2,
                              self.width - self.PAD_R - self.MARKER_ARROW_WIDTH - self.MARKER_LABEL_WIDTH,
                              self.width - self.PAD_R - self.MARKER_ARROW_WIDTH,
                              self.width - self.PAD_R,
                              s_h - self.MARKER_RADIUS,
                              u_h - (self.MARKER_LABEL_HEIGHT - self.MARKER_STROKE_WIDTH) / 2,
                              r_h,
                              u_h + (self.MARKER_LABEL_HEIGHT - self.MARKER_STROKE_WIDTH) / 2,
                              s_h + self.MARKER_RADIUS,
                              self.MARKER_RADIUS);
    };


    self.create_marker = function (user, s_h, u_h, r_h, t) {
        var d = self.make_path_for_marker(s_h, u_h, r_h);

        // Map the color_index given by DataStore to the actual color
        // (FIXME This almost duplicates some code in Ranking.css...)
        switch (user["selected"]) {
            case 1:  // Blue
                var color_a = "#729fcf";
                var color_b = "#3465a4";
                break;
            case 2:  // Butter
                var color_a = "#fce94f";
                var color_b = "#edd400";
                break;
            case 3:  // Red
                var color_a = "#ef2929";
                var color_b = "#cc0000";
                break;
            case 4:  // Chameleon
                var color_a = "#8ae234";
                var color_b = "#73d216";
                break;
            case 5:  // Orange
                var color_a = "#fcaf3e";
                var color_b = "#f57900";
                break;
            case 6:  // Plum
                var color_a = "#ad7fa8";
                var color_b = "#75507b";
                break;
            case 7:  // Aluminium
                var color_a = "#babdb6";
                var color_b = "#888a85";
                break;
            case 8:  // Chocolate
                var color_a = "#e9b96e";
                var color_b = "#c17d11";
                break;
        }

        self.paper.setStart();
        self.paper.path(d).attr({
            "fill": color_b,
            "stroke": color_a,
            "stroke-width": self.MARKER_STROKE_WIDTH,
            "stroke-linejoin": "round"});
        // Place the text inside the label, with a padding-right equal to its
        // padding-top and padding-bottom.
        var t_x = self.width - self.PAD_R - self.MARKER_ARROW_WIDTH - (self.MARKER_LABEL_HEIGHT - 12) / 2;
        self.paper.text(t_x, u_h, self.transform_key(user)).attr({
            "fill": "#ffffff",
            "stroke": "none",
            "font-family": "sans-serif",
            "font-size": "12px",
            "text-anchor": "end"});
        var set = self.paper.setFinish();
        set.attr({"cursor": "pointer",
                  "opacity": 0});

        set.click(function () {
            Scoreboard.scroll_into_view(user["key"]);
        });

        user["markers"] = set;

        user["marker_c_anim"] = Raphael.animation({"opacity": 1}, t, function () {
            delete user["marker_c_anim"];
        });
        set.animate(user["marker_c_anim"]);
    };

    self.transform_key = function(user) {
      var s = user['f_name'] + ' ' + user['l_name'];
      var sl = s.split(' ');
      var out = '';
      for (var i = 0; i < sl.length; i++) {
          if (sl[i].length > 0) {
              out += sl[i][0];
          }
      }
      if (user["team"] != null && user["team"] != undefined) {
          return user['team'] + '-' + out;
      } else {
          return out;
      }
    };


    self.update_marker = function (user, s_h, u_h, r_h, t) {
        var d = self.make_path_for_marker(s_h, u_h, r_h);

        // If the duration of the animation is 0 or if the element has just
        // been created (i.e. its creation animation hasn't finished yet) then
        // just set the new path and position. Else, animate them.
        if (t && !user["marker_c_anim"]) {
            user["markers"].stop();
            user["marker_u_anim"] = Raphael.animation({"path": d, "y": u_h}, t, function () {
                delete user["marker_u_anim"];
            });
            user["markers"].animate(user["marker_u_anim"]);
        } else {
            user["markers"].attr({"path": d, "y": u_h});
        }
    };


    self.delete_marker = function (user, t) {
        var markers = user["markers"];
        delete user["markers"];

        // If an update animation is running, we stop and delete it
        if (user["marker_u_anim"]) {
            markers.stop();
            delete user["marker_u_anim"];
        }

        var anim = Raphael.animation({"opacity": 0}, t, function () {
            markers.remove();
        });
        markers.animate(anim);

        self.user_list.splice($.inArray(user, self.user_list), 1);
        self.update_markers(t);
    };


    self.get_score_height = function (score, max_score) {
        if (max_score <= 0) {
            return self.height - self.PAD_B;
        }
        return self.height - self.PAD_B - score / max_score * (self.height - self.PAD_T - self.PAD_B);
    };


    self.get_rank_height = function (rank, max_rank) {
        if (max_rank <= 1) {
            return self.PAD_T;
        }
        return self.PAD_T + (rank - 1) / (max_rank - 1) * (self.height - self.PAD_T - self.PAD_B);
    };


    self.merge_clusters = function (a, b) {
        // See the next function to understand the purpose of this function
        var middle = (a.n * (a.b + a.e) / 2 + b.n * (b.b + b.e) / 2) / (a.n + b.n);
        a.list = a.list.concat(b.list);
        a.n += b.n;
        a.b = middle - (a.n * self.MARKER_LABEL_HEIGHT + (a.n - 1) * self.MARKER_PADDING) / 2;
        a.e = a.b + a.n * self.MARKER_LABEL_HEIGHT + (a.n - 1) * self.MARKER_PADDING;
    };


    self.update_markers = function (t) {
        // Use them as shortcut
        var h = self.MARKER_LABEL_HEIGHT;
        var p = self.MARKER_PADDING;

        // We iterate over all selected users (in top-to-bottom order). For
        // each of them we create a cluster which, initally, contains just that
        // user. Then, if the cluster overlaps with another, we merge them and
        // increase its size so that its element don't overlap anymore. We
        // repeat this process unit no two clusters overlap, and then proceed
        // to the next user. We also take care that no cluster is outside the
        // visible area, either above or below.

        // The list of clusters and its size (n == cs.length)
        var cs = new Array();
        var n = 0;

        for (var i in self.user_list) {
            var user = self.user_list[i];
            var r_height = self.get_rank_height(user["rank"], DataStore.user_count);

            // 'b' (for begin) is the y coordinate of the top of the cluster
            // 'e' (for end) is the y coordinate of the bottom of the cluster
            // 'n' is the number of items it contains (c.n == c.list.length)
            cs.push({'b': r_height - h/2, 'e': r_height + h/2, 'list': [user], 'n': 1});
            n += 1;

            // Check if it overlaps with the one above it
            while (n > 1 && cs[n-2].e + p > cs[n-1].b) {
                self.merge_clusters(cs[n-2], cs[n-1]);
                cs.pop();
                n -= 1;
            }

            // Check if it overflows at the top of the visible area
            if (cs[n-1].b < self.PAD_T - h/2) {
                cs[n-1].e += (self.PAD_T - h/2) - cs[n-1].b;
                cs[n-1].b = self.PAD_T - h/2;
            }
        }

        // Check if it overflows at the bottom of the visible area
        while (n > 0 && cs[n-1].e > self.height - self.PAD_B + h/2) {
            cs[n-1].b += (self.height - self.PAD_B + h/2) - cs[n-1].e;
            cs[n-1].e = self.height - self.PAD_B + h/2;

            // Check if it overlaps with the one above it
            if (n > 1 && cs[n-2].e + p > cs[n-1].b) {
                self.merge_clusters(cs[n-2], cs[n-1]);
                cs.pop();
                n -= 1;
            }
        }

        // If it overflows again at the top then there's simply not enough
        // space to hold them all. Compress them.
        if (n > 0 && cs[0].b < self.PAD_T - h/2) {
            cs[0].b = self.PAD_T - h/2;
        }

        // Proceed with the actual drawing
        for (var i in cs) {
            var c = cs[i];
            var begin = c.b;
            var step = (c.e - begin - h) / (c.n - 1);  // NaN if c.n == 1

            for (var j in c.list) {
                var user = c.list[j];

                var s_height = self.get_score_height(user["global"], DataStore.global_max_score);
                var r_height = self.get_rank_height(user["rank"], DataStore.user_count);

                if (user["markers"]) {
                    // Update the existing marker
                    self.update_marker(user, s_height, begin + h/2, r_height, t);
                } else {
                    // Create a new marker
                    self.create_marker(user, s_height, begin + h/2, r_height, t);
                }

                begin += step;  // begin is NaN if step is NaN: no problem
                                // because if c.n == 1 begin won't be used again
            }
        }
    };


    self.score_handler = function (u_id, user, t_id, task, delta) {
        var new_score = user["global"];
        var old_score = new_score - delta;
        var max_score = DataStore.global_max_score;

        self.scores[self.get_score_class(old_score, max_score)] -= 1;
        self.scores[self.get_score_class(new_score, max_score)] += 1;

        self.update_score_chart(1000);

        if (user["selected"] > 0) {
            self.user_list.sort(self.compare_users);
            self.update_markers(1000);
        }
    };


    self.rank_handler = function (u_id, user, delta) {
        if (user["selected"] > 0) {
            self.update_markers(1000);
        }
    };


    self.select_handler = function (u_id, color) {
        var user = DataStore.users[u_id];
        if (color > 0) {
            self.user_list.push(user);
            self.user_list.sort(self.compare_users);
            self.update_markers(1000);
        } else {
            self.delete_marker(DataStore.users[u_id], 1000);
        }
    };

    /* TODO: When users get added/removed the total user count changes and all
       rank "markers" need to be adjusted!
     */
};
