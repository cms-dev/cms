#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from abc import ABCMeta, abstractmethod

from jinja2 import Markup

from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT


class ParameterType(metaclass=ABCMeta):
    """Base class for parameter types."""

    TEMPLATE = None

    def __init__(self, name, short_name, description):
        """Initialization.

        name (str): name of the parameter.
        short_name (str): short name without spaces, used for HTML
            element ids.
        description (str): describes the usage and effect of this
            parameter.

        """
        self.name = name
        self.short_name = short_name
        self.description = description

    @abstractmethod
    def validate(self, value):
        """Validate that the passed value is syntactically appropriate.

        value (object): the value to test

        raise (ValueError): if the value is malformed for this parameter.

        """
        pass

    @abstractmethod
    def parse_string(self, value):
        """Parse the specified string and returns the parsed value.

        value (str): the string value to parse.

        return (object): the parsed value, of the type appropriate for the
            parameter type.

        raise (ValueError): if parsing fails.

        """
        pass

    def parse_handler(self, handler, prefix):
        """Parse relevant parameters in the handler.

        Attempts to parse any relevant parameters in the specified handler.

        handler (tornado.web.RequestHandler): a handler containing
            the required parameters as arguments.
        prefix (str): the prefix of the relevant arguments in the handler.

        return (object): the parsed value, of the type appropriate for the
            parameter type.

        raise (ValueError): if parsing fails.
        raise (MissingArgumentError) if the argument is missing from the
            handler.

        """
        return self.parse_string(handler.get_argument(
            prefix + self.short_name))

    def render(self, prefix, previous_value=None):
        """Generate a form snippet for this parameter type.

        prefix (str): prefix to add to the fields names in the form.
        previous_value (object|None): if not None, display this value as
            default.

        return (str): HTML form for the parameter type.

        """
        # Markup avoids escaping when other templates include this.
        return Markup(self.TEMPLATE.render(
            parameter=self, prefix=prefix, previous_value=previous_value))


class ParameterTypeString(ParameterType):
    """Type for a string parameter."""

    TEMPLATE = GLOBAL_ENVIRONMENT.from_string("""
<input type="text"
       name="{{ prefix ~ parameter.short_name }}"
       value="{{ previous_value }}" />
""")

    def validate(self, value):
        if not isinstance(value, str):
            raise ValueError(
                "Invalid value for string parameter %s" % self.name)

    def parse_string(self, value):
        return value


class ParameterTypeInt(ParameterType):
    """Type for an integer parameter."""

    TEMPLATE = GLOBAL_ENVIRONMENT.from_string("""
<input type="text"
       name="{{ prefix ~ parameter.short_name }}"
       value="{{ previous_value }}" />
""")

    def validate(self, value):
        if not isinstance(value, int):
            raise ValueError("Invalid value for int parameter %s" % self.name)

    def parse_string(self, value):
        return int(value)


class ParameterTypeChoice(ParameterType):
    """Type for a parameter giving a choice among a finite number of items."""

    TEMPLATE = GLOBAL_ENVIRONMENT.from_string("""
<select name="{{ prefix ~ parameter.short_name }}">
{% for choice_value, choice_description in parameter.values.items() %}
  <option value="{{ choice_value }}"
          {% if choice_value == previous_value %}selected{% endif %}>
    {{ choice_description }}
  </option>
{% endfor %}
</select>
""")

    def __init__(self, name, short_name, description, values):
        """Initialization.

        values (dict): dictionary mapping each choice to a short description.

        """
        super().__init__(name, short_name, description)
        self.values = values

    def validate(self, value):
        # Convert to string to avoid TypeErrors on unhashable types.
        if str(value) not in self.values:
            raise ValueError("Invalid choice %s for parameter %s" %
                             (value, self.name))

    def parse_string(self, value):
        if value not in self.values:
            raise ValueError("Value %s doesn't match any allowed choice."
                             % value)
        return value


class ParameterTypeCollection(ParameterType):
    """Type of a parameter containing a tuple of sub-parameters."""

    TEMPLATE = GLOBAL_ENVIRONMENT.from_string("""
<table>
{% for subp in parameter.subparameters %}
  {% set subp_prefix = "%s%s_%d_"|format(prefix, parameter.short_name,
                                         loop.index0) %}
  {% set subp_previous_value = (previous_value[loop.index0]
                                if previous_value is not none else none) %}
  <tr>
    <td>{{ subp.name }}</td>
    <td>{{ subp.render(subp_prefix, subp_previous_value) }}</td>
  </tr>
{% endfor %}
</table>
""")

    def __init__(self, name, short_name, description, subparameters):
        """Initialization.

        subparameters ([ParameterType]): list of types of each sub-parameter.

        """
        super().__init__(name, short_name, description)
        self.subparameters = subparameters

    def validate(self, value):
        if not isinstance(value, list):
            raise ValueError("Parameter %s should be a list" % self.name)
        if len(value) != len(self.subparameters):
            raise ValueError("Invalid value for parameter %s" % self.name)
        for subvalue, subparameter in zip(value, self.subparameters):
            subparameter.validate(subvalue)

    def parse_string(self, value):
        raise NotImplementedError(
            "parse_string is not implemented for composite parameter types.")

    def parse_handler(self, handler, prefix):
        parsed_values = []
        for i in range(len(self.subparameters)):
            new_prefix = "%s%s_%d_" % (prefix, self.short_name, i)
            parsed_values.append(
                self.subparameters[i].parse_handler(handler, new_prefix))
        return parsed_values
