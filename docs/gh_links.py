#!/usr/bin/python
# -*- coding: utf-8 -*-

# Sphinx extension to add roles for some GitHub features
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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


from docutils import nodes, utils

from sphinx.util.nodes import split_explicit_title

def gh_issue(role, rawtext, text, lineno, inliner, options={}, content=[]):
    text = utils.unescape(text)
    has_explicit_title, title, part = split_explicit_title(text)
    if not has_explicit_title:
        title = 'issue #%s' % part
    full_url = 'https://github.com/cms-dev/cms/issues/%s' % part

    pnode = nodes.reference(title, title, internal=False, refuri=full_url, **options)
    return [pnode], []

def make_gh_download(app):
    def gh_download(role, rawtext, text, lineno, inliner, options={}, content=[]):
        title = utils.unescape(text)
        full_url = 'https://github.com/cms-dev/cms/archive/v%s.tar.gz' % app.config.release

        pnode = nodes.reference(title, title, internal=False, refuri=full_url, **options)
        return [pnode], []
    return gh_download

def setup_roles(app):
    app.add_role("gh_issue", gh_issue)
    app.add_role("gh_download", make_gh_download(app))

def setup(app):
    app.connect('builder-inited', setup_roles)
