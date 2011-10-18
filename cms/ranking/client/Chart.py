# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from pyjamas.Canvas import Color

from pyjamas import Window


def draw_chart(canvas, y_min, y_max, y_def, h_def, x_int, data, color, marks):
    """Draw a chart on the given canvas.

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

    """
    # width and height
    wid = canvas.getCoordWidth()
    hei = canvas.getCoordHeight()

    # the padding around the chart
    pad_l = 1
    pad_r = 1
    pad_t = 1
    pad_b = 1

    # the intervals of allowed x values
    x_size = sum([e - b for b, e in x_int])

    # convert values to canvas coordinates
    def get_x(x):
        return pad_l + x * (wid - pad_l - pad_r) / x_size

    def get_y(y):
        return pad_t + (y_max - y) * (hei - pad_t - pad_b) / (y_max - y_min)

    # clear the canvas
    canvas.clear()

    # draw the axes
    canvas.setLineWidth(2)
    canvas.setStrokeStyle(Color.Color("#dddddd"))

    canvas.beginPath()
    canvas.moveTo(pad_l, pad_t)
    canvas.lineTo(pad_l, hei - pad_b)
    canvas.lineTo(wid - pad_r, hei - pad_b)
    canvas.lineTo(wid - pad_r, pad_t)
    canvas.stroke()

    # draw horizontal markers
    canvas.setLineWidth(1)
    for m in marks:
        canvas.beginPath()
        canvas.moveTo(get_x(0), get_y(m))
        canvas.lineTo(get_x(x_size), get_y(m))
        canvas.stroke()

    i = 0  # index of current interval
    x_cum = 0  # cumulated x value (sum of the size of the first i-1 intervals)
    x_pos = 0  # current x value
    y_pos = y_def  # current y value
    h_pos = h_def  # current h value
    x_b = 0  # the 'begin' value of the current interval
    x_e = 0  # the 'end' value of the current interval

    tops = [(x_pos, y_pos)]  # points of the line marking the top of the area
    bots = [(x_pos, y_pos + h_pos)]  # points of the line marking the bottom

    # helper method to open an interval
    def open_group():
        canvas.setLineWidth(2)
        canvas.setStrokeStyle(Color.Color(color[0], color[1], color[2]))
        canvas.beginPath()
        x_b += x_int[i][0] - x_b  # x_b = x_int[i][0]
        x_e += x_int[i][1] - x_e  # x_e = x_int[i][1]
        canvas.moveTo(get_x(x_pos), get_y(y_pos))

    # helper method to close an interval
    def close_group():
        x_cum += x_e - x_b
        x_pos += x_cum - x_pos  # x_pos = x_cum
        canvas.lineTo(get_x(x_pos), get_y(y_pos))
        tops.append((x_pos, y_pos))
        bots.append((x_pos, y_pos + h_pos))
        canvas.stroke()

    # helper method to draw a separator
    def draw_separator():
        canvas.setLineWidth(2)
        canvas.setStrokeStyle(Color.Color("#dddddd"))
        canvas.beginPath()
        canvas.moveTo(get_x(x_pos), get_y(y_min))
        canvas.lineTo(get_x(x_pos), get_y(y_max))
        canvas.stroke()

    open_group()
    for x, y, h in data:
        while i < len(x_int) and x_e <= x:
            close_group()
            i += 1
            if i < len(x_int):
                draw_separator()
                open_group()
            else:
                x_b = x_e = 0
        if x_b <= x < x_e:
            x_pos = x_cum + x - x_b
            canvas.lineTo(get_x(x_pos), get_y(y_pos))
            tops.append((x_pos, y_pos))
            bots.append((x_pos, y_pos + h_pos))
            y_pos = y
            h_pos = h
            canvas.lineTo(get_x(x_pos), get_y(y_pos))
            tops.append((x_pos, y_pos))
            bots.append((x_pos, y_pos + h_pos))
        else:
            y_pos = y
            h_pos = h
            canvas.moveTo(get_x(x_pos), get_y(y_pos))
            tops.append((x_pos, y_pos))
            bots.append((x_pos, y_pos + h_pos))
    if i < len(x_int):
        close_group()
        i += 1
    while i < len(x_int):
        draw_separator()
        open_group()
        close_group()
        i += 1

    # bug in Pyjamas: I have to create the color string manually
    canvas.setFillStyle(Color.Color("rgba(%d,%d,%d,%.2f)" % (color[0], color[1], color[2], 0.3)))
    canvas.beginPath()
    canvas.moveTo(get_x(tops[0][0]), get_y(tops[0][1]))
    for p in tops:
        canvas.lineTo(get_x(p[0]), get_y(p[1]))
    for p in reversed(bots):
        canvas.lineTo(get_x(p[0]), get_y(p[1]))
    canvas.closePath()
    canvas.fill()
