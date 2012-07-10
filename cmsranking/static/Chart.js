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

var Chart = new function () {
    var self = this;

    self.draw_chart = function (canvas, y_min, y_max, y_def, h_def, x_int, data, color, marks) {
        // canvas is the context
/*
        canvas (GWTCanvas): the canvas this chart will be drawn on
        y_min (float): the y value corresponding to the bottom of the chart
        y_max (float): the y value corresponding to the top of the chart
            (note: y_min can be grater than y_max - the chart will be upside-down)
        y_def (float): the default y value (the line will start at that value)
        h_def (float): the default height of the colored area
        x_int (list of tuples of float): the list of x intervals to be drawn,
            in the form [begin, end)
        data (list of tuples of float): the data to be drawn, in the form (x, y, h)
        color (tuple of int): the r, g and b components of the color for the line
        marks (list of float): the y values at which horizontal lines will be drawn
*/

        // width and height
        var wid = canvas.width;
        var hei = canvas.height;

        // the padding around the chart
        var pad_l = 22;
        var pad_r = 1;
        var pad_t = 6;
        var pad_b = 6;

        // the intervals of allowed x values
        var x_size = 0;
        for (var i in x_int) {
            x_size += x_int[i][1] - x_int[i][0];
        }

        // convert values to canvas coordinates
        var get_x = function (x) {
            return pad_l + x * (wid - pad_l - pad_r) / x_size;
        };

        var get_y = function (y) {
            return pad_t + (y_max - y) * (hei - pad_t - pad_b) / (y_max - y_min == 0? 1: y_max - y_min);
        };

        // clear the canvas
        canvas.width = wid;

        // get the context
        var context = canvas.getContext("2d");

        // draw the axes
        context.lineWidth = 2;
        context.strokeStyle = "#dddddd";

        context.beginPath();
        context.moveTo(pad_l, pad_t);
        context.lineTo(pad_l, hei - pad_b);
        context.lineTo(wid - pad_r, hei - pad_b);
        context.lineTo(wid - pad_r, pad_t);
        context.stroke();

        // draw horizontal markers
        context.lineWidth = 1;
        context.moveTo(pad_l, pad_t);
        context.lineTo(wid - pad_r, pad_t);
        context.stroke();
        for (var i in marks) {
            context.beginPath();
            context.moveTo(get_x(0), get_y(marks[i]));
            context.lineTo(get_x(x_size), get_y(marks[i]));
            context.stroke();
        }

        // draw labels on the axes
        context.fillStyle = "#000000";
        context.textAlign = "right";
        context.textBaseline = "middle";
        if (y_min != y_max)
            context.fillText(y_min.toString(), 18, hei - pad_b);
        context.fillText(y_max.toString(), 18, pad_t);
        for (var i in marks) {
            context.fillText(marks[i].toString(), 18, get_y(marks[i]));
        }

        var i = 0  // index of current interval
        var x_cum = 0  // cumulated x value (sum of the size of the first i-1 intervals)
        var x_pos = 0  // current x value
        var y_pos = y_def  // current y value
        var h_pos = h_def  // current h value
        var x_b = 0  // the 'begin' value of the current interval
        var x_e = 0  // the 'end' value of the current interval

        var tops = [[x_pos, y_pos]]  // points of the line marking the top of the area
        var bots = [[x_pos, y_pos + h_pos]]  // points of the line marking the bottom

        // helper method to open an interval
        var open_group = function () {
            context.lineWidth = 2;
            context.strokeStyle = "rgb(" + color[0] + "," + color[1] + "," + color[2] + ")";
            context.beginPath();
            x_b = x_int[i][0];
            x_e = x_int[i][1];
            context.moveTo(get_x(x_pos), get_y(y_pos));
        }

        // helper method to close an interval
        var close_group = function () {
            x_cum += x_e - x_b;
            x_pos = x_cum;
            context.lineTo(get_x(x_pos), get_y(y_pos));
            tops.push([x_pos, y_pos]);
            bots.push([x_pos, y_pos + h_pos])
            context.stroke();
        }

        // helper method to draw a separator
        var draw_separator = function () {
            context.lineWidth = 2;
            context.strokeStyle = "#dddddd";
            context.beginPath();
            context.moveTo(get_x(x_pos), get_y(y_min));
            context.lineTo(get_x(x_pos), get_y(y_max));
            context.stroke();
        }

        open_group();

        for (var idx in data) {
            var x = data[idx][0];
            var y = data[idx][1];
            var h = data[idx][2];

            while (i < x_int.length && x_e <= x) {
                close_group();
                i += 1;
                if (i < x_int.length) {
                    draw_separator();
                    open_group();
                } else {
                    x_b = 0;
                    x_e = 0;
                }
            }
            if (x_b <= x && x < x_e) {
                x_pos = x_cum + x - x_b;
                context.lineTo(get_x(x_pos), get_y(y_pos));
                tops.push([x_pos, y_pos]);
                bots.push([x_pos, y_pos + h_pos]);
                y_pos = y;
                h_pos = h;
                context.lineTo(get_x(x_pos), get_y(y_pos));
                tops.push([x_pos, y_pos]);
                bots.push([x_pos, y_pos + h_pos]);
            } else {
                y_pos = y;
                h_pos = h;
                context.moveTo(get_x(x_pos), get_y(y_pos));
                tops.push([x_pos, y_pos]);
                bots.push([x_pos, y_pos + h_pos]);
            }
        }
        if (i < x_int.length) {
            close_group();
            i += 1;
        }
        while (i < x_int.length) {
            draw_separator();
            open_group();
            close_group();
            i += 1;
        }

        context.fillStyle = "rgba(" + color[0] + "," + color[1] + "," + color[2] + ",0.3)";
        context.beginPath();
        context.moveTo(get_x(tops[0][0]), get_y(tops[0][1]));
        for (var i = 0; i < tops.length; i += 1) {
            context.lineTo(get_x(tops[i][0]), get_y(tops[i][1]));
        }
        for (var i = bots.length - 1; i >= 0; i -= 1) {
            context.lineTo(get_x(bots[i][0]), get_y(bots[i][1]));
        }
        context.closePath();
        context.fill();
    };
};
