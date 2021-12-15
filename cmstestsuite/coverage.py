#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2017 Luca Chiodini <luca@chiodini.org>
# Copyright © 2021 Andrey Vihrov <andrey.vihrov@gmail.com>
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

import os
import logging
import requests
import subprocess
import sys
from urllib.parse import urlparse

from cmstestsuite import CONFIG, sh


logger = logging.getLogger(__name__)


_COVERAGE_DIRECTORIES = [
    "cms",
    "cmscommon",
    "cmscontrib",
    "cmsranking",
    "cmstaskenv",
]
_COVERAGE_CMDLINE = [
    sys.executable, "-m", "coverage", "run", "-p",
    "--source=%s" % ",".join(_COVERAGE_DIRECTORIES)]


def coverage_cmdline(cmdline):
    """Return a cmdline possibly decorated to record coverage."""
    if CONFIG.get('COVERAGE', False):
        return _COVERAGE_CMDLINE + cmdline
    else:
        return cmdline


def clear_coverage():
    """Clear existing coverage reports."""
    if CONFIG.get('COVERAGE', False):
        logging.info("Clearing old coverage data.")
        sh([sys.executable, "-m", "coverage", "erase"])


def combine_coverage():
    """Combine coverage reports from different programs."""
    if CONFIG.get('COVERAGE', False):
        logger.info("Combining coverage results.")
        sh([sys.executable, "-m", "coverage", "combine"])
        sh([sys.executable, "-m", "coverage", "xml"])


# Cache directory for subsequent runs.
_CODECOV_DIR = os.path.join("cache", "cmstestsuite", "codecov")


def _download_file(url, out):
    """Download and save a binary file.

    url (str): file to download.
    out (str): output file name.

    """
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(out, "wb") as f:
        for chunk in r.iter_content(chunk_size=4096):
            f.write(chunk)


def _import_pgp_key(gpg_home, keyring, fingerprint):
    """Import a PGP key from public keyservers.

    gpg_home (str): GnuPG home directory.
    keyring (str): Keyring file to use.
    fingerprint (str): PGP key fingerprint.

    """

    keyservers = [ "hkps://keyserver.ubuntu.com", "hkps://pgp.mit.edu" ]

    for keyserver in keyservers:
        logger.info("Importing PGP key %s from %s." %
                    (fingerprint[-8:], urlparse(keyserver).netloc))
        try:
            subprocess.check_call(["gpg", "--homedir", gpg_home, "--keyring",
                                   keyring, "--no-default-keyring",
                                   "--keyserver", keyserver,
                                   "--recv-keys", fingerprint])
            return
        except subprocess.CalledProcessError:
            logger.warning("PGP key import failed.", exc_info=True)

    raise Exception("No usable keyservers left.")


def _get_codecov_uploader():
    """Fetch and return the Codecov uploader.

    return (str): path to the stored uploader.

    """
    base_url = "https://uploader.codecov.io/latest/linux/"
    executable = "codecov"
    shasum = "codecov.SHA256SUM"
    sigfile = "codecov.SHA256SUM.sig"

    gpg_home = os.path.realpath(os.path.join(_CODECOV_DIR, "gnupg"))
    # Codecov Uploader (Codecov Uploader Verification Key)
    # <security@codecov.io>
    fingerprint = "27034E7FDB850E0BBC2C62FF806BB28AED779869"

    if not os.access(os.path.join(_CODECOV_DIR, executable), os.X_OK):
        os.makedirs(gpg_home, mode=0o700)
        _import_pgp_key(gpg_home, "trustedkeys.gpg", fingerprint)

        logger.info("Fetching Codecov uploader.")
        for name in [executable, shasum, sigfile]:
            _download_file(base_url + name, os.path.join(_CODECOV_DIR, name))

        logger.info("Checking Codecov uploader integrity.")
        subprocess.check_call(["gpgv", "--homedir", gpg_home, sigfile, shasum],
                              cwd=_CODECOV_DIR)
        subprocess.check_call(["sha256sum", "-c", shasum], cwd=_CODECOV_DIR)

        os.chmod(os.path.join(_CODECOV_DIR, executable), 0o755)

    return os.path.join(_CODECOV_DIR, executable)


def send_coverage_to_codecov(flag):
    """Send the coverage report to Codecov with the given flag."""
    if CONFIG.get('COVERAGE', False):
        logger.info("Sending coverage results to codecov for flag %s." % flag)
        uploader = _get_codecov_uploader()
        subprocess.check_call([uploader, "-F", flag])
