#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import atexit
import errno
import io
import json
import mechanize
import os
import re
import signal
import socket
import subprocess
import time
from urlparse import urlsplit

import cmstestsuite.web
from cmstestsuite.web.CWSRequests import LoginRequest, SubmitRequest
from cmstestsuite.web.AWSRequests import AWSSubmissionViewRequest


# CONFIG is populated by our test script.
CONFIG = {
    'VERBOSITY': 0,
}

# cms_config holds the decoded-JSON of the cms.conf configuration file.
global cms_config
cms_config = None

# We store a list of all services that are running so that we can cleanly shut
# them down.
global running_services
running_services = {}

global running_servers
running_servers = {}

global created_users
created_users = {}

global created_tasks
created_tasks = {}


class FrameworkException(Exception):
    pass


class RemoteService(object):
    """Class which implements the RPC protocol used by CMS.

    This is deliberately a re-implementation in order to catch or
    trigger bugs in the CMS services.

    """
    def __init__(self, service_name, shard):
        address, port = cms_config["core_services"][service_name][shard]

        self.service_name = service_name
        self.shard = shard
        self.address = address
        self.port = port

    def call(self, function_name, data):
        """Perform a synchronous RPC call."""
        s = json.dumps({
            "__id": "foo",
            "__method": function_name,
            "__data": data,
        })
        msg = s + "\r\n"

        # Send message.
        sock = socket.socket()
        sock.connect((self.address, self.port))
        sock.send(msg)

        # Wait for response.
        s = ''
        while len(s) < 2 or s[-2:] != "\r\n":
            s += sock.recv(1)
        s = s[:-2]
        sock.close()

        # Decode reply.
        reply = json.loads(s)

        return reply


def read_cms_config():
    global cms_config
    cms_config = json.load(io.open("%(CONFIG_PATH)s" % CONFIG,
                                   "rt", encoding="utf-8"))


def get_cms_config():
    if cms_config is None:
        read_cms_config()
    return cms_config


def sh(cmdline, ignore_failure=False):
    """Execute a simple shell command.

    If cmdline is a string, it is passed to sh -c verbatim.  All escaping must
    be performed by the user.  If cmdline is an array, then no escaping is
    required.

    """
    if CONFIG["VERBOSITY"] >= 1:
        print('$', cmdline)
    if CONFIG["VERBOSITY"] >= 3:
        cmdline += ' > /dev/null 2>&1'
    if isinstance(cmdline, list):
        ret = subprocess.call(cmdline)
    else:
        ret = os.system(cmdline)
    if not ignore_failure and ret != 0:
        raise FrameworkException(
            "Execution failed with %d/%d. Tried to execute:\n%s\n" %
            (ret & 0xff, ret >> 8, cmdline))


def spawn(cmdline):
    """Execute a python application."""

    def kill(job):
        try:
            job.kill()
        except OSError:
            pass

    if CONFIG["VERBOSITY"] >= 1:
        print('$', ' '.join(cmdline))

    if CONFIG["TEST_DIR"] is not None:
        cmdline = ['python-coverage', 'run', '-p', '--source=cms'] + \
            cmdline

    if CONFIG["VERBOSITY"] >= 3:
        stdout = None
        stderr = None
    else:
        stdout = io.open(os.devnull, 'wb')
        stderr = stdout
    job = subprocess.Popen(cmdline, stdout=stdout, stderr=stderr)
    atexit.register(lambda: kill(job))
    return job


def info(s):
    print('==>', s)


def configure_cms(options):
    """Creates the cms.conf file, setting any parameters as requested.

    The parameters are substituted in textually, and thus this may be
    quite fragile.

    options (dict): mapping from parameter to textual JSON argument.

    """
    f = io.open("%(TEST_DIR)s/examples/cms.conf.sample" % CONFIG,
                "rt", encoding="utf-8")
    lines = f.readlines()
    unset = set(options.keys())
    for i, line in enumerate(lines):
        g = re.match(r'^(\s*)"([^"]+)":', line)
        if g:
            whitespace, key = g.groups()
            if key in unset:
                lines[i] = '%s"%s": %s,\n' % (whitespace, key, options[key])
                unset.remove(key)

    out_file = io.open("%(CONFIG_PATH)s" % CONFIG, "wt", encoding="utf-8")
    for l in lines:
        out_file.write(l)
    out_file.close()

    if unset:
        print("These configuration items were not set:")
        print("  " + ", ".join(sorted(list(unset))))

    # Load the config database.
    read_cms_config()


def start_prog(path, shard=0, contest=None):
    """Execute a CMS process."""
    args = [path]
    if shard is not None:
        args.append("%s" % shard)
    if contest is not None:
        args += ['-c', "%s" % contest]
    return spawn(args)


