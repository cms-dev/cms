#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Martin Mareš <mj@ucw.cz>
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

"""Install CMS to a virtual environment.
"""

from argparse import ArgumentParser, Namespace
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import NoReturn
import venv


target_path: Path
is_verbose: bool


def progress(msg: str) -> None:
    print('** ' + msg)


def error(msg: str) -> NoReturn:
    print('ERROR: ' + msg)
    sys.exit(1)


def verbose(msg: str) -> None:
    if is_verbose:
        print(msg)


def find_target_path(dir: str | None) -> Path:
    if dir:
        tp = Path(dir)
    else:
        tp = Path.home() / 'cms'
    if (tp / 'cms/server/__init__.py').is_file():
        error(f'Target directory {tp} seems to contain the CMS source tree.'
              + (' You probably need to specify --dir=...' if not dir else ""))
    return tp


INSTALL_DIRS = [
    'etc',
    'log',
    'cache/fs-cache-shared',
    'lib',
    'run',
    'include',
]


INSTALL_CONFIGS = [
    ('cms.toml', 'config/cms.sample.toml'),
    ('cms_ranking.toml', 'config/cms_ranking.sample.toml'),
]


INSTALL_SYSTEMD_SERVICES = [
    'cms@.service',
    'cms-logging.service',
    'cms-ranking.service',
]


def create_dirs() -> None:
    progress(f"Creating directories under {target_path}")
    for dir in INSTALL_DIRS:
        (target_path / dir).mkdir(mode=0o755, parents=True, exist_ok=True)


def create_venv() -> None:
    if (target_path / 'bin/python').is_file():
        verbose("Python virtual environment already exists")
    else:
        progress("Creating Python virtual environment")
        venv.create(str(target_path), symlinks=True, with_pip=True, prompt=target_path.name)
        subprocess.run(
            # setuptools >= 81 deprecate pkg_resources
            [str(target_path / 'bin/pip'), 'install', '-U', 'pip', 'wheel'],
            check=True)


def install_package() -> None:
    progress("Installing CMS package" + (" (editable)" if args.editable else ""))
    subprocess.run(
        [str(target_path / 'bin/pip'), 'install']
            + ['-c', 'constraints.txt']
            + (['-e'] if args.editable else [])
            + ['.' + ('[devel]' if args.devel else "")],
        check=True)


def install_config() -> None:
    for config, sample in INSTALL_CONFIGS:
        config_path = target_path / 'etc' / config
        if config_path.is_file():
            verbose(f"Configuration file {config_path} already exists")
        else:
            progress(f"Installing {sample} as {config_path}")
            shutil.copyfile(sample, config_path)


def check_isolate(args: Namespace) -> None:
    progress('Checking if isolate is available')
    isolate = shutil.which('isolate', mode=os.F_OK)
    if isolate is None:
        error('Cannot find isolate in $PATH. Is it installed?')
    if not os.access(isolate, os.X_OK):
        st = os.stat(isolate)
        exec_for_group = st.st_mode & 0o4011 == 0o4010
        error('Isolate exists, but it is not executable.'
              + (' Are you in the isolate group?' if exec_for_group else ""))


def install_cms(args: Namespace) -> None:
    if not args.skip_isolate:
        check_isolate(args)
    create_dirs()
    create_venv()
    install_package()
    install_config()


def install_venv_with_deps(args: Namespace) -> None:
    create_venv()
    progress("Installing Python dependencies")
    subprocess.run(
        [str(target_path / 'bin/pip'), 'install', '-r', 'constraints.txt'],
        check=True)


def install_systemd(args: Namespace) -> None:
    progress("Installing systemd services")
    source_path = Path('config/systemd')
    dest_path = Path('~/.config/systemd/user').expanduser()
    dest_path.mkdir(parents=True, exist_ok=True)
    for service in INSTALL_SYSTEMD_SERVICES:
        source = source_path / service
        dest = dest_path / service
        if dest.is_file() and not args.force:
            print(f'{dest} already exists, use --force to overwrite it.')
        else:
            body = source.read_text()
            body = body.replace('@CMS_DIR@', str(target_path))
            dest.write_text(body)
            verbose(f'{dest} installed')

    progress("Reloading user systemd")
    subprocess.run(['systemctl', '--user', 'daemon-reload'],
                   check=True)


if __name__ == '__main__':
    parser = ArgumentParser(
        description='Script used to install CMS')

    parser.add_argument(
        "--dir", type=str,
        help='Directory to install CMS to (default: ~/cms)')

    parser.add_argument(
        "--skip-isolate", default=False, action='store_true',
        help='Do not check that isolate is available')

    parser.add_argument(
        "-v", "--verbose", default=False, action='store_true',
        help='Show more details')

    subparsers = parser.add_subparsers(metavar="command",
                                       help="Subcommand to run")

    cms_cmd = subparsers.add_parser("cms", help="Complete installation of CMS")
    cms_cmd.set_defaults(func=install_cms)
    cms_cmd.add_argument(
        "-e", "--editable", default=False, action='store_true',
        help='Install CMS Python packages as editable')
    cms_cmd.add_argument(
        "-d", "--devel", default=False, action='store_true',
        help='Install dependencies used for development')

    (subparsers.add_parser("venv", help="Only prepare the Python virtual environment with dependencies")
        .set_defaults(func=install_venv_with_deps))

    (subparsers.add_parser("check-isolate", help="Only check that isolate is available")
        .set_defaults(func=check_isolate))

    systemd_cmd = subparsers.add_parser("systemd", help="Install user systemd services for starting CMS")
    systemd_cmd.set_defaults(func=install_systemd)
    systemd_cmd.add_argument(
        "-f", "--force", default=False, action='store_true',
        help='Overwrite unit files if they already exist')

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.error("Please specify a command to run. "
                     "Use \"--help\" for more information.")

    is_verbose = args.verbose
    skip_isolate = args.skip_isolate
    target_path = find_target_path(args.dir)

    args.func(args)
