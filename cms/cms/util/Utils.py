#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import time
import datetime
import os
import sys
import codecs
import hashlib


## ANSI utilities ##
# see for reference: http://pueblo.sourceforge.net/doc/manual/ansi_color_codes.html

ANSI_FG_COLORS = {'black':   30,
                  'red':     31,
                  'green':   32,
                  'yellow':  33,
                  'blue':    34,
                  'magenta': 35,
                  'cyan':    36,
                  'white':   37}

ANSI_BG_COLORS = {'black':   40,
                  'red':     41,
                  'green':   42,
                  'yellow':  43,
                  'blue':    44,
                  'magenta': 45,
                  'cyan':    46,
                  'white':   47}

ANSI_RESET_CMD = 0
ANSI_FG_DEFAULT_CMD = 39
ANSI_BG_DEFAULT_CMD = 49
ANSI_BOLD_ON_CMD = 1
ANSI_BOLD_OFF_CMD = 22
ANSI_ITALICS_ON_CMD = 3
ANSI_ITALICS_OFF_CMD = 23
ANSI_UNDERLINE_ON_CMD = 4
ANSI_UNDERLINE_OFF_CMD = 24
ANSI_STRIKETHROUGH_ON_CMD = 9
ANSI_STRIKETHROUGH_OFF_CMD = 29
ANSI_INVERT_CMD = 7


def filter_ansi_escape(s):
    """Filter out ANSI commands from the given string.

    """
    ansi_mode = False
    res = ''
    for c in s:
        if c == u'\033':
            ansi_mode = True
        if not ansi_mode:
            res += c
        if c == u'm':
            ansi_mode = False
    return res


def ansi_command(*args):
    """Produce the escape string that corresponds to the given ANSI
    command.

    """
    return '\033[%sm' % (";".join(map(lambda x: str(x), args)))


def ansi_color_hash(s):
    """Enclose a string in a ANSI code giving it a color that
    depends on its content.

    s (string): the string to color
    return (string): s enclosed in an ANSI code

    """
    # Magic number: 30 is the lowest of ANSI_FG_COLORS
    return 30 + (sum([ord(x) for x in s]) % len(ANSI_FG_COLORS))


def ansi_color_string(s, col):
    """Enclose a string in a ANSI code giving it the specified color.

    s (string): the string to color
    col (int): the color ANSI code
    return (string): s enclosed in an ANSI code

    """
    return ansi_command(col, ANSI_BOLD_ON_CMD) + \
        s + ansi_command(ANSI_RESET_CMD)


## Logging utilities ##

SEV_CRITICAL = "CRITICAL"
SEV_ERROR    = "ERROR   "
SEV_WARNING  = "WARNING "
SEV_INFO     = "INFO    "
SEV_DEBUG    = "DEBUG   "

SEVERITY_COLORS = {SEV_CRITICAL: 'red',
                   SEV_ERROR:    'red',
                   SEV_WARNING:  'yellow',
                   SEV_INFO:     'green',
                   SEV_DEBUG:    'cyan'}


def format_log(msg, coord, operation, severity, timestamp, colors=False):
    """Format a log message in a common way (for local and remote
    logging).

    msg (string): the message to log
    operation (string): a high-level description of the long-term
                        operation that is going on in the service
    severity (string): a constant defined in Logger
    timestamp (float): seconds from epoch
    colors (bool): whether to use ANSI color commands (for the logs
                   directed to a shell)
    returns (string): the formatted log

    """
    d = datetime.datetime.fromtimestamp(timestamp)
    service_full = coord
    if operation != "":
        service_full += "/%s" % (operation)

    if colors:
        severity_color = ANSI_FG_COLORS[SEVERITY_COLORS[severity]]
        coord_color = ansi_color_hash(coord)
        if operation == "":
            format_string = "%s [%s] %%s" % \
                (ansi_color_string("%s - %s", severity_color),
                 ansi_color_string("%s", coord_color))
        else:
            operation_color = ansi_color_hash(operation)
            format_string = "%s [%s/%s] %%s" % \
                (ansi_color_string("%s - %s", severity_color),
                 ansi_color_string("%s", coord_color),
                 ansi_color_string("%s", operation_color))
    else:
        if operation == "":
            format_string = "%s - %s [%s] %s"
        else:
            format_string = "%s - %s [%s/%s] %s"

    if operation == "":
        return format_string % ('{0:%Y/%m/%d %H:%M:%S}'.format(d),
                                severity, coord, msg)
    else:
        return format_string % ('{0:%Y/%m/%d %H:%M:%S}'.format(d),
                                severity, coord, operation, msg)


## Other utilities ##