def start_servicer(service_name, check, shard=0, contest=None):
    """Start a CMS service."""

    info("Starting %s." % service_name)
    executable = os.path.join('.', 'scripts', 'cms%s' % (service_name))
    if CONFIG["TEST_DIR"] is None:
        executable = 'cms%s' % service_name
    prog = start_prog(executable, shard=shard, contest=contest)

    # Wait for service to come up - ping it!
    attempts = 0
    while attempts <= 12:
        attempts += 1
        try:
            try:
                check(service_name, shard)
            except socket.error as error:
                if error.errno != errno.ECONNREFUSED:
                    raise error
                else:
                    time.sleep(0.1 * (1.2 ** attempts))
                    continue
            else:
                return prog
        except Exception:
            print("Unexpected exception while waiting for the service:")
            raise

    # If we arrive here, it means the service was not fired up.
    if shard is None:
        raise FrameworkException("Failed to bring up service %s" %
                                 service_name)
    else:
        raise FrameworkException("Failed to bring up service %s/%d" %
                                 (service_name, shard))


def check_service(service_name, shard):
    """Check if the service is up."""
    rs = RemoteService(service_name, shard)
    reply = rs.call("echo", {"string": "hello"})
    if reply['__data'] != 'hello':
        raise Exception("Strange response from service.")


def start_service(service_name, shard=0, contest=None):
    """Start a CMS service."""
    prog = start_servicer(service_name, check_service, shard, contest)
    rs = RemoteService(service_name, shard)
    running_services[(service_name, shard, contest)] = (rs, prog)

    return prog


def restart_service(service_name, shard=0, contest=None):
    shutdown_service(service_name, shard, contest)
    return start_service(service_name, shard, contest)


def check_server(service_name, shard):
    """Check if the server is up."""
    check_service(service_name, shard)
    if service_name == 'AdminWebServer':
        port = cms_config['admin_listen_port']
    else:
        port = cms_config['contest_listen_port'][shard]
    sock = socket.socket()
    sock.connect(('127.0.0.1', port))
    sock.close()


def start_server(service_name, shard=0, contest=None):
    """Start a CMS server."""
    prog = start_servicer(service_name, check_server, shard, contest)
    running_servers[service_name] = prog

    return prog


def check_ranking_web_server(service_name, shard):
    """Check if RankingWebServer is up."""
    assert service_name == "RankingWebServer"
    assert shard is None
    url = urlsplit(cms_config['rankings'][0])
    sock = socket.socket()
    sock.connect((url.hostname, url.port))
    sock.close()


def start_ranking_web_server():
    """Start the RankingWebServer. It's a bit special compared to the
    others.

    """
    prog = start_servicer(
        "RankingWebServer", check_ranking_web_server, shard=None)
    running_servers['RankingWebServer'] = prog
    return prog


def shutdown_service(service_name, shard=0, contest=None):
    rs, prog = running_services[(service_name, shard, contest)]

    info("Asking %s/%d to terminate..." % (service_name, shard))
    rs = running_services[(service_name, shard, contest)]
    rs = RemoteService(service_name, shard)
    rs.call("quit", {"reason": "from test harness"})
    prog.wait()

    del running_services[(service_name, shard, contest)]


def shutdown_services():
    for key in running_services.keys():
        service_name, shard, contest = key
        shutdown_service(service_name, shard, contest)

    for name, server in running_servers.iteritems():
        info("Terminating %s." % name)
        os.kill(server.pid, signal.SIGINT)
        server.wait()


def combine_coverage():
    info("Combining coverage results.")
    sh("python-coverage combine")


def admin_req(path, multipart_post=False, args=None, files=None):
    url = 'http://localhost:8889' + path
    br = mechanize.Browser()
    br.set_handle_robots(False)

    # Some requests must be forced to be multipart.
    # Do this by making files not None.
    if multipart_post and files is None:
        files = []

    return cmstestsuite.web.browser_do_request(br, url, args, files)


def get_tasks(contest_id):
    '''Return a list of existing tasks, returned as a dictionary of
      'taskname' => { 'id': ..., 'title': ... }

    '''
    r = admin_req('/tasklist/%d' % contest_id)
    groups = re.findall(r'''
        <tr> \s*
        <td> \s* (.*) \s* </td> \s*
        <td><a\s+href="../task/(\d+)">(.*)</a></td>
        ''', r.read(), re.X)
    tasks = {}
    for g in groups:
        title, id, name = g
        id = int(id)
        tasks[name] = {
            'title': title,
            'id': id,
        }

    return tasks


