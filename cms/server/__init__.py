#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from .util import \
    CommonRequestHandler, DIMS, UNITS, \
    actual_phase_required, compute_actual_phase, \
    encode_for_url, file_handler_gen, filter_ascii, \
    format_amount_of_time, format_dataset_attrs, format_date, \
    format_datetime, format_datetime_smart, format_size, format_time, \
    format_token_rules, get_score_class, create_url_builder, multi_contest


__all__ = [
    # util
    "CommonRequestHandler", "DIMS", "UNITS",
    "actual_phase_required", "compute_actual_phase",
    "encode_for_url", "file_handler_gen", "filter_ascii",
    "format_amount_of_time", "format_dataset_attrs", "format_date",
    "format_datetime", "format_datetime_smart", "format_size", "format_time",
    "format_token_rules", "get_score_class", "create_url_builder",
    "multi_contest",
]
