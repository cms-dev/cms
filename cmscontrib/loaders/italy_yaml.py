#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014-2018 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2015-2019 Luca Chiodini <luca@chiodini.org>
# Copyright © 2016 Andrea Cracco <guilucand@gmail.com>
# Copyright © 2018 Edoardo Morassutto <edoardo.morassutto@gmail.com>
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

import logging
import os
import os.path
import re
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from copy import deepcopy

import yaml

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE, \
    FEEDBACK_LEVEL_FULL, FEEDBACK_LEVEL_RESTRICTED, \
    FEEDBACK_LEVEL_OI_RESTRICTED
from cms.db import Contest, User, Task, Statement, Attachment, Team, Dataset, \
    Manager, Testcase, Generator, SubtaskValidator
from cms.db.modelsolution import validate_model_solution_name
from cms.grading.languagemanager import LANGUAGES, HEADER_EXTS, \
    SOURCE_EXTS, filename_to_language, get_language
from cms.grading.language import CompiledLanguage
from cms.grading.tasktypes.util import get_allowed_manager_basenames, compile_manager_bytes
from cmscommon.constants import \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK, SCORE_MODE_MAX_TOKENED_LAST
from cmscommon.crypto import build_password
from cmscommon.testcases import (
    compile_template_regex,
    pair_testcases_in_directory,
)
from cmscommon.zip import safe_extract_zip
from cmscontrib import touch
from .base_loader import ContestLoader, TaskLoader, UserLoader, TeamLoader, \
    LANGUAGE_MAP, LoaderValidationError


logger = logging.getLogger(__name__)


def find_first_existing_dir(base_path, folder_names):
    """Find the first existing directory from a list of alternatives.

    base_path: the base directory to search in.
    folder_names: list of folder names to try.

    return: the name of the first existing folder, or None if none exist.

    Raises a critical error if multiple folders exist.

    """
    found_folders = []
    found_paths = []

    for folder_name in folder_names:
        folder_path = os.path.join(base_path, folder_name)
        if os.path.isdir(folder_path):
            # Check if this is the same directory as any we've already found
            is_duplicate = False
            for existing_path in found_paths:
                try:
                    if os.path.samefile(folder_path, existing_path):
                        is_duplicate = True
                        break
                except (OSError, ValueError):
                    if os.path.realpath(folder_path) == os.path.realpath(existing_path):
                        is_duplicate = True
                        break

            if not is_duplicate:
                found_folders.append(folder_name)
                found_paths.append(folder_path)

    if len(found_folders) > 1:
        error_msg = ("Multiple alternative folders found: %s. "
                     "Please keep only one." % ", ".join(found_folders))
        logger.error(error_msg)
        raise LoaderValidationError(error_msg)

    return found_folders[0] if found_folders else None


def detect_testcase_sources(task_path):
    """Detect and validate testcase sources in a task directory.

    task_path: path to the task directory.

    return: tuple (source_type, source_path) where source_type is one of:
        'legacy' - legacy input/output folders
        'zip' - tests.zip or testcases.zip
        'folder' - tests or testcases folder
        None - no testcase source found

    Raises LoaderValidationError if multiple conflicting sources are found.
    """
    has_legacy = (os.path.exists(os.path.join(task_path, "input")) and
                  os.path.exists(os.path.join(task_path, "output")))

    zip_sources = []
    for zip_name in ["tests.zip", "testcases.zip"]:
        zip_path = os.path.join(task_path, zip_name)
        if os.path.exists(zip_path):
            zip_sources.append((zip_name, zip_path))

    folder_sources = []
    for folder_name in ["tests", "testcases"]:
        folder_path = os.path.join(task_path, folder_name)
        if os.path.isdir(folder_path):
            folder_sources.append((folder_name, folder_path))

    if len(zip_sources) > 1:
        error_msg = ("Multiple testcase zip files found: %s. Please keep only one." %
                     ", ".join([name for name, _ in zip_sources]))
        logger.error(error_msg)
        raise LoaderValidationError(error_msg)

    if len(folder_sources) > 1:
        error_msg = ("Multiple testcase folders found: %s. Please keep only one." %
                     ", ".join([name for name, _ in folder_sources]))
        logger.error(error_msg)
        raise LoaderValidationError(error_msg)

    if len(zip_sources) > 0 and len(folder_sources) > 0:
        error_msg = ("Both testcase zip (%s) and folder (%s) found. Please keep only one." %
                     (zip_sources[0][0], folder_sources[0][0]))
        logger.error(error_msg)
        raise LoaderValidationError(error_msg)

    if has_legacy:
        if zip_sources or folder_sources:
            new_source = zip_sources[0][0] if zip_sources else folder_sources[0][0]
            error_msg = ("Both legacy (input/output) and new-style testcase source (%s) found. "
                         "Please keep only one." % new_source)
            logger.error(error_msg)
            raise LoaderValidationError(error_msg)
        return ('legacy', task_path)
    elif zip_sources:
        return ('zip', zip_sources[0][1])
    elif folder_sources:
        return ('folder', folder_sources[0][1])
    else:
        return (None, None)


def compile_manager_source(file_cacher, source_path, source_filename,
                           compiled_filename, task_name, notify=None,
                           raise_on_error=False, language_name=None,
                           kind="Manager"):
    """Compile a manager or generator source file.

    file_cacher: FileCacher instance for storing files.
    source_path: path to the source file.
    source_filename: name of the source file.
    compiled_filename: name for the compiled binary.
    task_name: name of the task (for logging).
    notify: optional callback(title: str, text: str) to report errors.
    raise_on_error: if True, raise LoaderValidationError on compilation failure.
    language_name: optional explicit language name (e.g., "C++17 / g++").
        If provided, this language is used instead of auto-detection from
        the filename. This is useful for distinguishing between languages
        with the same file extension (e.g., PyPy vs CPython for .py files).
    kind: description prefix for file cacher (default: "Manager").
        Use "Generator" for generator files.

    return: tuple (source_digest, compiled_digest) or None if compilation fails
            (and raise_on_error is False).

    raise: LoaderValidationError if compilation fails and raise_on_error is True.

    """
    with open(source_path, 'rb') as f:
        source_body = f.read()

    error_message = []

    def capture_error(title, text):
        error_message.append("%s: %s" % (title, text))
        if notify:
            notify(title, text)

    success, compiled_bytes, _stats = compile_manager_bytes(
        file_cacher,
        source_filename,
        source_body,
        compiled_filename,
        sandbox_name="loader_compile",
        for_evaluation=True,
        notify=capture_error,
        language_name=language_name
    )

    if not success:
        if raise_on_error:
            msg = error_message[0] if error_message else (
                "Failed to compile %s. Make sure isolate sandbox is properly "
                "configured and accessible." % source_filename)
            raise LoaderValidationError(msg)
        return None

    source_digest = file_cacher.put_file_content(
        source_body, "%s source %s for task %s" % (kind, source_filename, task_name))
    compiled_digest = file_cacher.put_file_content(
        compiled_bytes, "Compiled %s %s for task %s" % (kind.lower(), compiled_filename, task_name))

    return (source_digest, compiled_digest)


def apply_checker_to_output_eval(evaluation_param, explicit_output_eval, exponent,
                                  managers_folder, checker_source_desc, notify):
    """Determine output_eval when a checker is discovered.

    When a checker is found, this function decides whether to use 'comparator'
    or respect an explicit output_eval setting from task.yaml.

    evaluation_param: current evaluation parameter value.
    explicit_output_eval: explicit output_eval from task.yaml, or None.
    exponent: exponent value if realprecision was configured, or None.
    managers_folder: name of the managers folder (for warning messages).
    checker_source_desc: description of how checker was found (for warnings).
    notify: callback(title, text) to report configuration conflicts.

    return: the new evaluation_param value to use.

    """
    if explicit_output_eval is not None:
        if explicit_output_eval != "comparator":
            msg = ("Checker %s but explicit output_eval '%s' specified in "
                   "task.yaml. Using explicit setting." %
                   (checker_source_desc, explicit_output_eval))
            logger.warning(msg)
            notify("Configuration conflict", msg)
        return evaluation_param

    if exponent is not None:
        logger.warning(
            "Both checker (from %s/) and exponent specified. "
            "Checker takes precedence, ignoring exponent parameter.",
            managers_folder)
    return "comparator"


# Patch PyYAML to make it load all strings as unicode instead of str
# (see http://stackoverflow.com/questions/2890146).
def construct_yaml_str(self, node):
    return self.construct_scalar(node)


yaml.Loader.add_constructor("tag:yaml.org,2002:str", construct_yaml_str)
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", construct_yaml_str)


def getmtime(fname):
    return os.stat(fname).st_mtime


yaml_cache = {}

def load_yaml_from_path(path):
    if path in yaml_cache:
        return yaml_cache[path]
    with open(path, "rt", encoding="utf-8") as f:
        value = yaml.safe_load(f)
    yaml_cache[path] = value
    return deepcopy(value)


def load(src, dst, src_name, dst_name=None, conv=lambda i: i):
    """Execute:
      dst[dst_name] = conv(src[src_name])
    with the following features:

      * If src_name is a list, it tries each of its element as
        src_name, stopping when the first one succedes.

      * If dst_name is None, it is set to src_name; if src_name is a
        list, dst_name is set to src_name[0] (_not_ the one that
        succedes).

      * By default conv is the identity function.

      * If dst is None, instead of assigning the result to
        dst[dst_name] (which would cast an exception) it just returns
        it.

      * If src[src_name] doesn't exist, the behavior is different
        depending on whether dst is None or not: if dst is None,
        conv(None) is returned; if dst is not None, nothing is done
        (in particular, dst[dst_name] is _not_ assigned to conv(None);
        it is not assigned to anything!).

    """
    if dst is not None and dst_name is None:
        if isinstance(src_name, list):
            dst_name = src_name[0]
        else:
            dst_name = src_name
    res = None
    found = False
    if isinstance(src_name, list):
        for this_src_name in src_name:
            try:
                res = src[this_src_name]
            except KeyError:
                pass
            else:
                found = True
                break
    else:
        if src_name in src:
            found = True
            res = src[src_name]
    if dst is not None:
        if found:
            dst[dst_name] = conv(res)
    else:
        return conv(res)


