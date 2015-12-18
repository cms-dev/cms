#!/usr/bin/env python2

from __future__ import print_function
from gevent import monkey, sleep, spawn
from gevent.socket import wait_read, wait_write
from gevent.pywsgi import WSGIServer
monkey.patch_all()
import psycopg2
import pickle
import sys
import base64
from datetime import timedelta
import traceback
from cms import config
from cms.server import compute_actual_phase
from cmscommon.datetime import make_datetime
from tornado.web import decode_signed_value


def gevent_wait_callback(conn, timeout=None):
    """A wait callback useful to allow gevent to work with Psycopg."""
    while 1:
        state = conn.poll()
        if state == psycopg2.extensions.POLL_OK:
            break
        elif state == psycopg2.extensions.POLL_READ:
            wait_read(conn.fileno(), timeout=timeout)
        elif state == psycopg2.extensions.POLL_WRITE:
            wait_write(conn.fileno(), timeout=timeout)
        else:
            raise psycopg2.OperationalError(
                "Bad result from poll: %r" % state)

psycopg2.extensions.set_wait_callback(gevent_wait_callback)

class AuthServer(object):
    def updater(self):
        try:
            conn_info = config.database.split('/')[2]
            conn_db = config.database.split('/')[3]
            conn_host = conn_info.split('@')[1]
            conn_user, conn_password = conn_info.split('@')[0].split(':')
            conn = psycopg2.connect("user=%s dbname=%s password=%s host=%s" % (conn_user, conn_db, conn_password, conn_host))
            cur = conn.cursor()
        except:
            traceback.print_exc()
            sys.exit(2)
        while True:
            try:
                sleep(0.5)
                self.timestamp = make_datetime()
                cur.execute("SELECT ip_autologin, start, stop, per_user_time FROM contests WHERE id = %s;", (self.contest_id,))
                contests = cur.fetchall()
                assert(len(contests) == 1)
                contest = contests[0]
                self.contest = dict(zip(["ip_autologin", "start", "stop", "per_user_time"], contest))
                cur.execute("""SELECT ip, starting_time, delay_time, extra_time, participations.password, users.password, username
                               FROM participations INNER JOIN users ON user_id = users.id
                               WHERE contest_id = %%s %s;""" % ("AND hidden == 'f'" if config.block_hidden_users else ""),
                            (self.contest_id,))
                participations = cur.fetchall()
                username_participation = dict()
                ip_participation = dict()
                wrong_ips = set()
                for part in participations:
                    part = dict(zip(["ip", "starting_time", "delay_time", "extra_time", "password", "u_password", "username"], part))
                    if part["password"] is None:
                        part["password"] = part["u_password"]
                    username_participation[part["username"]] = part
                    if part["ip"] in ip_participation:
                        del ip_participation[part["ip"]]
                        wrong_ips.add(part["ip"])
                    if part["ip"] not in wrong_ips:
                        ip_participation[part["ip"]] = part
                self.ip_participation = ip_participation
                self.username_participation = username_participation
            except:
                traceback.print_exc()

    def __init__(self, contest):
        self.contest_id = contest
        self.cookie_key = base64.b64encode(config.secret_key)
        self.username_participation = dict()
        self.ip_participation = dict()
        spawn(self.updater)

    def get_participation(self, cookies, addr):
        if self.contest["ip_autologin"]:
            return self.ip_participation.get(addr, None)
        cookies = map(lambda x: x.strip(), cookies.split(";"))
        login_cookie = None
        for lc in cookies:
            if lc.startswith('login='):
                login_cookie = lc[7:-1]
        if login_cookie is None:
            return None
        username, password, time = pickle.loads(decode_signed_value(self.cookie_key, 'login', login_cookie))
        if self.timestamp - make_datetime(time) > timedelta(seconds=config.cookie_duration):
            return None
        part = self.username_participation.get(username, None)
        if part is None:
            return None
        if part["password"] != password:
            return None
        # TODO: check IP lock
        return part

    def check(self, cookies, addr):
        try:
            participation = self.get_participation(cookies, addr)
            if participation is None:
                return False
            return compute_actual_phase(
                self.timestamp, self.contest["start"], self.contest["stop"],
                self.contest["per_user_time"], participation["starting_time"],
                participation["delay_time"], participation["extra_time"])[0] == 0
        except:
            traceback.print_exc()
            return False

    def __call__(self, env, start_response):
        if 'HTTP_COOKIE' in env and self.check(env['HTTP_COOKIE'], env['REMOTE_ADDR']):
            start_response('200 OK', [])
        else:
            start_response('403 Forbidden', [])
        return ""



def main():
    contest = None
    for i in xrange(1, len(sys.argv)-1):
        if sys.argv[i] == '-c':
            contest = int(sys.argv[i+1])
    if contest is None:
        print("Usage: %s -c contest" % sys.argv[0], file=sys.stderr)
        sys.exit(1)
    WSGIServer(('', 8088), AuthServer(contest)).serve_forever()