def get_users(contest_id):
    '''Return a list of existing users, returned as a dictionary of
      'username' => { 'id': ..., 'firstname': ..., 'lastname': ... }

    '''
    r = admin_req('/userlist/%d' % contest_id)
    groups = re.findall(r'''
        <tr> \s*
        <td> \s* (.*) \s* </td> \s*
        <td> \s* (.*) \s* </td> \s*
        <td><a\s+href="../user/(\d+)">(.*)</a></td>
        ''', r.read(), re.X)
    users = {}
    for g in groups:
        firstname, lastname, id, username = g
        id = int(id)
        users[username] = {
            'firstname': firstname,
            'lastname': lastname,
            'id': id,
        }

    return users


def add_contest(**kwargs):
    resp = admin_req('/contest/add', multipart_post=True, args=kwargs)
    # Contest ID is returned as HTTP response.
    page = resp.read()
    match = re.search(
        r'<form enctype="multipart/form-data" action="../contest/([0-9]+)" '
        'method="POST" name="edit_contest">',
        page)
    if match is None:
        raise FrameworkException("Unable to create contest.")
    return int(match.groups()[0])


def add_task(contest_id, **kwargs):
    # We need to specify token_mode. Why this and no others?
    if 'token_mode' not in kwargs:
        kwargs['token_mode'] = 'disabled'

    r = admin_req('/add_task/%d' % contest_id,
                  multipart_post=True,
                  args=kwargs)
    g = re.search(r'/task/([0-9]+)$', r.geturl())
    if g:
        task_id = int(g.group(1))
        created_tasks[task_id] = kwargs
        return task_id
    else:
        raise FrameworkException("Unable to create task.")


def add_manager(task_id, manager):
    args = {}
    files = [
        ('manager', manager),
    ]
    dataset_id = get_task_active_dataset_id(task_id)
    admin_req('/add_manager/%d' % (dataset_id),
              multipart_post=True, files=files, args=args)


def get_task_active_dataset_id(task_id):
    resp = admin_req('/task/%d' % task_id)
    page = resp.read()
    match = re.search(
        r'id="title_dataset_([0-9]+).* \(Live\)</',
        page)
    if match is None:
        raise FrameworkException("Unable to create contest.")
    dataset_id = int(match.groups()[0])
    return dataset_id


def add_testcase(task_id, num, input_file, output_file, public):
    files = [
        ('input', input_file),
        ('output', output_file),
    ]
    args = {}
    args["codename"] = "%03d" % num
    if public:
        args['public'] = '1'
    dataset_id = get_task_active_dataset_id(task_id)
    admin_req('/add_testcase/%d' % (dataset_id),
              multipart_post=True, files=files, args=args)


def add_user(contest_id, **kwargs):
    r = admin_req('/add_user/%d' % contest_id, args=kwargs)
    g = re.search(r'/user/([0-9]+)$', r.geturl())
    if g:
        user_id = int(g.group(1))
        created_users[user_id] = kwargs
        return user_id
    else:
        raise FrameworkException("Unable to create user.")


def add_existing_task(contest_id, task_id, **kwargs):
    '''Add information about an existing task to our database so that we can
    use it for submitting later.'''
    created_tasks[task_id] = kwargs


def add_existing_user(contest_id, user_id, **kwargs):
    '''Add information about an existing user to our database so that we can
    use it for submitting later.'''
    created_users[user_id] = kwargs


def cws_submit(contest_id, task_id, user_id, filename, language):
    username = created_users[user_id]['username']
    password = created_users[user_id]['password']
    base_url = 'http://localhost:8888/'
    task = (task_id, created_tasks[task_id]['name'])

    def step(request):
        request.prepare()
        request.execute()

    browser = mechanize.Browser()
    browser.set_handle_robots(False)

    lr = LoginRequest(browser, username, password, base_url=base_url)
    step(lr)
    sr = SubmitRequest(browser, task, base_url=base_url, filename=filename)
    step(sr)

    submission_id = sr.get_submission_id()

    if submission_id is None:
        raise FrameworkException("Failed to submit solution.")

    return submission_id


def get_evaluation_result(contest_id, submission_id, timeout=30):
    browser = mechanize.Browser()
    browser.set_handle_robots(False)
    base_url = 'http://localhost:8889/'

    WAITING_STATUSES = re.compile(
        r'Compiling\.\.\.|Evaluating\.\.\.|Evaluated')
    COMPLETED_STATUS = re.compile(
        r'Compilation failed|Evaluated \(')

    num_tries = timeout
    while num_tries > 0:
        num_tries -= 1

        sr = AWSSubmissionViewRequest(browser, submission_id,
                                      base_url=base_url)
        sr.prepare()
        sr.execute()

        result = sr.get_submission_info()
        status = result['status']

        if COMPLETED_STATUS.search(status):
            return result

        if WAITING_STATUSES.search(status):
            time.sleep(1)
            continue

        raise FrameworkException("Unknown submission status: %s" % status)

    raise FrameworkException("Waited too long for result.")
