#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
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

import datetime
import os
import hashlib


def mkdir(path):
    """Make a directory without complaining for errors.

    path (string): the path of the directory to create
    returns (bool): True if the dir is ok, False if it is not

    """
    try:
        os.mkdir(path)
        return True
    except OSError:
        if os.path.isdir(path):
            return True
    return False


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


def get_compilation_command(language, source_filenames, executable_filename,
                            for_evaluation=True):
    """Returns the compilation command for the specified language,
    source filenames and executable filename. The command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    language (string): one of the recognized languages.
    source_filenames (list): a list of the string that are the
                             filenames of the source files to compile.
    executable_filename (string): the output file.
    for_evaluation (bool): if True, define EVAL during the compilation;
                           defaults to True.
    return (list): a list of string to be passed to subprocess.

    """
    # For compiling in 32-bit mode under 64-bit OS: add "-march=i686",
    # "-m32" for gcc/g++. Don't know about Pascal. Anyway, this will
    # require some better support from the evaluation environment
    # (particularly the sandbox, which has to be compiled in a
    # different way depending on whether it will execute 32- or 64-bit
    # programs).
    if language == "c":
        command = ["/usr/bin/gcc"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-lm", "-o", executable_filename]
        command += source_filenames
    elif language == "cpp":
        command = ["/usr/bin/g++"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-o", executable_filename]
        command += source_filenames
    elif language == "pas":
        command = ["/usr/bin/fpc"]
        if for_evaluation:
            command += ["-dEVAL"]
        command += ["-XS", "-O2", "-o%s" % executable_filename]
        command += source_filenames
    return command


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


def white_diff_canonicalize(string):
    """Convert the input string to a canonical form for the white diff
    algorithm; that is, the strings a and b are mapped to the same
    string by white_diff_canonicalize() if and only if they have to be
    considered equivalent for the purposes of the white_diff
    algorithm.

    More specifically, this function strips all the leading and
    trailing whitespaces from s and collapse all the runs of
    consecutive whitespaces into just one copy of one specific
    whitespace.

    string (string): the string to canonicalize.
    return (string): the canonicalized string.

    """
    # Replace all the whitespaces with copies of " ", making the rest
    # of the algorithm simpler
    for char in WHITES[1:]:
        string = string.replace(char, WHITES[0])

    # Split the string according to " ", filter out empty tokens and
    # join again the string using just one copy of the first
    # whitespace; this way, runs of more than one whitespaces are
    # collapsed into just one copy.
    string = WHITES[0].join([x for x in string.split(WHITES[0])
                             if x != ''])
    return string


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
        except ValueError:
            return False
        if num < 0 or num >= 256:
            return False
    return True