def parse_datetime(val):
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc)
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, timezone.utc)
    raise ValueError("Invalid datetime format.")


def make_timedelta(t):
    return timedelta(seconds=t)


def normalize_testcase_codename(codename: str) -> str:
    """Normalize a testcase codename as written by an admin in task.yaml.

    Purely numeric codenames refer to the legacy input%d.txt/output%d.txt
    numbering, whose codenames are zero-padded to three digits; all the other
    codenames (e.g. those coming from a testcase archive, like "7-01") are
    used verbatim.

    codename: the codename as written in task.yaml.

    return: the codename as stored in the dataset.

    """
    codename = codename.strip()
    try:
        return "%03d" % int(codename)
    except ValueError:
        return codename


def _convert_filename_to_codename(filename: str, submission_format: list[str]) -> str:
    """Convert a disk filename to its codename format for submission files.

    When model solutions are exported, filenames like "solution.%l" are expanded
    to actual extensions like "solution.cpp". During import, we need to convert
    them back to the codename format so that the submission files match the
    task's submission_format.

    filename: the disk filename (e.g., "solution.cpp")
    submission_format: the task's submission format (e.g., ["solution.%l"])

    return: the codename if a match is found (e.g., "solution.%l"),
            otherwise the original filename.

    """
    base, ext = os.path.splitext(filename)

    # First pass: try exact base matching
    for codename in submission_format:
        if codename.endswith(".%l"):
            # This is a language-dependent codename
            codename_base = codename[:-3]  # Remove .%l
            if base == codename_base and ext in SOURCE_EXTS:
                return codename
        else:
            # Fixed filename, must match exactly
            if filename == codename:
                return codename

    # Second pass: for single-file tasks with one %l codename, be lenient
    # This handles cases where the exported filename base doesn't match the
    # codename base (e.g., file "solution.cpp" but submission_format is
    # ["task_name.%l"]). If there's only one possible codename and the file
    # has a valid source extension, use that codename.
    if len(submission_format) == 1 and ext in SOURCE_EXTS:
        single_codename = submission_format[0]
        if single_codename.endswith(".%l"):
            return single_codename

    # No match found, return original filename
    return filename