def maybe_mkdir(d):
    """Make a directory without throwing an exception if it already
    exists. Warning: this method fails silently also if the directory
    could not be created because there is a non-directory file with
    the same name. In oter words, there is no guarantee that after the
    execution, the file d exists and is a directory.

    """
    try:
        os.mkdir(d)
    except OSError:
        pass


def sha1sum(path):
    """Calculates the SHA1 sum of a file, given by its path.

    """
    BUFLEN = 8192
    with open(path, 'rb') as fin:
        hasher = hashlib.sha1()
        buf = fin.read(BUFLEN)
        while buf != '':
            hasher.update(buf)
            buf = fin.read(BUFLEN)
        return hasher.hexdigest()


def get_compilation_command(language, source_filenames, executable_filename):
    """Returns the compilation command for the specified language,
    source filenames and executable filename. The command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    language (string): one of the recognized languages.
    source_filenames (list): a list of the string that are the
                             filenames of the source files to compile.
    executable_filename (string): the output file.
    return (list): a list of string to be passed to subprocess.

    """
    # For compiling in 32-bit mode under 64-bit OS: add "-march=i686",
    # "-m32" for gcc/g++. Don't know about Pascal. Anyway, this will
    # require some better support from the evaluation environment
    # (particularly the sandbox, which has to be compiled in a
    # different way depending on whether it will execute 32- or 64-bit
    # programs).
    if language == "c":
        command = ["/usr/bin/gcc", "-DEVAL", "-static", "-O2", "-lm", "-o", executable_filename]
    elif language == "cpp":
        command = ["/usr/bin/g++", "-DEVAL", "-static", "-O2", "-o", executable_filename]
    elif language == "pas":
        command = ["/usr/bin/fpc", "-dEVAL", "-XS", "-O2", "-o%s" % (executable_filename)]
    return command + source_filenames


def format_time_or_date(timestamp):
    """Return timestamp formatted as HH:MM:SS if the date is
    the same date as today, as a complete date + time if the
    date is different.

    timestamp (int): unix time.
    return (string): timestamp formatted as above.

    """
    dt_ts = datetime.datetime.fromtimestamp(timestamp)
    if dt_ts.date() == datetime.date.today():
        return dt_ts.strftime("%H:%M:%S")
    else:
        return dt_ts.strftime("%H:%M:%S, %d/%m/%Y")


WHITES = " \t\n\r"


def white_diff_canonicalize(s):
    """Convert the input string to a canonical form for the white diff
    algorithm; that is, the strings a and b are mapped to the same
    string by white_diff_canonicalize() if and only if they have to be
    considered equivalent for the purposes of the white_diff
    algorithm.

    More specifically, this function strips all the leading and
    trailing whitespaces from s and collapse all the runs of
    consecutive whitespaces into just one copy of one specific
    whitespace.

    s (string): the string to canonicalize.
    return (string): the canonicalized string.

    """
    # Replace all the whitespaces with copies of " ", making the rest
    # of the algorithm simpler
    for c in WHITES[1:]:
        s = s.replace(c, WHITES[0])

    # Split the string according to " ", filter out empty tokens and
    # join again the string using just one copy of the first
    # whitespace; this way, runs of more than one whitespaces are
    # collapsed into just one copy.
    s = WHITES[0].join([x for x in s.split(WHITES[0])
                        if x != ''])
    return s


def white_diff(output, res):
    """Compare the two output files. Two files are equal if for every
    integer i, line i of first file is equal to line i of second
    file. Two lines are equal if they differ only by number or type of
    whitespaces.

    Note that trailing lines composed only of whitespaces don't change
    the 'equality' of the two files. Note also that by line we mean
    'sequence of characters ending with \n or EOF and beginning right
    after BOF or \n'. In particular, every line has *at most* one \n.

    output (file): the first file to compare.
    res (file): the second file to compare.
    return (bool): True if the two file are equal as explained above.

    """

    while True:
        lout = output.readline()
        lres = res.readline()

        # Both files finished: comparison succeded
        if lres == '' and lout == '':
            return True

        # Only one file finished: ok if the other contains only blanks
        elif lres == '' or lout == '':
            lout = lout.strip(WHITES)
            lres = lres.strip(WHITES)
            if lout != '' or lres != '':
                return False

        # Both file still have lines to go: ok if they agree except
        # for the number of whitespaces
        else:
            lout = white_diff_canonicalize(lout)
            lres = white_diff_canonicalize(lres)
            if lout != lres:
                return False


def valid_ip(ip):
    """Return True if ip is a valid IPv4 address.

    ip (string): the ip to validate.

    return (bool): True iff valid.

    """
    fields = ip.split(".")
    if len(fields) != 4:
        return
    for field in fields:
        try:
            num = int(field)
        except Exception as error:
            return False
        if num < 0 or num >= 256:
            return False
    return True
