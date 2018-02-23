#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

""" A collection of parameter type descriptions supported by AWS.

These parameter types can be used to specify the accepted parameters
of a task type or a score type. These types can cover 'basic' JSON
values, as task_type_parameters and score_type_parameters are
represented by JSON objects.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *
from six import string_types, with_metaclass

from abc import ABCMeta, abstractmethod

from tornado.template import Template


class ParameterType(with_metaclass(ABCMeta, object)):
    """Base class for parameter types.

    """

    def __init__(self, name, short_name, description):
        """Initialization.

        name (string): name of the parameter.
        short_name (string): short name without spaces, used for HTML
                             element ids.
        description (string): describes the usage and effect of this
                              parameter.

        """
        self.name = name
        self.short_name = short_name
        self.description = description

    @abstractmethod
    def validate(self, value):
        """Validate that the passed value is syntactically appropriate

        value (object): the value to test

        raise (ValueError): if the value is malformed for this parameter.

        """
        pass

    @abstractmethod
    def parse_string(self, value):
        """Parse the specified string and returns the parsed value.

        Attempts to parse a value string (as received by a server from
        a form) and returns a value of the according type. If parsing
        fails, this method must raise a ValueError exception with
        an appropriate message.
        """
        pass

    def parse_handler(self, handler, prefix):
        """Parse relevant parameters in the handler.

        Attempts to parse any relevant parameters in the specified handler.

        handler (tornado.web.RequestHandler): A handler containing
            the required parameters as arguments.
        prefix (string): The prefix of the relevant arguments in the handler.
        """
        return self.parse_string(handler.get_argument(
            prefix + self.short_name))

    @abstractmethod
    def render(self, prefix, previous_value=None):
        pass


class ParameterTypeString(ParameterType):
    """String parameter type."""

    TEMPLATE = "<input type=\"text\" name=\"{{parameter_name}}\" " \
        "value=\"{{parameter_value}}\" />"

    def validate(self, value):
        if not isinstance(value, string_types):
            raise ValueError("Invalid value for string parameter %s" %
                             self.name)

    def parse_string(self, value):
        """Returns the specified string.
        """
        return value

    def render(self, prefix, previous_value=None):
        return Template(self.TEMPLATE).generate(
            parameter_name=prefix + self.short_name,
            parameter_value=previous_value)


class ParameterTypeFloat(ParameterType):
    """Numeric parameter type."""

    TEMPLATE = "<input type=\"text\" name=\"{{parameter_name}}\" " \
        "value=\"{{parameter_value}}\" />"

    def validate(self, value):
        if not isinstance(value, float):
            raise ValueError("Invalid value for float parameter %s" %
                             self.name)

    def parse_string(self, value):
        """Attempts to parse the specified string as a float and
        returns the parsed value.
        """
        return float(value)

    def render(self, prefix, previous_value=None):
        return Template(self.TEMPLATE).generate(
            parameter_name=prefix + self.short_name,
            parameter_value=previous_value)


class ParameterTypeInt(ParameterType):
    """Numeric parameter type."""

    TEMPLATE = "<input type=\"text\" name=\"{{parameter_name}}\" " \
        "value=\"{{parameter_value}}\" />"

    def validate(self, value):
        if not isinstance(value, int):
            raise ValueError("Invalid value for int parameter %s" % self.name)

    def parse_string(self, value):
        """Attempts to parse the specified string as a float and
        returns the parsed value.
        """
        return int(value)

    def render(self, prefix, previous_value=None):
        return Template(self.TEMPLATE).generate(
            parameter_name=prefix + self.short_name,
            parameter_value=previous_value)


class ParameterTypeBoolean(ParameterType):
    """Boolean parameter type.
    """

    TEMPLATE = "<input type=\"checkbox\" name=\"{{parameter_name}}\" " \
        "{% if checked %}checked{% end %} />"

    def validate(self, value):
        if not isinstance(value, bool):
            raise ValueError("Invalid value for boolean parameter %s" %
                             self.name)

    def parse_string(self, value):
        """Returns True if the value is not None.
        """
        return value is not None

    def render(self, prefix, previous_value=False):
        return Template(self.TEMPLATE).generate(
            parameter_name=prefix + self.short_name,
            enabled=(previous_value is True))


class ParameterTypeChoice(ParameterType):
    """Parameter type representing a limited number of choices."""

    TEMPLATE = "{% from six import iteritems %}" \
        "<select name=\"{{parameter_name}}\">" \
        "{% for choice_value, choice_description "\
        " in iteritems(choices) %}" \
        "<option value=\"{{choice_value}}\" " \
        "{% if choice_value == parameter_value %}" \
        "selected" \
        "{% end %}>" \
        "{{choice_description}}" \
        "</option>" \
        "{% end %}" \
        "</select>"

    def __init__(self, name, short_name, description, values):
        """
        values (dict): Short descriptions of the accepted choices,
            indexed by their respective accepted choices.
        """
        ParameterType.__init__(self, name, short_name, description)
        self.values = values

    def validate(self, value):
        if value not in self.values:
            raise ValueError("Invalid choice %s for parameter %s" %
                             (value, self.name))

    def parse_string(self, value):
        """Tests whether the string is an accepted value.

        Returns the same string if it's an accepted value, otherwise it raises
        ValueError.
        """
        if value not in self.values:
            raise ValueError("Value %s doesn't match any allowed choice."
                             % value)
        return value

    def render(self, prefix, previous_value=None):
        return Template(self.TEMPLATE).generate(
            parameter_name=prefix + self.short_name,
            choices=self.values,
            parameter_value=previous_value)


class ParameterTypeArray(ParameterType):
    """Parameter type representing an arbitrary-size array of sub-parameters.

    Only a single sub-parameter type is supported.
    """

    TEMPLATE = "<a href=\"#\">Add element</a>" \
        "<table>" \
        "{% for element in elements%}" \
        "<tr><td>{{element.name}}</td>" \
        "<td>{% raw element.content %}</td></tr>" \
        "{% end %}" \
        "</table>"

    def __init__(self, name, short_name, description, subparameter):
        ParameterType.__init__(self, name, short_name, description)
        self.subparameter = subparameter

    def validate(self, value):
        if not isinstance(value, list):
            raise ValueError("Parameter %s should be a list" % self.name)
        for val in value:
            self.subparameter.validate(val)

    def parse_string(self, value):
        pass

    def parse_handler(self, handler, prefix):
        parsed_values = []
        i = 0
        old_prefix = "%s%s_%d" % (prefix, self.short_name, i)
        while handler.get_argument(old_prefix) is not None:
            new_prefix = "%s%s_%d_" % (prefix, self.short_name, i)
            parsed_values.append(
                self.subparameter.parse_handler(handler, new_prefix))
        return parsed_values

    def render(self, prefix, previous_value=None):
        if previous_value is None:
            previous_value = []
        elements = []
        for i in range(len(previous_value)):
            subparam_value = previous_value[i]
            new_prefix = "%s%s_%d_" % (prefix, self.short_name, i)
            elements.append({
                "name": self.subparameter.name,
                "content": self.subparameter.render(new_prefix,
                                                    subparam_value)})
        return Template(self.TEMPLATE).generate(elements=elements)


class ParameterTypeCollection(ParameterType):
    """A fixed-size list of subparameters."""

    TEMPLATE = "<table>" \
        "{% for element in elements %}" \
        "<tr><td>{{element['name']}}</td>" \
        "<td>{% raw element['content'] %}</td></tr>" \
        "{% end %}" \
        "</table>"

    def __init__(self, name, shortname, description, subparameters):
        ParameterType.__init__(self, name, shortname, description)
        self.subparameters = subparameters

    def validate(self, value):
        if not isinstance(value, list):
            raise ValueError("Parameter %s should be a list" % self.name)
        if len(value) != len(self.subparameters):
            raise ValueError("Invalid value for parameter %s" % self.name)
        for subvalue, subparameter in zip(value, self.subparameters):
            subparameter.validate(subvalue)

    def parse_string(self, value):
        pass

    def parse_handler(self, handler, prefix):
        parsed_values = []
        for i in range(len(self.subparameters)):
            new_prefix = "%s%s_%d_" % (prefix, self.short_name, i)
            parsed_values.append(
                self.subparameters[i].parse_handler(handler, new_prefix))
        return parsed_values

    def render(self, prefix, previous_value=None):
        elements = []
        for i in range(len(self.subparameters)):
            try:
                subparam_value = previous_value[i]
            except:
                subparam_value = ''
            new_prefix = "%s%s_%d_" % (prefix, self.short_name, i)
            elements.append({
                "name": self.subparameters[i].name,
                "content": self.subparameters[i].render(new_prefix,
                                                        subparam_value)})
        return Template(self.TEMPLATE).generate(elements=elements)