class YamlLoader(ContestLoader, TaskLoader, UserLoader, TeamLoader):
    """Load a contest, task, user or team stored using the Italian IOI format.

    Given the filesystem location of a contest, task, user or team, stored
    using the Italian IOI format, parse those files and directories to produce
    data that can be consumed by CMS, i.e. the corresponding instances of the
    DB classes.

    """

    short_name = 'italy_yaml'
    description = 'Italian YAML-based format'

    def __init__(self, path, file_cacher):
        super().__init__(path, file_cacher)
        self._notifier = None

    def set_notifier(self, notify):
        """Set a notification callback for reporting errors to the admin UI.

        notify: callable(title: str, text: str) that adds a notification.

        """
        self._notifier = notify

    def _notify(self, title, text):
        """Internal helper to send notifications if a notifier is set.

        If no notifier is set, just logs the error instead.

        title: notification title.
        text: notification text.

        """
        if self._notifier:
            self._notifier(title, text)
        else:
            logger.error("%s: %s", title, text)

    @staticmethod
    def detect(path):
        """See docstring in class Loader."""
        # TODO - Not really refined...
        return os.path.exists(os.path.join(path, "contest.yaml")) or \
            os.path.exists(os.path.join(path, "task.yaml")) or \
            os.path.exists(os.path.join(os.path.dirname(path), "contest.yaml"))

    def get_task_loader(self, taskname):
        loader = YamlLoader(os.path.join(self.path, taskname), self.file_cacher)
        loader._notifier = self._notifier
        return loader

    def get_contest(self):
        """See docstring in class ContestLoader."""
        if not os.path.exists(os.path.join(self.path, "contest.yaml")):
            logger.critical("File missing: \"contest.yaml\"")
            return None

        conf = load_yaml_from_path(os.path.join(self.path, "contest.yaml"))

        # Here we update the time of the last import
        touch(os.path.join(self.path, ".itime_contest"))
        # If this file is not deleted, then the import failed
        touch(os.path.join(self.path, ".import_error_contest"))

        args = {}

        # Contest information
        load(conf, args, ["name", "nome_breve"])
        load(conf, args, ["description", "nome"])
        load(conf, args, "allowed_localizations")
        load(conf, args, "languages")
        load(conf, args, "submissions_download_allowed")
        load(conf, args, "allow_questions")
        load(conf, args, "allow_user_tests")
        load(conf, args, "score_precision")

        logger.info("Loading parameters for contest %s.", args["name"])

        # Logging in
        load(conf, args, "block_hidden_participations")
        load(conf, args, "allow_password_authentication")
        load(conf, args, "allow_registration")
        load(conf, args, "ip_restriction")
        load(conf, args, "ip_autologin")

        # Token parameters
        # Use the new token settings format if detected.
        if "token_mode" in conf:
            load(conf, args, "token_mode")
            load(conf, args, "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_interval", conv=make_timedelta)
            load(conf, args, "token_gen_max")
        # Otherwise fall back on the old one.
        else:
            logger.warning(
                "contest.yaml uses a deprecated format for token settings "
                "which will soon stop being supported, you're advised to "
                "update it.")
            # Determine the mode.
            if conf.get("token_initial", None) is None:
                args["token_mode"] = TOKEN_MODE_DISABLED
            elif conf.get("token_gen_number", 0) > 0 and \
                    conf.get("token_gen_time", 0) == 0:
                args["token_mode"] = TOKEN_MODE_INFINITE
            else:
                args["token_mode"] = TOKEN_MODE_FINITE
            # Set the old default values.
            args["token_gen_initial"] = 0
            args["token_gen_number"] = 0
            args["token_gen_interval"] = timedelta()
            # Copy the parameters to their new names.
            load(conf, args, "token_total", "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_initial", "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_time", "token_gen_interval",
                 conv=make_timedelta)
            load(conf, args, "token_max", "token_gen_max")
            # Remove some corner cases.
            if args["token_gen_initial"] is None:
                args["token_gen_initial"] = 0
            if args["token_gen_interval"].total_seconds() == 0:
                args["token_gen_interval"] = timedelta(minutes=1)

        # Times
        load(conf, args, ["start", "inizio"], conv=parse_datetime)
        load(conf, args, ["stop", "fine"], conv=parse_datetime)
        load(conf, args, ["timezone"])
        load(conf, args, ["per_user_time"], conv=make_timedelta)

        # Limits
        load(conf, args, "max_submission_number")
        load(conf, args, "max_user_test_number")
        load(conf, args, "min_submission_interval", conv=make_timedelta)
        load(conf, args, "min_user_test_interval", conv=make_timedelta)

        # Analysis mode
        load(conf, args, "analysis_enabled")
        load(conf, args, "analysis_start", conv=parse_datetime)
        load(conf, args, "analysis_stop", conv=parse_datetime)

        tasks: list[str] | None = load(conf, None, ["tasks", "problemi"])
        participations: list[dict] | None = load(conf, None, ["users", "utenti"])
        participations = [] if participations is None else participations
        for p in participations:
            p["password"] = build_password(p["password"])

        # Import was successful
        os.remove(os.path.join(self.path, ".import_error_contest"))

        logger.info("Contest parameters loaded.")

        return Contest(**args), tasks, participations

    def get_user(self):
        """See docstring in class UserLoader."""

        if not os.path.exists(os.path.join(os.path.dirname(self.path),
                                           "contest.yaml")):
            logger.critical("File missing: \"contest.yaml\"")
            return None

        username = os.path.basename(self.path)
        logger.info("Loading parameters for user %s.", username)

        conf = load_yaml_from_path(
            os.path.join(os.path.dirname(self.path), "contest.yaml"))

        args = {}

        conf = load(conf, None, ["users", "utenti"])

        for user in conf:
            if user["username"] == username:
                conf = user
                break
        else:
            logger.critical("The specified user cannot be found.")
            return None

        load(conf, args, "username")
        load(conf, args, "password", conv=build_password)

        load(conf, args, ["first_name", "nome"])
        load(conf, args, ["last_name", "cognome"])

        if "first_name" not in args:
            args["first_name"] = ""
        if "last_name" not in args:
            args["last_name"] = args["username"]

        logger.info("User parameters loaded.")

        return User(**args)

    def get_team(self):
        """See docstring in class TeamLoader."""

        if not os.path.exists(os.path.join(os.path.dirname(self.path),
                                           "contest.yaml")):
            logger.critical("File missing: \"contest.yaml\"")
            return None

        team_code = os.path.basename(self.path)
        logger.info("Loading parameters for team %s.", team_code)

        conf = load_yaml_from_path(
            os.path.join(os.path.dirname(self.path), "contest.yaml"))

        args = {}

        conf = load(conf, None, "teams")

        for team in conf:
            if team["code"] == team_code:
                conf = team
                break
        else:
            logger.critical("The specified team cannot be found.")
            return None

        load(conf, args, "code")
        load(conf, args, "name")

        logger.info("Team parameters loaded.")

        return Team(**args)

    def get_task(self, get_statement=True) -> Task | None:
        """See docstring in class TaskLoader."""
        name = os.path.split(self.path)[1]

        if (not os.path.exists(os.path.join(self.path, "task.yaml"))) and \
           (not os.path.exists(os.path.join(self.path, "..", name + ".yaml"))):
            logger.critical("File missing: \"task.yaml\"")
            return None

        # We first look for the yaml file inside the task folder,
        # and eventually fallback to a yaml file in its parent folder.
        try:
            conf = load_yaml_from_path(os.path.join(self.path, "task.yaml"))
        except OSError as err:
            try:
                deprecated_path = os.path.join(self.path, "..", name + ".yaml")
                conf = load_yaml_from_path(deprecated_path)

                logger.warning("You're using a deprecated location for the "
                               "task.yaml file. You're advised to move %s to "
                               "%s.", deprecated_path,
                               os.path.join(self.path, "task.yaml"))
            except OSError:
                # Since both task.yaml and the (deprecated) "../taskname.yaml"
                # are missing, we will only warn the user that task.yaml is
                # missing (to avoid encouraging the use of the deprecated one)
                raise err

        # Here we update the time of the last import
        touch(os.path.join(self.path, ".itime"))
        # If this file is not deleted, then the import failed
        touch(os.path.join(self.path, ".import_error"))

        args = {}

        load(conf, args, ["name", "nome_breve"])
        load(conf, args, ["title", "nome"])

        if name != args["name"]:
            logger.info("The task name (%s) and the directory name (%s) are "
                        "different. The former will be used.", args["name"],
                        name)

        if args["name"] == args["title"]:
            logger.warning("Short name equals long name (title). "
                           "Please check.")

        name = args["name"]

        logger.info("Loading parameters for task %s.", name)

        if get_statement:
            # The language of testo.pdf / statement.pdf, defaulting to 'he'
            primary_language = load(conf, None, "primary_language")
            if primary_language is None:
                primary_language = "he"

            statement = find_first_existing_dir(
                self.path,
                ["statement", "statements", "Statement", "Statements", "testo"])

            statement_dir = (os.path.join(self.path, statement)
                             if statement is not None else self.path)

            single_statement_path = None
            if statement is not None:
                candidate_statement = os.path.join(
                    statement_dir, "%s.pdf" % statement)
                if os.path.exists(candidate_statement):
                    single_statement_path = candidate_statement

            multi_statement_paths = {}
            for lang, lang_code in LANGUAGE_MAP.items():
                path = os.path.join(statement_dir, "%s.pdf" % lang)
                if os.path.exists(path):
                    multi_statement_paths[lang_code] = path

            if len(multi_statement_paths) > 0:
                # Ensure that either a statement.pdf or testo.pdf is specified,
                # or a list of <lang>.pdf files are specified, but not both,
                # unless statement.pdf or testo.pdf is a symlink, in which case
                # we let it slide.
                if single_statement_path is not None and not os.path.islink(
                    single_statement_path
                ):
                    logger.warning(
                        f"A statement (not a symlink!) is present at {single_statement_path} "
                        f"but {len(multi_statement_paths)} more multi-language statements "
                        "were found. This is likely an error. Proceeding with "
                        "importing the multi-language files only."
                    )
                statements_to_import = multi_statement_paths
            else:
                if single_statement_path is None:
                    pdf_files = [f for f in os.listdir(statement_dir)
                                if f.endswith('.pdf') and os.path.isfile(os.path.join(statement_dir, f))]

                    if len(pdf_files) == 1:
                        single_statement_path = os.path.join(statement_dir, pdf_files[0])
                        logger.info("Auto-detected single PDF file as statement: %s", pdf_files[0])

                    if statement is None and single_statement_path is None:
                        error_msg = "Statement folder not found."
                        logger.error(error_msg)
                        raise LoaderValidationError(error_msg)

                statements_to_import = {
                    primary_language: single_statement_path}

            if primary_language not in statements_to_import.keys() or statements_to_import[primary_language] is None:
                error_msg = "Couldn't find statement for primary language %s, aborting." % primary_language
                logger.error(error_msg)
                raise LoaderValidationError(error_msg)

            args["statements"] = dict()
            for lang_code, statement_path in statements_to_import.items():
                digest = self.file_cacher.put_file_from_path(
                    statement_path,
                    "Statement for task %s (lang: %s)" % (name, lang_code),
                )
                # Look for source file with same base name (.doc, .docx, .tex)
                source_digest = None
                source_extension = None
                if statement_path is not None:
                    base_path = statement_path[:-4]  # Remove .pdf extension
                    for ext in [".doc", ".docx", ".tex"]:
                        source_path = base_path + ext
                        if os.path.exists(source_path):
                            source_digest = self.file_cacher.put_file_from_path(
                                source_path,
                                "Statement source for task %s (lang: %s)" % (name, lang_code),
                            )
                            source_extension = ext
                            logger.info("Found source file for statement: %s", source_path)
                            break
                args["statements"][lang_code] = Statement(lang_code, digest, source_digest=source_digest,
                                                          source_extension=source_extension)

            args["primary_statements"] = [primary_language]

        # Import submission_format if specified, otherwise use default
        submission_format = conf.get("submission_format")
        if submission_format is not None:
            # Normalize to list if someone writes a scalar
            if isinstance(submission_format, str):
                args["submission_format"] = [submission_format]
            else:
                args["submission_format"] = submission_format
        else:
            args["submission_format"] = ["%s.%%l" % name]

        # Import the feedback level when explicitly set
        # (default behaviour is restricted)
        if conf.get("feedback_level", None) == FEEDBACK_LEVEL_FULL:
            args["feedback_level"] = FEEDBACK_LEVEL_FULL
        elif conf.get("feedback_level", None) == FEEDBACK_LEVEL_RESTRICTED:
            args["feedback_level"] = FEEDBACK_LEVEL_RESTRICTED
        elif conf.get("feedback_level", None) == FEEDBACK_LEVEL_OI_RESTRICTED:
            args["feedback_level"] = FEEDBACK_LEVEL_OI_RESTRICTED

        if conf.get("score_mode", None) == SCORE_MODE_MAX:
            args["score_mode"] = SCORE_MODE_MAX
        elif conf.get("score_mode", None) == SCORE_MODE_MAX_SUBTASK:
            args["score_mode"] = SCORE_MODE_MAX_SUBTASK
        elif conf.get("score_mode", None) == SCORE_MODE_MAX_TOKENED_LAST:
            args["score_mode"] = SCORE_MODE_MAX_TOKENED_LAST

        # Import allowed_languages if specified (for per-task language restrictions)
        load(conf, args, "allowed_languages")

        # Use the new token settings format if detected.
        if "token_mode" in conf:
            load(conf, args, "token_mode")
            load(conf, args, "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_interval", conv=make_timedelta)
            load(conf, args, "token_gen_max")
        # Otherwise fall back on the old one.
        else:
            logger.warning(
                "task.yaml uses a deprecated format for token settings which "
                "will soon stop being supported, you're advised to update it.")
            # Determine the mode.
            if conf.get("token_initial", None) is None:
                args["token_mode"] = TOKEN_MODE_DISABLED
            elif conf.get("token_gen_number", 0) > 0 and \
                    conf.get("token_gen_time", 0) == 0:
                args["token_mode"] = TOKEN_MODE_INFINITE
            else:
                args["token_mode"] = TOKEN_MODE_FINITE
            # Set the old default values.
            args["token_gen_initial"] = 0
            args["token_gen_number"] = 0
            args["token_gen_interval"] = timedelta()
            # Copy the parameters to their new names.
            load(conf, args, "token_total", "token_max_number")
            load(conf, args, "token_min_interval", conv=make_timedelta)
            load(conf, args, "token_initial", "token_gen_initial")
            load(conf, args, "token_gen_number")
            load(conf, args, "token_gen_time", "token_gen_interval",
                 conv=make_timedelta)
            load(conf, args, "token_max", "token_gen_max")
            # Remove some corner cases.
            if args["token_gen_initial"] is None:
                args["token_gen_initial"] = 0
            if args["token_gen_interval"].total_seconds() == 0:
                args["token_gen_interval"] = timedelta(minutes=1)

        load(conf, args, "max_submission_number")
        load(conf, args, "max_user_test_number")
        load(conf, args, "min_submission_interval", conv=make_timedelta)
        load(conf, args, "min_user_test_interval", conv=make_timedelta)

        # Attachments
        args["attachments"] = dict()
        attachments_folder = find_first_existing_dir(
            self.path, ["att", "attachements", "Attachements", "attachments", "Attachments"])
        if attachments_folder is not None:
            for filename in os.listdir(
                    os.path.join(self.path, attachments_folder)):
                digest = self.file_cacher.put_file_from_path(
                    os.path.join(self.path, attachments_folder, filename),
                    "Attachment %s for task %s" % (filename, name))
                args["attachments"][filename] = Attachment(filename, digest)

        # Score precision.
        load(conf, args, "score_precision")

        task = Task(**args)

        args = {}
        args["task"] = task
        args["description"] = conf.get("version", "Default")
        args["autojudge"] = False

        load(conf, args, ["time_limit", "timeout"], conv=float)
        # The Italian YAML format specifies memory limits in MiB.
        load(conf, args, ["memory_limit", "memlimit"],
             conv=lambda mb: mb * 1024 * 1024)

        # Builds the parameters that depend on the task type
        args["managers"] = []
        infile_param = conf.get("infile", "")
        outfile_param = conf.get("outfile", "")

        # Check if compilation and output_eval are explicitly specified in task.yaml
        # These take precedence over file-based detection
        explicit_compilation = conf.get("compilation")
        explicit_output_eval = conf.get("output_eval")

        # If there is sol/grader.%l for some language %l, then,
        # presuming that the task type is Batch, we retrieve graders
        # in the form sol/grader.%l
        graders = False
        for lang in LANGUAGES:
            if os.path.exists(os.path.join(
                    self.path, "sol", "grader%s" % lang.source_extension)):
                graders = True
                break
        if graders:
            # Read grader for each language
            for lang in LANGUAGES:
                extension = lang.source_extension
                grader_filename = os.path.join(
                    self.path, "sol", "grader%s" % extension)
                if os.path.exists(grader_filename):
                    digest = self.file_cacher.put_file_from_path(
                        grader_filename,
                        "Grader for task %s and language %s" %
                        (task.name, lang))
                    args["managers"] += [
                        Manager("grader%s" % extension, digest)]
                else:
                    logger.warning("Grader for language %s not found ", lang)
            # Read managers with other known file extensions
            for other_filename in os.listdir(os.path.join(self.path, "sol")):
                if any(other_filename.endswith(header)
                       for header in HEADER_EXTS):
                    digest = self.file_cacher.put_file_from_path(
                        os.path.join(self.path, "sol", other_filename),
                        "Manager %s for task %s" % (other_filename, task.name))
                    args["managers"] += [
                        Manager(other_filename, digest)]

        # Use explicit compilation parameter if specified, otherwise detect from files
        if explicit_compilation is not None:
            if explicit_compilation in ("alone", "grader", "stub"):
                compilation_param = explicit_compilation
            else:
                error_msg = ("Invalid compilation value '%s' (expected one of: "
                             "alone, grader, stub)" % explicit_compilation)
                logger.error(error_msg)
                raise LoaderValidationError(error_msg)
        else:
            compilation_param = "grader" if graders else "alone"

        # If there is check/checker (or equivalent), then, presuming
        # that the task type is Batch or OutputOnly, we retrieve the
        # comparator
        checker_found = False
        paths = [os.path.join(self.path, "check", "checker"),
                 os.path.join(self.path, "cor", "correttore")]
        for path in paths:
            if os.path.exists(path):
                digest = self.file_cacher.put_file_from_path(
                    path,
                    "Manager for task %s" % task.name)
                args["managers"] += [
                    Manager("checker", digest)]
                checker_found = True
                break

        # Use explicit output_eval parameter if specified, otherwise detect from files
        if explicit_output_eval is not None:
            if explicit_output_eval in ("diff", "comparator", "realprecision"):
                evaluation_param = explicit_output_eval
            else:
                error_msg = ("Invalid output_eval value '%s' (expected one of: "
                             "diff, comparator, realprecision)" % explicit_output_eval)
                logger.error(error_msg)
                raise LoaderValidationError(error_msg)
        else:
            evaluation_param = "comparator" if checker_found else "diff"

        exponent = load(conf, None, "exponent")
        if exponent is not None:
            try:
                exponent = int(exponent)
                if exponent < 0:
                    error_msg = (
                        "exponent must be a non-negative integer, got: %d" % exponent
                    )
                    logger.error(error_msg)
                    raise LoaderValidationError(error_msg)
            except (ValueError, TypeError) as e:
                error_msg = "exponent must be an integer, got: %s" % exponent
                logger.error(error_msg)
                raise LoaderValidationError(error_msg) from e

            if evaluation_param == "comparator":
                logger.warning(
                    "Both checker and exponent specified. Checker takes precedence, "
                    "ignoring exponent parameter.")
            else:
                evaluation_param = "realprecision"

        managers_folder = find_first_existing_dir(
            self.path, ["managers", "Managers"])
        if managers_folder is not None:
            managers_path = os.path.join(self.path, managers_folder)

            # Determine allowed compile basenames from task type
            task_type = conf.get("task_type")
            allowed_compile_basenames = get_allowed_manager_basenames(task_type)

            existing_manager_filenames = {m.filename for m in args["managers"]}

            # Pre-scan to detect source/compiled collisions
            # This ensures consistent behavior regardless of os.listdir order
            managers_files = [f for f in os.listdir(managers_path)
                              if os.path.isfile(os.path.join(managers_path, f))]
            sources_by_base = {}
            compiled_by_base = {}
            for filename in managers_files:
                base_noext, ext = os.path.splitext(filename)
                if base_noext not in allowed_compile_basenames:
                    continue
                if ext in SOURCE_EXTS:
                    sources_by_base.setdefault(base_noext, []).append(filename)
                else:
                    compiled_by_base.setdefault(base_noext, []).append(filename)

            # Basenames where both source and compiled exist - we'll compile from source
            collision_bases = {b for b in allowed_compile_basenames
                               if sources_by_base.get(b) and compiled_by_base.get(b)}
            notified_collision_bases = set()

            for filename in sorted(managers_files):  # Sort for deterministic order
                file_path = os.path.join(managers_path, filename)
                base_noext, ext = os.path.splitext(filename)

                # Check if this is a source file that should be compiled
                should_compile = (base_noext in allowed_compile_basenames and
                                  ext in SOURCE_EXTS)

                if should_compile:
                    result = compile_manager_source(
                        self.file_cacher, file_path, filename,
                        base_noext, task.name, notify=self._notify,
                        raise_on_error=(self._notifier is None))

                    if result is not None:
                        source_digest, compiled_digest = result

                        # Emit warning if we're compiling over an existing compiled file
                        if base_noext in collision_bases and base_noext not in notified_collision_bases:
                            msg = ("Both source (%s) and compiled (%s) manager found in %s/. "
                                   "Compiling from source and ignoring the existing compiled binary." %
                                   (filename, base_noext, managers_folder))
                            logger.warning(msg)
                            self._notify("Manager conflict", msg)
                            notified_collision_bases.add(base_noext)

                        if filename not in existing_manager_filenames:
                            args["managers"] += [Manager(filename, source_digest)]
                            existing_manager_filenames.add(filename)

                        if base_noext not in existing_manager_filenames:
                            args["managers"] += [Manager(base_noext, compiled_digest)]
                            existing_manager_filenames.add(base_noext)

                            if base_noext == "checker":
                                evaluation_param = apply_checker_to_output_eval(
                                    evaluation_param, explicit_output_eval, exponent,
                                    managers_folder,
                                    "compiled from %s/" % managers_folder,
                                    self._notify)
                    else:
                        logger.warning(
                            "Failed to compile %s from managers folder, skipping",
                            filename)
                else:
                    # Skip compiled files when source exists for same basename
                    if (base_noext in collision_bases and
                        base_noext in allowed_compile_basenames):
                        # This is a compiled file that will be replaced by compiled-from-source
                        continue

                    if filename not in existing_manager_filenames:
                        digest = self.file_cacher.put_file_from_path(
                            file_path,
                            "Manager %s for task %s" % (filename, task.name))
                        args["managers"] += [Manager(filename, digest)]
                        existing_manager_filenames.add(filename)

                        # Handle precompiled checker (no extension)
                        if filename == "checker":
                            evaluation_param = apply_checker_to_output_eval(
                                evaluation_param, explicit_output_eval, exponent,
                                managers_folder,
                                "precompiled in %s/" % managers_folder,
                                self._notify)

        # Override score_type if explicitly specified
        if "score_type" in conf and "score_type_parameters" in conf:
            logger.info("Overriding 'score_type' and 'score_type_parameters' "
                        "as per task.yaml")
            n_input = conf["n_input"] if "n_input" in conf else 0
            load(conf, args, "score_type")
            load(conf, args, "score_type_parameters")
        else:
            if "score_type" in conf or "score_type_parameters" in conf:
                logger.warning("To override score type data, task.yaml must "
                            "specify both 'score_type' and "
                            "'score_type_parameters'.")

            # Detect subtasks by checking GEN
            gen_filename = os.path.join(self.path, 'gen', 'GEN')
            try:
                with open(gen_filename, "rt", encoding="utf-8") as gen_file:
                    subtasks = []
                    testcases = 0
                    points = None
                    for line in gen_file:
                        line = line.strip()
                        splitted = line.split('#', 1)

                        if len(splitted) == 1:
                            # This line represents a testcase, otherwise
                            # it's just a blank
                            if splitted[0] != '':
                                testcases += 1

                        else:
                            testcase, comment = splitted
                            testcase = testcase.strip()
                            comment = comment.strip()
                            testcase_detected = len(testcase) > 0
                            copy_testcase_detected = comment.startswith("COPY:")
                            subtask_detected = comment.startswith('ST:')

                            flags = [testcase_detected,
                                    copy_testcase_detected,
                                    subtask_detected]
                            if len([x for x in flags if x]) > 1:
                                raise Exception("No testcase and command in"
                                                " the same line allowed")

                            # This line represents a testcase and contains a
                            # comment, but the comment doesn't start a new
                            # subtask
                            if testcase_detected or copy_testcase_detected:
                                testcases += 1

                            # This line starts a new subtask
                            if subtask_detected:
                                # Close the previous subtask
                                if points is None:
                                    assert testcases == 0
                                else:
                                    subtasks.append([points, testcases])
                                # Open the new one
                                testcases = 0
                                points = int(comment[3:].strip())

                    # Close last subtask (if no subtasks were defined, just
                    # fallback to Sum)
                    if points is None:
                        args["score_type"] = "Sum"
                        total_value = float(conf.get("total_value", 100.0))
                        input_value = 0.0
                        n_input = testcases
                        if n_input != 0:
                            input_value = total_value / n_input
                        args["score_type_parameters"] = input_value
                    else:
                        subtasks.append([points, testcases])
                        assert 100 == sum([int(st[0]) for st in subtasks])
                        n_input = sum([int(st[1]) for st in subtasks])
                        args["score_type"] = "GroupMin"
                        args["score_type_parameters"] = subtasks

                    if "n_input" in conf:
                        assert int(conf['n_input']) == n_input

            # If gen/GEN doesn't exist, just fallback to Sum
            except OSError:
                args["score_type"] = "Sum"
                total_value = float(conf.get("total_value", 100.0))
                input_value = 0.0
                n_input = load(conf, None, ["n_input", "n_test"])
                if n_input is None:
                    n_input = 0
                else:
                    n_input = int(n_input)
                if n_input != 0:
                    input_value = total_value / n_input
                args["score_type_parameters"] = input_value

        # Determine task type from config or legacy detection
        configured_type = conf.get("task_type")
        legacy_output_only = conf.get('output_only', False)

        # Track output codenames for BatchAndOutput tasks (set by setup_batch)
        output_codenames = None

        # Helper to set up OutputOnly task type
        def setup_output_only():
            args["task_type"] = "OutputOnly"
            args["time_limit"] = None
            args["memory_limit"] = None
            args["task_type_parameters"] = [evaluation_param]
            if evaluation_param == "realprecision":
                args["task_type_parameters"].append(exponent if exponent is not None else 6)
            task.submission_format = \
                ["output_%03d.txt" % i for i in range(n_input)]

        # Helper to set up Communication task type
        def setup_communication():
            num_processes = load(conf, None, "num_processes")
            if num_processes is None:
                num_processes = 1
            io_type = load(conf, None, "user_io")
            if io_type is not None:
                if io_type not in ["std_io", "fifo_io"]:
                    logger.warning("user_io incorrect. Valid options "
                                   "are 'std_io' and 'fifo_io'. "
                                   "Ignored.")
                    io_type = None
            logger.info("Task type Communication")
            args["task_type"] = "Communication"

            # Detect if stubs exist for file-based compilation detection
            stubs_found = False
            if os.path.isdir(os.path.join(self.path, "sol")):
                for lang in LANGUAGES:
                    stub_name = os.path.join(
                        self.path, "sol", "stub%s" % lang.source_extension
                    )
                    if os.path.exists(stub_name):
                        stubs_found = True
                        break

            # Determine compilation parameter: use explicit if specified, otherwise detect
            if explicit_compilation is not None:
                if explicit_compilation in ("alone", "stub"):
                    comm_compilation = explicit_compilation
                else:
                    error_msg = ("Invalid compilation value '%s' for Communication task "
                                 "(expected one of: alone, stub)" % explicit_compilation)
                    logger.error(error_msg)
                    raise LoaderValidationError(error_msg)
            else:
                comm_compilation = "stub" if stubs_found else "alone"

            # Determine default io_type based on compilation
            default_io = "fifo_io" if comm_compilation == "stub" else "std_io"
            args["task_type_parameters"] = [
                num_processes,
                comm_compilation,
                io_type or default_io,
            ]

            # Look for manager in legacy locations or managers folder
            manager_found = False
            paths = [
                os.path.join(self.path, "check", "manager"),
                os.path.join(self.path, "cor", "manager"),
            ]
            for path in paths:
                if os.path.exists(path):
                    digest = self.file_cacher.put_file_from_path(
                        path, "Manager for task %s" % task.name
                    )
                    args["managers"] += [Manager("manager", digest)]
                    manager_found = True
                    break

            # Check managers folder if not found in legacy locations
            if not manager_found and managers_folder is not None:
                manager_path = os.path.join(self.path, managers_folder, "manager")
                if os.path.exists(manager_path):
                    digest = self.file_cacher.put_file_from_path(
                        manager_path, "Manager for task %s" % task.name
                    )
                    args["managers"] += [Manager("manager", digest)]
                    manager_found = True

            if not manager_found:
                logger.warning("Communication task but no manager found")

            # Load stubs and headers
            if os.path.isdir(os.path.join(self.path, "sol")):
                for lang in LANGUAGES:
                    stub_name = os.path.join(
                        self.path, "sol", "stub%s" % lang.source_extension
                    )
                    if os.path.exists(stub_name):
                        digest = self.file_cacher.put_file_from_path(
                            stub_name,
                            "Stub for task %s and language %s" % (task.name, lang.name),
                        )
                        args["managers"] += [
                            Manager("stub%s" % lang.source_extension, digest)
                        ]
                    elif comm_compilation == "stub":
                        logger.warning("Stub for language %s not found.", lang.name)
                for other_filename in os.listdir(os.path.join(self.path, "sol")):
                    if any(other_filename.endswith(header) for header in HEADER_EXTS):
                        digest = self.file_cacher.put_file_from_path(
                            os.path.join(self.path, "sol", other_filename),
                            "Stub %s for task %s" % (other_filename, task.name),
                        )
                        args["managers"] += [Manager(other_filename, digest)]

        # Helper to set up TwoSteps task type
        def setup_twosteps():
            logger.info("Task type TwoSteps")
            args["task_type"] = "TwoSteps"
            args["task_type_parameters"] = [evaluation_param]

        # Helper to set up Batch/BatchAndOutput task type
        def setup_batch():
            nonlocal output_codenames
            args["task_type"] = "Batch"
            args["task_type_parameters"] = [
                compilation_param,
                [infile_param, outfile_param],
                evaluation_param,
            ]

            args["task_type_parameters"].append(
                exponent if exponent is not None else 6
            )

            output_only_testcases = load(
                conf,
                None,
                "output_only_testcases",
                conv=lambda x: "" if x is None else x,
            )
            output_optional_testcases = load(
                conf,
                None,
                "output_optional_testcases",
                conv=lambda x: "" if x is None else x,
            )
            if len(output_only_testcases) > 0 or len(output_optional_testcases) > 0:
                args["task_type"] = "BatchAndOutput"
                output_only_codenames = set()
                if len(output_only_testcases) > 0:
                    output_only_codenames = {
                        normalize_testcase_codename(x)
                        for x in output_only_testcases.split(",")
                    }
                    args["task_type_parameters"].append(",".join(output_only_codenames))
                else:
                    args["task_type_parameters"].append("")
                output_codenames = set()
                if len(output_optional_testcases) > 0:
                    output_codenames = {
                        normalize_testcase_codename(x)
                        for x in output_optional_testcases.split(",")
                    }
                output_codenames.update(output_only_codenames)
                task.submission_format.extend(
                    filename
                    for filename in ("output_%s.txt" % s
                                     for s in sorted(output_codenames))
                    if filename not in task.submission_format
                )
            # If task_type is explicitly BatchAndOutput but no output_only_testcases specified
            elif configured_type == "BatchAndOutput":
                args["task_type"] = "BatchAndOutput"
                args["task_type_parameters"].append("")  # Empty output_only_testcases

        # Task type selection: use configured_type if present, otherwise use legacy detection
        if configured_type == "OutputOnly":
            setup_output_only()
        elif configured_type == "Communication":
            setup_communication()
        elif configured_type == "TwoSteps":
            setup_twosteps()
        elif configured_type in ("Batch", "BatchAndOutput"):
            setup_batch()
        elif configured_type is None:
            # Legacy detection: check output_only flag first
            if legacy_output_only:
                setup_output_only()
            else:
                # Check for Communication task via manager file presence
                paths = [
                    os.path.join(self.path, "check", "manager"),
                    os.path.join(self.path, "cor", "manager"),
                ]
                is_communication = any(os.path.exists(path) for path in paths)
                if is_communication:
                    setup_communication()
                else:
                    # Default to Batch/BatchAndOutput
                    setup_batch()
        else:
            # Unknown task_type - raise error
            error_msg = (
                "Unknown task_type '%s' (expected one of: "
                "Batch, BatchAndOutput, OutputOnly, Communication, TwoSteps)"
                % configured_type
            )
            logger.error(error_msg)
            raise LoaderValidationError(error_msg)

        args["testcases"] = []
        testcases_temp_dir = None

        source_type, source_path = detect_testcase_sources(self.path)

        if source_type == "legacy":
            # Legacy input/output folders
            for i in range(n_input):
                input_digest = self.file_cacher.put_file_from_path(
                    os.path.join(self.path, "input", "input%d.txt" % i),
                    "Input %d for task %s" % (i, task.name),
                )
                output_digest = self.file_cacher.put_file_from_path(
                    os.path.join(self.path, "output", "output%d.txt" % i),
                    "Output %d for task %s" % (i, task.name),
                )
                test_codename = "%03d" % i
                args["testcases"] += [
                    Testcase(test_codename, True, input_digest, output_digest)
                ]
                if args["task_type"] == "OutputOnly":
                    task.attachments.set(
                        Attachment("input_%s.txt" % test_codename, input_digest)
                    )
                elif args["task_type"] == "BatchAndOutput":
                    if (
                        output_codenames is not None
                        and test_codename in output_codenames
                    ):
                        task.attachments.set(
                            Attachment("input_%s.txt" % test_codename, input_digest)
                        )
        elif source_type in ("zip", "folder"):
            testcases_temp_dir = None

            try:
                if source_type == "zip":
                    testcases_temp_dir = tempfile.mkdtemp(prefix="cms_testcases_")
                    with zipfile.ZipFile(source_path, "r") as zip_ref:
                        safe_extract_zip(zip_ref, testcases_temp_dir)

                    contents = os.listdir(testcases_temp_dir)
                    if len(contents) == 1 and os.path.isdir(
                        os.path.join(testcases_temp_dir, contents[0])
                    ):
                        testcases_dir = os.path.join(testcases_temp_dir, contents[0])
                    else:
                        testcases_dir = testcases_temp_dir
                    logger.info(
                        "Extracted testcases from %s", os.path.basename(source_path)
                    )
                else:
                    testcases_dir = source_path

                input_template = load(conf, None, "input_template")
                if input_template is None:
                    input_template = "input.*"
                output_template = load(conf, None, "output_template")
                if output_template is None:
                    output_template = "output.*"

                try:
                    input_re = compile_template_regex(input_template)
                    output_re = compile_template_regex(output_template)
                    paired_testcases = pair_testcases_in_directory(
                        testcases_dir, input_re, output_re
                    )
                except ValueError as e:
                    error_msg = str(e)
                    logger.error(error_msg)
                    raise LoaderValidationError(error_msg) from e

                if n_input == 0 and not os.path.exists(
                    os.path.join(self.path, "gen", "GEN")
                ):
                    n_input = len(paired_testcases)
                    logger.info("Discovered %d testcases from templates", n_input)

                if len(paired_testcases) != n_input:
                    error_msg = (
                        "Testcase count mismatch: found %d testcases but expected %d"
                        % (len(paired_testcases), n_input)
                    )
                    logger.error(error_msg)
                    raise LoaderValidationError(error_msg)

                # Load testcases
                for codename, (input_path, output_path) in paired_testcases.items():
                    input_digest = self.file_cacher.put_file_from_path(
                        input_path, "Input %s for task %s" % (codename, task.name)
                    )
                    output_digest = self.file_cacher.put_file_from_path(
                        output_path, "Output %s for task %s" % (codename, task.name)
                    )
                    args["testcases"] += [
                        Testcase(codename, True, input_digest, output_digest)
                    ]
                    if args["task_type"] == "OutputOnly":
                        task.attachments.set(
                            Attachment("input_%s.txt" % codename, input_digest)
                        )
                    elif args["task_type"] == "BatchAndOutput":
                        if (
                            output_codenames is not None
                            and codename in output_codenames
                        ):
                            task.attachments.set(
                                Attachment("input_%s.txt" % codename, input_digest)
                            )
            finally:
                if testcases_temp_dir:
                    import shutil

                    shutil.rmtree(testcases_temp_dir, ignore_errors=True)
        else:
            # No testcase source found - check if this is a generator-based task
            generators_yaml = conf.get("generators", []) or []
            generators_folder = find_first_existing_dir(
                self.path, ["generators", "Generators", "generator", "Generator"]
            )
            has_generators = bool(generators_yaml) or generators_folder is not None

            if has_generators:
                # Generator-based task: allow zero testcases, they will be generated later
                logger.warning(
                    "No testcases found for task %s, but generators are present; "
                    "importing dataset with zero testcases (expected to be generated later)",
                    task.name,
                )
            elif n_input and n_input > 0:
                # n_input is explicitly set but no testcases or generators found - this is an error
                error_msg = (
                    "No testcases found, but n_input=%d in config. "
                    "Expected input/output folders or tests/testcases folder/zip."
                    % n_input
                )
                logger.error(error_msg)
                raise LoaderValidationError(error_msg)
            else:
                # Allow tasks with no testcases (n_input is 0 or not set)
                logger.warning(
                    "No testcases found for task %s; importing dataset with zero testcases",
                    task.name,
                )
            # args["testcases"] was initialized to [] above, just fall through

        public_testcases = load(
            conf,
            None,
            ["public_testcases", "risultati"],
            conv=lambda x: "" if x is None else x,
        )
        if public_testcases == "all":
            for t in args["testcases"]:
                t.public = True
        elif len(public_testcases) > 0:
            for t in args["testcases"]:
                t.public = False

            # Parse tokens - support both codenames (new) and indices (legacy)
            tokens = [tok.strip() for tok in public_testcases.split(",") if tok.strip()]
            # Build codename lookup while testcases is still a list
            tc_by_codename = {tc.codename: tc for tc in args["testcases"]}

            for tok in tokens:
                # First try to match by codename
                tc = tc_by_codename.get(tok)
                if tc is not None:
                    tc.public = True
                    continue

                # Fallback: try to interpret as index (for legacy configs)
                try:
                    idx = int(tok)
                except ValueError:
                    logger.warning("Invalid public_testcases token '%s', ignoring", tok)
                    continue

                if 0 <= idx < len(args["testcases"]):
                    args["testcases"][idx].public = True
                else:
                    logger.warning("public_testcases index %s out of range", tok)

        args["testcases"] = dict((tc.codename, tc) for tc in args["testcases"])
        args["managers"] = dict((mg.filename, mg) for mg in args["managers"])

        dataset = Dataset(**args)
        task.active_dataset = dataset

        # Parse model solutions from task.yaml if present
        # Store the data on the dataset for later processing by the importer
        model_solutions_data = self._parse_model_solutions(conf, task.name)
        if model_solutions_data:
            # Store as a temporary attribute for the importer to process
            dataset._model_solutions_import_data = model_solutions_data

        # Parse generators from task.yaml and generators/ folder if present
        # Attach directly to dataset (similar to managers and testcases)
        generators = self._parse_generators(conf, task.name)
        for filename, generator in generators.items():
            generator.dataset = dataset
            dataset.generators[filename] = generator

        # Parse subtask validators from task.yaml and validators/ folder if present
        # Attach directly to dataset (similar to generators)
        validators = self._parse_validators(conf, task.name)
        for subtask_index, validator in validators.items():
            validator.dataset = dataset
            dataset.subtask_validators[subtask_index] = validator

        # Import was successful
        os.remove(os.path.join(self.path, ".import_error"))

        logger.info("Task parameters loaded.")

        return task

    def _parse_model_solutions(self, conf, task_name):
        """Parse model solutions from task.yaml and solutions/ folder.

        conf: the task configuration dictionary.
        task_name: name of the task (for logging).

        return: list of model solution data dicts, each containing:
            - name: solution name (identifier)
            - description: human-readable description
            - language: programming language (optional)
            - files: dict of codename -> digest
            - expected_score_min: minimum expected score (optional)
            - expected_score_max: maximum expected score (optional)
            - subtask_expected_scores: dict of subtask scores (optional)
            - has_metadata: True if metadata was found in task.yaml

        Supports two import formats (can be mixed for single-file tasks):
        1. Subdirectory format: solutions/{name}/ contains all files
        2. Flat file format (single-file tasks only): solutions/ contains
           source files directly, filename (without extension) becomes name
        """
        # Get submission_format, using the same default as get_task()
        submission_format = conf.get("submission_format")
        if submission_format is None:
            # Default to task_name.%l if not specified
            submission_format = ["%s.%%l" % task_name]
        elif isinstance(submission_format, str):
            # Normalize scalar to list
            submission_format = [submission_format]
        is_single_file_task = len(submission_format) == 1

        # Find solutions directory (supports alternative names)
        solutions_folder = find_first_existing_dir(
            self.path, ["solutions", "Solutions", "solution", "Solution"]
        )
        solutions_dir = (
            os.path.join(self.path, solutions_folder)
            if solutions_folder is not None
            else None
        )

        model_solutions_yaml = conf.get("model_solutions", []) or []

        if not model_solutions_yaml and not solutions_dir:
            return []

        # Phase 1: Discover all model solutions from filesystem
        fs_solutions = self._discover_model_solutions_from_fs(
            solutions_dir, submission_format, is_single_file_task, task_name
        )

        # Phase 2: Parse YAML metadata
        yaml_meta_by_name = {}
        for sol_conf in model_solutions_yaml:
            name = sol_conf.get("name")
            if not name:
                logger.warning("Model solution missing 'name' field, skipping")
                continue
            yaml_meta_by_name[name] = {
                "description": sol_conf.get("description", ""),
                "language": sol_conf.get("language"),
                "expected_score_min": sol_conf.get("expected_score_min"),
                "expected_score_max": sol_conf.get("expected_score_max"),
                "subtask_expected_scores": sol_conf.get("subtask_expected_scores"),
            }

        # Phase 3: Merge filesystem discoveries with YAML metadata
        result = []
        for name in sorted(fs_solutions.keys()):
            fs_info = fs_solutions[name]
            meta = yaml_meta_by_name.get(name)

            if not fs_info["files"]:
                logger.warning(
                    "Model solution '%s' has no files in solutions folder", name
                )
                continue

            # Use YAML metadata if available, otherwise use defaults
            sol_data = {
                "name": name,
                "description": meta["description"] if meta else "",
                "language": (
                    meta.get("language")
                    if meta and meta.get("language")
                    else fs_info["language"]
                ),
                "subtask_expected_scores": (
                    meta.get("subtask_expected_scores") if meta else None
                ),
                "files": fs_info["files"],
                "has_metadata": meta is not None,
            }
            if meta:
                sol_data["expected_score_min"] = meta.get("expected_score_min")
                sol_data["expected_score_max"] = meta.get("expected_score_max")

            result.append(sol_data)

        # Warn about YAML entries with no matching filesystem solution
        for name in yaml_meta_by_name:
            if name not in fs_solutions:
                logger.warning(
                    "Model solution '%s' is defined in task.yaml but has no "
                    "files in solutions folder",
                    name,
                )

        if result:
            logger.info("Found %d model solution(s) to import", len(result))

        return result

    def _parse_generators(self, conf, task_name):
        """Parse generators from task.yaml and generators/ folder.

        conf: the task configuration dictionary.
        task_name: name of the task (for logging).

        return: dict mapping filename to Generator objects, ready to be
            attached to dataset.generators.

        Generators are discovered from the generators/ folder (or variants like
        Generators/, generator/, Generator/). Template metadata can be specified
        in task.yaml under the 'generators' key. If no metadata is provided,
        the task's input_template/output_template from config are used as defaults,
        falling back to "input.*" and "output.*" if those are also not set.

        Generators are compiled using compile_manager_bytes, similar to how
        managers are compiled. If compilation fails, the generator is skipped.
        """
        # Load global defaults for generator templates from config
        # These are the same templates used for testcase discovery
        base_input_template = load(conf, None, "input_template")
        if base_input_template is None:
            base_input_template = "input.*"
        base_output_template = load(conf, None, "output_template")
        if base_output_template is None:
            base_output_template = "output.*"

        # Find generators directory (supports alternative names)
        generators_folder = find_first_existing_dir(
            self.path, ["generators", "Generators", "generator", "Generator"]
        )
        generators_dir = (
            os.path.join(self.path, generators_folder)
            if generators_folder is not None
            else None
        )

        generators_yaml = conf.get("generators", []) or []

        if not generators_yaml and not generators_dir:
            return {}

        # Build a lookup from filename to YAML metadata
        yaml_meta_by_filename = {}
        for gen_conf in generators_yaml:
            filename = gen_conf.get("filename")
            if not filename:
                logger.warning("Generator entry missing 'filename' field, skipping")
                continue
            yaml_meta_by_filename[filename] = {
                "input_template": gen_conf.get("input_template", base_input_template),
                "output_template": gen_conf.get(
                    "output_template", base_output_template
                ),
                "language": gen_conf.get("language"),
            }

        result = {}

        # Discover generators from filesystem
        if generators_dir and os.path.isdir(generators_dir):
            for filename in sorted(os.listdir(generators_dir)):
                file_path = os.path.join(generators_dir, filename)
                if not os.path.isfile(file_path):
                    continue

                # Check if it's a source file
                _, ext = os.path.splitext(filename)
                if ext not in SOURCE_EXTS:
                    logger.warning(
                        "Skipping non-source file '%s' in generators folder", filename
                    )
                    continue

                # Get language from YAML metadata if available, otherwise auto-detect
                meta = yaml_meta_by_filename.get(filename)
                yaml_language_name = meta.get("language") if meta else None

                if yaml_language_name:
                    # Use explicit language from YAML
                    try:
                        language = get_language(yaml_language_name)
                    except KeyError:
                        logger.warning(
                            "Unknown language '%s' for generator '%s', "
                            "falling back to auto-detection",
                            yaml_language_name,
                            filename,
                        )
                        language = filename_to_language(filename)
                else:
                    # Auto-detect language from filename
                    language = filename_to_language(filename)

                if language is None:
                    logger.warning(
                        "Could not detect language for generator '%s', skipping",
                        filename,
                    )
                    continue

                if not isinstance(language, CompiledLanguage):
                    logger.warning(
                        "Generator '%s' must be a compiled language, not '%s', "
                        "skipping",
                        filename,
                        language.name,
                    )
                    continue

                # Compile the generator using compile_manager_source
                compiled_filename = "generator"

                result_digests = compile_manager_source(
                    self.file_cacher,
                    file_path,
                    filename,
                    compiled_filename,
                    task_name,
                    notify=self._notify,
                    raise_on_error=False,
                    language_name=language.name,
                    kind="Generator",
                )

                if result_digests is None:
                    logger.warning("Failed to compile generator '%s'", filename)
                    continue

                source_digest, executable_digest = result_digests

                # Get templates from YAML metadata or use config defaults
                # (meta was already fetched above for language detection)
                input_template = meta["input_template"] if meta else base_input_template
                output_template = (
                    meta["output_template"] if meta else base_output_template
                )

                # Create Generator object directly
                generator = Generator(
                    filename=filename,
                    digest=source_digest,
                    executable_digest=executable_digest,
                    input_filename_template=input_template,
                    output_filename_template=output_template,
                    language_name=language.name,
                )
                result[filename] = generator

        # Warn about YAML entries with no matching filesystem file
        if generators_dir and os.path.isdir(generators_dir):
            fs_files = set(os.listdir(generators_dir))
            for filename in yaml_meta_by_filename:
                if filename not in fs_files:
                    logger.warning(
                        "Generator '%s' is defined in task.yaml but not found "
                        "in generators folder",
                        filename,
                    )

        if result:
            logger.info("Found %d generator(s) to import", len(result))

        return result

    def _parse_validators(self, conf, task_name):
        """Parse subtask validators from task.yaml and validators/ folder.

        conf: the task configuration dictionary.
        task_name: name of the task (for logging).

        return: dict mapping subtask_index to SubtaskValidator objects, ready to be
            attached to dataset.subtask_validators.

        Validators are discovered from the validators/ folder (or variants like
        Validators/, validator/, Validator/). Metadata can be specified
        in task.yaml under the 'validators' key, which should contain a list
        of objects with 'filename' and 'subtask_index' fields.

        If no metadata is provided in task.yaml, the subtask index is inferred
        from the filename. The filename should contain a number that represents
        the subtask index (0-indexed). For example:
        - "validator_0.cpp" -> subtask 0
        - "subtask1_validator.cpp" -> subtask 1
        - "val2.cpp" -> subtask 2

        Validators are compiled using compile_manager_bytes, similar to how
        generators are compiled. If compilation fails, the validator is skipped.
        """
        # Find validators directory (supports alternative names)
        validators_folder = find_first_existing_dir(
            self.path, ["validators", "Validators", "validator", "Validator"]
        )
        validators_dir = (
            os.path.join(self.path, validators_folder)
            if validators_folder is not None
            else None
        )

        validators_yaml = conf.get("validators", []) or []

        if not validators_yaml and not validators_dir:
            return {}

        # Build a lookup from filename to YAML metadata
        yaml_meta_by_filename = {}
        for val_conf in validators_yaml:
            filename = val_conf.get("filename")
            if not filename:
                logger.warning("Validator entry missing 'filename' field, skipping")
                continue
            subtask_index = val_conf.get("subtask_index")
            if subtask_index is None:
                logger.warning(
                    "Validator entry for '%s' missing 'subtask_index' field, skipping",
                    filename,
                )
                continue
            # Validate subtask_index is a non-negative integer
            try:
                subtask_index = int(subtask_index)
                if subtask_index < 0:
                    raise ValueError("subtask_index must be non-negative")
            except (ValueError, TypeError) as e:
                logger.warning(
                    "Validator entry for '%s' has invalid subtask_index '%s': %s, skipping",
                    filename, val_conf.get("subtask_index"), e,
                )
                continue
            yaml_meta_by_filename[filename] = {
                "subtask_index": subtask_index,
            }

        result = {}
        # If validators are declared in YAML but no directory found, log warning and continue
        if validators_yaml and not validators_dir:
            logger.warning(
                "Validators are declared in task.yaml but no validators folder was found; "
                "Looked for: validators/, Validators/, validator/, Validator/;"
                "skipping validators import"
            )

        # Discover validators from filesystem
        if validators_dir and os.path.isdir(validators_dir):
            for filename in sorted(os.listdir(validators_dir)):
                file_path = os.path.join(validators_dir, filename)
                if not os.path.isfile(file_path):
                    continue

                # Check if it's a source file
                _, ext = os.path.splitext(filename)
                if ext not in SOURCE_EXTS:
                    logger.warning(
                        "Skipping non-source file '%s' in validators folder", filename
                    )
                    continue

                language = filename_to_language(filename)
                if language is None:
                    logger.warning(
                        "Could not detect language for validator '%s', skipping",
                        filename)
                    continue

                if not isinstance(language, CompiledLanguage):
                    logger.warning(
                        "Validator '%s' must be a compiled language, not '%s', "
                        "skipping", filename, language.name)
                    continue

                # Get subtask index from YAML metadata or infer from filename
                meta = yaml_meta_by_filename.get(filename)
                if meta:
                    subtask_index = meta["subtask_index"]
                else:
                    # Try to infer subtask index from filename
                    subtask_index = self._infer_subtask_index_from_filename(filename)
                    if subtask_index is None:
                        logger.warning(
                            "Could not determine subtask index for validator '%s'. "
                            "Please specify it in task.yaml or use a filename with "
                            "a number (e.g., validator_0.cpp)", filename)
                        continue

                # Check for duplicate subtask index
                if subtask_index in result:
                    logger.warning(
                        "Duplicate validator for subtask %d: '%s' conflicts with '%s', "
                        "skipping", subtask_index, filename,
                        result[subtask_index].filename)
                    continue

                # Compile the validator using compile_manager_source helper
                compile_result = compile_manager_source(
                    self.file_cacher,
                    file_path,
                    filename,
                    "validator",
                    task_name,
                    notify=self._notify,
                    raise_on_error=False,
                    kind="Validator"
                )

                if compile_result is None:
                    logger.warning(
                        "Failed to compile validator '%s'", filename)
                    continue

                source_digest, executable_digest = compile_result

                # Create SubtaskValidator object directly
                validator = SubtaskValidator(
                    subtask_index=subtask_index,
                    filename=filename,
                    digest=source_digest,
                    executable_digest=executable_digest,
                )
                result[subtask_index] = validator

        # Warn about YAML entries with no matching filesystem file
        if validators_dir and os.path.isdir(validators_dir):
            fs_files = set(os.listdir(validators_dir))
            for filename in yaml_meta_by_filename:
                if filename not in fs_files:
                    logger.warning(
                        "Validator '%s' is defined in task.yaml but not found "
                        "in validators folder", filename)

        if result:
            logger.info("Found %d validator(s) to import", len(result))

        return result

    def _infer_subtask_index_from_filename(self, filename):
        """Try to infer subtask index from a validator filename.

        filename: the validator filename (e.g., "validator_0.cpp")

        return: the subtask index (int) or None if it cannot be inferred.

        Looks for numbers in the filename and uses the first one found.
        Examples:
        - "validator_0.cpp" -> 0
        - "subtask1_validator.cpp" -> 1
        - "val2.cpp" -> 2
        - "validator.cpp" -> None (no number found)
        """
        # Remove extension
        base, _ = os.path.splitext(filename)

        # Find all numbers in the filename
        numbers = re.findall(r'\d+', base)
        if numbers:
            return int(numbers[0])
        return None

    def _discover_model_solutions_from_fs(
            self, solutions_dir, submission_format, is_single_file_task, task_name):
        """Discover model solutions from the filesystem.

        Scans the solutions directory for both subdirectories (always valid)
        and flat source files (only valid for single-file tasks).

        solutions_dir: path to the solutions directory (or None if not found).
        submission_format: the task's submission format list.
        is_single_file_task: True if the task has only one submission file.
        task_name: name of the task (for logging).

        return: dict mapping solution name to {"files": {codename: digest},
                "language": detected_language_or_None}

        """
        solutions = {}  # name -> {"files": {}, "language": None}

        if not solutions_dir or not os.path.isdir(solutions_dir):
            return solutions

        for entry in sorted(os.listdir(solutions_dir)):
            path = os.path.join(solutions_dir, entry)

            if os.path.isdir(path):
                # Subdirectory represents a model solution
                name = entry
                if not self._is_valid_solution_name(name):
                    continue
                files, lang = self._load_solution_files_from_dir(
                    name, path, submission_format, task_name)
                if files:
                    self._merge_solution_entry(solutions, name, files, lang)
                else:
                    logger.warning(
                        "Model solution directory '%s' is empty, skipping", name)

            elif os.path.isfile(path):
                # Flat file: only allowed for single-file tasks
                if not is_single_file_task:
                    continue

                # Only accept source files (ignore README, etc.)
                if filename_to_language(entry) is None:
                    continue

                base, _ext = os.path.splitext(entry)
                if not self._is_valid_solution_name(base):
                    continue

                files, lang = self._load_solution_file(
                    base, path, entry, submission_format, task_name)
                self._merge_solution_entry(solutions, base, files, lang)

        return solutions

    def _is_valid_solution_name(self, name):
        """Check if a solution name is valid.

        Uses validate_model_solution_name from cms.db.modelsolution for
        consistency with the admin UI validation.

        name: the solution name to validate.

        return: True if valid, False otherwise (logs a warning).

        """
        try:
            validate_model_solution_name(name)
        except ValueError as e:
            logger.warning(
                "Skipping model solution '%s': %s", name, e)
            return False
        else:
            return True

    def _load_solution_files_from_dir(
            self, name, dir_path, submission_format, task_name):
        """Load all files from a model solution subdirectory.

        name: the solution name.
        dir_path: path to the solution subdirectory.
        submission_format: the task's submission format list.
        task_name: name of the task (for logging).

        return: tuple (files_dict, detected_language) where files_dict maps
                codename to digest, and detected_language is the first
                detected language or None.

        """
        files = {}
        language = None

        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            if not os.path.isfile(file_path):
                continue

            digest = self.file_cacher.put_file_from_path(
                file_path,
                "Model solution %s file %s for task %s" %
                (name, filename, task_name))

            # Convert disk filename to codename format
            codename = _convert_filename_to_codename(filename, submission_format)
            files[codename] = digest

            # Detect language from original filename if not yet set
            if language is None:
                detected = filename_to_language(filename)
                if detected is not None:
                    language = detected.name

        return files, language

    def _load_solution_file(
            self, base, file_path, filename, submission_format, task_name):
        """Load a single flat file as a model solution.

        base: the solution name (filename without extension).
        file_path: full path to the file.
        filename: the filename (with extension).
        submission_format: the task's submission format list.
        task_name: name of the task (for logging).

        return: tuple (files_dict, detected_language) where files_dict maps
                codename to digest.

        """
        digest = self.file_cacher.put_file_from_path(
            file_path,
            "Model solution %s file %s for task %s" %
            (base, filename, task_name))

        codename = _convert_filename_to_codename(filename, submission_format)
        files = {codename: digest}

        detected = filename_to_language(filename)
        language = detected.name if detected else None

        return files, language

    def _merge_solution_entry(self, solutions, name, files, language):
        """Merge a solution entry into the solutions dict.

        If a solution with the same name already exists, merge the files
        and log a warning. This handles the case where both a subdirectory
        and a flat file exist with the same base name.

        solutions: the solutions dict to update.
        name: the solution name.
        files: dict of codename -> digest.
        language: detected language or None.

        """
        if name in solutions and solutions[name]["files"]:
            logger.warning(
                "Multiple definitions for model solution '%s' in solutions "
                "folder; merging files (flat files take precedence)", name)

        entry = solutions.setdefault(name, {"files": {}, "language": None})
        entry["files"].update(files)
        if entry["language"] is None:
            entry["language"] = language

    def contest_has_changed(self):
        """See docstring in class ContestLoader."""
        name = os.path.split(self.path)[1]
        contest_yaml = os.path.join(self.path, "contest.yaml")

        if not os.path.exists(contest_yaml):
            raise LoaderValidationError("File missing: \"contest.yaml\"")

        # If there is no .itime file, we assume that the contest has changed
        if not os.path.exists(os.path.join(self.path, ".itime_contest")):
            return True

        itime = getmtime(os.path.join(self.path, ".itime_contest"))

        # Check if contest.yaml has changed
        if getmtime(contest_yaml) > itime:
            return True

        # Only check for error sentinel file in CLI mode (when no notifier is set).
        # In admin UI mode, the archive is unpacked to a temp directory, so this
        # file cannot be accessed by the user and shouldn't persist across uploads.
        if self._notifier is None:
            if os.path.exists(os.path.join(self.path, ".import_error_contest")):
                raise LoaderValidationError(
                    "Last attempt to import contest %s failed. "
                    "After fixing the error, delete the file .import_error_contest" % name)

        return False

    def user_has_changed(self):
        """See docstring in class UserLoader."""
        # This works as users are kept inside contest.yaml, so changing
        # them alters the last modified time of contest.yaml.
        # TODO Improve this.
        return self.contest_has_changed()

    def team_has_changed(self):
        """See docstring in class TeamLoader."""
        # This works as teams are kept inside contest.yaml, so changing
        # them alters the last modified time of contest.yaml.
        # TODO Improve this.
        return self.contest_has_changed()

    def task_has_changed(self):
        """See docstring in class TaskLoader."""
        name = os.path.split(self.path)[1]

        if (not os.path.exists(os.path.join(self.path, "task.yaml"))) and \
           (not os.path.exists(os.path.join(self.path, "..", name + ".yaml"))):
            raise LoaderValidationError("File missing: \"task.yaml\"")

        # We first look for the yaml file inside the task folder,
        # and eventually fallback to a yaml file in its parent folder.
        try:
            conf = load_yaml_from_path(os.path.join(self.path, "task.yaml"))
        except OSError:
            conf = load_yaml_from_path(
                os.path.join(self.path, "..", name + ".yaml"))

        # If there is no .itime file, we assume that the task has changed
        if not os.path.exists(os.path.join(self.path, ".itime")):
            return True

        itime = getmtime(os.path.join(self.path, ".itime"))

        # Generate a task's list of files
        files = []

        # Testcases (legacy input/output folders)
        if os.path.exists(os.path.join(self.path, "input")):
            for filename in os.listdir(os.path.join(self.path, "input")):
                files.append(os.path.join(self.path, "input", filename))
        if os.path.exists(os.path.join(self.path, "output")):
            for filename in os.listdir(os.path.join(self.path, "output")):
                files.append(os.path.join(self.path, "output", filename))

        # Testcases (new tests/testcases folders and zips)
        for testcases_name in ["tests", "testcases"]:
            testcases_path = os.path.join(self.path, testcases_name)
            if os.path.isdir(testcases_path):
                for filename in os.listdir(testcases_path):
                    files.append(os.path.join(testcases_path, filename))
            zip_path = os.path.join(self.path, testcases_name + ".zip")
            if os.path.exists(zip_path):
                files.append(zip_path)

        # Attachments (use find_first_existing_dir for consistency with get_task)
        att_folder = find_first_existing_dir(
            self.path, ["att", "attachements", "Attachements", "attachments", "Attachments"])
        if att_folder is not None:
            att_path = os.path.join(self.path, att_folder)
            for filename in os.listdir(att_path):
                files.append(os.path.join(att_path, filename))

        # Score file
        files.append(os.path.join(self.path, "gen", "GEN"))

        # Statement (use find_first_existing_dir for consistency with get_task)
        # Handles: statements folder with any PDF, or root directory if no statement folder
        statement_folder = find_first_existing_dir(
            self.path, ["statement", "statements", "Statement", "Statements", "testo"])
        statement_dir = (os.path.join(self.path, statement_folder)
                         if statement_folder is not None else self.path)
        if os.path.isdir(statement_dir):
            for filename in os.listdir(statement_dir):
                if filename.lower().endswith(".pdf"):
                    files.append(os.path.join(statement_dir, filename))

        # Managers (legacy check/cor folders)
        files.append(os.path.join(self.path, "check", "checker"))
        files.append(os.path.join(self.path, "cor", "correttore"))
        files.append(os.path.join(self.path, "check", "manager"))
        files.append(os.path.join(self.path, "cor", "manager"))

        # Managers (new managers folder)
        for managers_name in ["managers", "Managers"]:
            managers_path = os.path.join(self.path, managers_name)
            if os.path.isdir(managers_path):
                for filename in os.listdir(managers_path):
                    files.append(os.path.join(managers_path, filename))

        # Model solutions (supports subdirectory format with multiple files)
        solutions_folder = find_first_existing_dir(
            self.path, ["solutions", "Solutions", "solution", "Solution"])
        if solutions_folder is not None:
            solutions_path = os.path.join(self.path, solutions_folder)
            if os.path.isdir(solutions_path):
                for root, _dirs, filenames in os.walk(solutions_path):
                    for fname in filenames:
                        files.append(os.path.join(root, fname))

        # Generators
        generators_folder = find_first_existing_dir(
            self.path, ["generators", "Generators", "generator", "Generator"])
        if generators_folder is not None:
            generators_path = os.path.join(self.path, generators_folder)
            if os.path.isdir(generators_path):
                for filename in os.listdir(generators_path):
                    files.append(os.path.join(generators_path, filename))

        # Validators
        validators_folder = find_first_existing_dir(
            self.path, ["validators", "Validators", "validator", "Validator"])
        if validators_folder is not None:
            validators_path = os.path.join(self.path, validators_folder)
            if os.path.isdir(validators_path):
                for filename in os.listdir(validators_path):
                    files.append(os.path.join(validators_path, filename))

        # Check if task is OutputOnly(via task_type or legacy output_only field)
        is_output_only = (conf.get('task_type') == "OutputOnly" or
                          conf.get('output_only', False))
        if not is_output_only and os.path.isdir(os.path.join(self.path, "sol")):
            for lang in LANGUAGES:
                files.append(os.path.join(
                    self.path, "sol", "grader%s" % lang.source_extension))
            for other_filename in os.listdir(os.path.join(self.path, "sol")):
                if any(other_filename.endswith(header)
                       for header in HEADER_EXTS):
                    files.append(
                        os.path.join(self.path, "sol", other_filename))

        # Yaml
        files.append(os.path.join(self.path, "task.yaml"))
        files.append(os.path.join(self.path, "..", name + ".yaml"))

        # Check is any of the files have changed
        for fname in files:
            if os.path.exists(fname):
                if getmtime(fname) > itime:
                    return True

        # Only check for error sentinel file in CLI mode (when no notifier is set).
        # In admin UI mode, the archive is unpacked to a temp directory, so this
        # file cannot be accessed by the user and shouldn't persist across uploads.
        if self._notifier is None:
            if os.path.exists(os.path.join(self.path, ".import_error")):
                raise LoaderValidationError(
                    "Last attempt to import task %s failed. "
                    "After fixing the error, delete the file .import_error" % name)

        return False
