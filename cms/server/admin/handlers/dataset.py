#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

"""Dataset-related handlers for AWS.

"""

import io
import os
import logging
import re
import shutil
import tempfile
import uuid
import zipfile

import collections

try:
    collections.MutableMapping
except:
    # Monkey-patch: Tornado 4.5.3 does not work on Python 3.11 by default
    collections.MutableMapping = collections.abc.MutableMapping

import tornado.web

from cms import config
from cms.db import Dataset, Generator, Manager, Message, ModelSolutionMeta, \
    Participation, Session, Submission, Task, Testcase
from cms.grading.tasktypes.util import \
    get_allowed_manager_basenames, compile_manager_bytes, create_sandbox
from cms.grading.languagemanager import filename_to_language, get_language
from cms.grading.language import CompiledLanguage
from cms.grading.subtask_validation import set_sandbox_resource_limits
from cmscommon.datetime import make_datetime
from cmscommon.importers import import_testcases_from_zipfile, compile_template_regex
from .base import BaseHandler, require_permission


logger = logging.getLogger(__name__)


def check_compiled_file_conflict(filename, allowed_basenames, existing_managers):
    """Check if uploading a compiled file conflicts with existing source.

    When a compiled file (no extension) is uploaded for a basename that has
    an existing source file, this would conflict with auto-compilation.

    Args:
        filename: The filename being uploaded.
        allowed_basenames: Set of basenames that are auto-compiled.
        existing_managers: Dict or set of existing manager filenames.

    Returns:
        The conflicting source filename if a conflict exists, None otherwise.
    """
    base_noext = os.path.splitext(os.path.basename(filename))[0]
    has_extension = "." in os.path.basename(filename)

    if base_noext in allowed_basenames and not has_extension:
        for existing_filename in existing_managers:
            existing_base = os.path.splitext(os.path.basename(existing_filename))[0]
            existing_has_ext = "." in os.path.basename(existing_filename)
            if existing_base == base_noext and existing_has_ext:
                return existing_filename
    return None


def validate_template(template: str, name: str) -> str | None:
    """Validate a filename template contains exactly one '*' and no path separators.

    Return an error message if invalid, None if valid.
    """
    if template.count('*') != 1:
        return "%s template must contain exactly one '*'." % name.capitalize()
    if '/' in template or '\\' in template:
        return "%s template must not contain directory separators." % name.capitalize()
    return None


class DatasetSubmissionsHandler(BaseHandler):
    """Shows all submissions for this dataset, allowing the admin to
    view the results under different datasets.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        self.contest = task.contest

        submission_query = self.sql_session.query(Submission)\
            .filter(Submission.task == task)
        page = int(self.get_query_argument("page", 0))
        self.render_params_for_submissions(submission_query, page)

        self.r_params["task"] = task
        self.r_params["active_dataset"] = task.active_dataset
        self.r_params["shown_dataset"] = dataset
        self.r_params["datasets"] = \
            self.sql_session.query(Dataset)\
                            .filter(Dataset.task == task)\
                            .order_by(Dataset.description).all()
        self.render("dataset.html", **self.r_params)


class CloneDatasetHandler(BaseHandler):
    """Clone a dataset by duplicating it (on the same task).

    It's equivalent to the old behavior of AddDatasetHandler when the
    dataset_id_to_copy given was the ID of an existing dataset.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id_to_copy):
        dataset = self.safe_get_item(Dataset, dataset_id_to_copy)
        task = self.safe_get_item(Task, dataset.task_id)
        fallback_page = self.url("task", task.id)

        task_id = task.id

        try:
            original_dataset = \
                self.safe_get_item(Dataset, dataset_id_to_copy)
        except ValueError:
            raise tornado.web.HTTPError(404)

        try:
            attrs = dict()

            self.get_string(attrs, "description")

            # Ensure description is unique.
            if any(attrs["description"] == d.description
                   for d in task.datasets):
                self.service.add_notification(
                    make_datetime(),
                    "Dataset name %r is already taken." % attrs["description"],
                    "Please choose a unique name for this dataset.")
                self.redirect(fallback_page)
                return

            self.get_time_limit(attrs, "time_limit")
            self.get_memory_limit(attrs, "memory_limit")
            self.get_task_type(
                attrs,
                "task_type",
                "TaskTypeOptions_clone_%s_" % dataset_id_to_copy,
            )
            self.get_score_type(attrs, "score_type", "score_type_parameters")

            # Create the dataset.
            attrs["autojudge"] = False
            attrs["task"] = task
            dataset = Dataset(**attrs)
            self.sql_session.add(dataset)

        except Exception as error:
            logger.warning("Invalid field.", exc_info=True)
            self.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if original_dataset is not None:
            # If we were cloning the dataset, copy all managers and
            # testcases across too. If the user insists, clone all
            # evaluation information too.
            clone_results = bool(self.get_argument("clone_results", False))
            clone_managers = bool(self.get_argument("clone_managers", False))
            dataset.clone_from(original_dataset, clone_managers, True, clone_results)

        # If the task does not yet have an active dataset, make this
        # one active.
        if task.active_dataset is None:
            task.active_dataset = dataset

        if self.try_commit():
            self.redirect(self.url("task", task_id))
        else:
            self.redirect(fallback_page)


class RenameDatasetHandler(BaseHandler):
    """Rename the description of a dataset (AJAX-only)."""
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        description: str = self.get_argument("description", "").strip()

        if not description:
            self.set_status(400)
            self.write({"error": "Description is required."})
            return

        # Ensure description is unique (comparing trimmed values)
        if any(
            description == d.description.strip()
            for d in task.datasets
            if d is not dataset
        ):
            self.set_status(400)
            self.write({"error": 'Dataset name "%s" is already taken.' % description})
            return

        dataset.description = description

        if self.try_commit():
            self.write({"success": True, "description": description})
        else:
            self.set_status(500)
            self.write({"error": "Failed to save changes."})
            return


class DeleteDatasetHandler(BaseHandler):
    """Delete a dataset from a task.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        self.sql_session.delete(dataset)

        if self.try_commit():
            # self.service.scoring_service.reinitialize()
            pass
        self.redirect(self.url("task", task.id))


class ActivateDatasetHandler(BaseHandler):
    """Set a given dataset to be the active one for a task."""
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_url = self.url("task", task.id)
        task.active_dataset = dataset

        if dataset.task_type == 'OutputOnly':
            try:
                task.set_default_output_only_submission_format()
            except Exception as e:
                raise RuntimeError(
                    f"Couldn't create default submission format for task {task.id}, "
                    f"dataset {dataset.id}") from e

        if self.try_commit():
            self.service.proxy_service.dataset_updated(
                task_id=task.id)

            # This kicks off judging of any submissions which were previously
            # unloved, but are now part of an autojudged taskset.
            self.service\
                .evaluation_service.search_operations_not_done()
            self.service\
                .scoring_service.search_operations_not_done()

        else:
            self.redirect(fallback_url)
            return

        # Now send notifications to contestants.
        datetime = make_datetime()

        r = re.compile('notify_([0-9]+)$')
        count = 0
        for k in self.request.arguments:
            m = r.match(k)
            if not m:
                continue
            participation = self.safe_get_item(Participation, m.group(1))
            message = Message(datetime,
                              self.get_argument("message_subject", ""),
                              self.get_argument("message_text", ""),
                              participation=participation)
            self.sql_session.add(message)
            count += 1

        if self.try_commit():
            self.service.add_notification(
                make_datetime(),
                "Messages sent to %d users." % count, "")

        self.redirect(fallback_url)


class ToggleAutojudgeDatasetHandler(BaseHandler):
    """Toggle whether a given dataset is judged automatically or not.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)

        dataset.autojudge = not dataset.autojudge

        if self.try_commit():
            # self.service.scoring_service.reinitialize()

            # This kicks off judging of any submissions which were previously
            # unloved, but are now part of an autojudged taskset.
            self.service\
                .evaluation_service.search_operations_not_done()
            self.service\
                .scoring_service.search_operations_not_done()

        self.write("./%d" % dataset.task_id)


class AddManagerHandler(BaseHandler):
    """Add a manager to a dataset.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        # Redirect to task page since we now use modal for adding managers
        self.redirect(self.url("task", task.id))

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_page = self.url("task", task.id)

        # Check if any files were uploaded
        if "manager" not in self.request.files:
            self.service.add_notification(
                make_datetime(),
                "No file selected",
                "Please select at least one file to upload.")
            self.redirect(fallback_page)
            return

        managers = self.request.files["manager"]
        task_name = task.name

        # Decide which auto-compiled basenames are allowed for this task type.
        # Use TaskType constants to avoid hardcoding names and to avoid
        # compiling unintended files (e.g., manager.%l for TwoSteps).
        allowed_compile_basenames = get_allowed_manager_basenames(dataset.task_type)

        # Check all files for compiled file conflicts before processing
        for manager in managers:
            filename = manager["filename"]
            base_noext = os.path.splitext(os.path.basename(filename))[0]

            # Check if uploading a compiled file conflicts with existing source
            conflicting_source = check_compiled_file_conflict(
                filename, allowed_compile_basenames, dataset.managers.keys())
            if conflicting_source is not None:
                self.service.add_notification(
                    make_datetime(),
                    "Cannot upload compiled manager",
                    ("A source file '%s' already exists for '%s'. "
                     "Compiled files are auto-generated from source. "
                     "Please upload the source file instead, or delete "
                     "the existing source first." %
                     (conflicting_source, base_noext)))
                self.redirect(fallback_page)
                return

        self.sql_session.close()

        def notify(title, text):
            self.service.add_notification(make_datetime(), title, text)

        # Phase 1: Compile all files first, collecting results in memory.
        # This ensures no files are stored in file_cacher if any compilation fails.
        planned_entries: list[tuple[str, bytes]] = []  # (filename, content_bytes)
        for manager in managers:
            filename = manager["filename"]
            body = manager["body"]
            base_noext = os.path.splitext(os.path.basename(filename))[0]

            # Always plan to store the original upload.
            planned_entries.append((filename, body))

            # If a source file for a known compiled language is uploaded,
            # compile it into an executable manager.
            language = filename_to_language(filename)

            if (language is not None
                    and isinstance(language, CompiledLanguage)
                    and base_noext in allowed_compile_basenames):
                compiled_filename = base_noext
                success, compiled_bytes, _stats = compile_manager_bytes(
                    self.service.file_cacher,
                    filename,
                    body,
                    compiled_filename,
                    sandbox_name="admin_compile",
                    for_evaluation=True,
                    notify=notify
                )

                if not success:
                    self.redirect(fallback_page)
                    return

                # Plan to store the compiled executable.
                if compiled_bytes is not None:
                    planned_entries.append((compiled_filename, compiled_bytes))

        # Phase 2: All compilations succeeded, now store all files in file_cacher.
        all_stored_entries: list[tuple[str, str]] = []  # (filename, digest)
        for filename, content in planned_entries:
            try:
                digest = self.service.file_cacher.put_file_content(
                    content, "Task manager for %s" % task_name
                )
                all_stored_entries.append((filename, digest))
            except Exception as error:
                logger.warning("Failed to store manager '%s'", filename, exc_info=True)
                self.service.add_notification(
                    make_datetime(),
                    "Manager storage failed",
                    "Error storing '%s': %s" % (filename, repr(error)),
                )
                self.redirect(fallback_page)
                return

        # Phase 3: Update database with all manager records.
        self.sql_session = Session()
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        for fname, dig in all_stored_entries:
            existing_manager = dataset.managers.get(fname)
            if existing_manager is not None:
                existing_manager.digest = dig
            else:
                manager = Manager(fname, dig, dataset=dataset)
                self.sql_session.add(manager)

        if self.try_commit():
            self.redirect(self.url("task", task.id))
        else:
            self.redirect(fallback_page)


class DeleteManagerHandler(BaseHandler):
    """Delete a manager."""

    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, dataset_id, manager_id):
        manager = self.safe_get_item(Manager, manager_id)
        dataset = self.safe_get_item(Dataset, dataset_id)

        # Protect against URLs providing incompatible parameters.
        if manager.dataset is not dataset:
            raise tornado.web.HTTPError(404)

        task_id = dataset.task_id

        # If deleting a source manager for checker/manager, also delete the compiled counterpart.
        filename = manager.filename
        base_noext = os.path.splitext(os.path.basename(filename))[0]
        # Determine if this is a source file (has an extension) for special basenames.
        if base_noext in ("checker", "manager") and "." in filename:
            # compiled counterpart has exactly the basename with no extension
            counterpart_name = base_noext
            # Need to re-fetch dataset.managers in this session scope
            try:
                counterpart = dataset.managers.get(counterpart_name)
            except Exception:
                counterpart = None
            if counterpart is not None:
                self.sql_session.delete(counterpart)

        self.sql_session.delete(manager)

        self.try_commit()
        self.write("./%d" % task_id)


class AddTestcaseHandler(BaseHandler):
    """Add a testcase to a dataset."""

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_page = self.url("task", task.id)

        codename = self.get_argument("codename")

        try:
            input_ = self.request.files["input"][0]
            output = self.request.files["output"][0]
        except KeyError:
            self.service.add_notification(
                make_datetime(), "Invalid data", "Please fill both input and output."
            )
            self.redirect(fallback_page)
            return

        public = self.get_argument("public", None) is not None
        task_name = task.name
        self.sql_session.close()

        try:
            input_digest = self.service.file_cacher.put_file_content(
                input_["body"], "Testcase input for task %s" % task_name
            )
            output_digest = self.service.file_cacher.put_file_content(
                output["body"], "Testcase output for task %s" % task_name
            )
        except Exception as error:
            self.service.add_notification(
                make_datetime(), "Testcase storage failed", repr(error)
            )
            self.redirect(fallback_page)
            return

        self.sql_session = Session()
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        testcase = Testcase(
            codename, public, input_digest, output_digest, dataset=dataset
        )
        self.sql_session.add(testcase)

        if dataset.active and dataset.task_type == "OutputOnly":
            try:
                task.set_default_output_only_submission_format()
            except Exception as e:
                raise RuntimeError(
                    f"Couldn't create default submission format for task {task.id}, "
                    f"dataset {dataset.id}"
                ) from e

        if self.try_commit():
            # max_score and/or extra_headers might have changed.
            self.service.proxy_service.reinitialize()
            self.redirect(self.url("task", task.id))
        else:
            self.redirect(fallback_page)


class AddTestcasesHandler(BaseHandler):
    """Add several testcases to a dataset."""

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_page = self.url("task", task.id)

        try:
            archive = self.request.files["archive"][0]
        except KeyError:
            self.service.add_notification(
                make_datetime(), "Invalid data", "Please choose tests archive."
            )
            self.redirect(fallback_page)
            return

        # Check for empty file
        if len(archive["body"]) == 0:
            self.service.add_notification(
                make_datetime(),
                "Empty file",
                "The selected archive is empty. Please select a non-empty zip file.",
            )
            self.redirect(fallback_page)
            return

        public = self.get_argument("public", None) is not None
        overwrite = self.get_argument("overwrite", None) is not None

        # Get input/output file names templates, or use default ones.
        input_template: str = self.get_argument("input_template", "input.*")
        output_template: str = self.get_argument("output_template", "output.*")

        # Validate templates
        error = validate_template(input_template, "input")
        if not error:
            error = validate_template(output_template, "output")
        if error:
            self.service.add_notification(
                make_datetime(), "Invalid template", error)
            self.redirect(fallback_page)
            return

        try:
            input_re = compile_template_regex(input_template)
            output_re = compile_template_regex(output_template)
        except ValueError as e:
            self.service.add_notification(
                make_datetime(), "Invalid template", str(e))
            self.redirect(fallback_page)
            return

        fp = io.BytesIO(archive["body"])
        try:
            successful_subject, successful_text = \
                import_testcases_from_zipfile(
                    self.sql_session,
                    self.service.file_cacher, dataset,
                    fp, input_re, output_re, overwrite, public)
        except Exception as error:
            self.service.add_notification(
                make_datetime(), str(error), repr(error))
            self.redirect(fallback_page)
            return

        self.service.add_notification(
            make_datetime(), successful_subject, successful_text)
        self.service.proxy_service.reinitialize()
        self.redirect(self.url("task", task.id))


class DeleteTestcaseHandler(BaseHandler):
    """Delete a testcase.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, dataset_id, testcase_id):
        testcase = self.safe_get_item(Testcase, testcase_id)
        dataset = self.safe_get_item(Dataset, dataset_id)

        # Protect against URLs providing incompatible parameters.
        if dataset is not testcase.dataset:
            raise tornado.web.HTTPError(404)

        task_id = testcase.dataset.task_id
        task = dataset.task

        self.sql_session.delete(testcase)

        if dataset.active and dataset.task_type == "OutputOnly":
            dataset.testcases.pop(testcase.codename, None)
            try:
                task.set_default_output_only_submission_format()
            except Exception as e:
                raise RuntimeError(
                    f"Couldn't create default submission format for task {task.id}, "
                    f"dataset {dataset.id}") from e

        if self.try_commit():
            # max_score and/or extra_headers might have changed.
            self.service.proxy_service.reinitialize()
        self.write("./%d" % task_id)


class DeleteSelectedTestcasesHandler(BaseHandler):
    """Delete multiple selected testcases from a dataset.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        task_id = task.id

        # Collect selected testcase IDs from the request.
        id_strings = self.get_arguments("testcase_id")

        # If nothing was selected, just redirect back without doing anything.
        if not id_strings:
            self.write("./%d" % task_id)
            return

        testcases = []
        for id_str in id_strings:
            try:
                tid = int(id_str)
            except ValueError:
                raise tornado.web.HTTPError(400)
            tc = self.safe_get_item(Testcase, tid)

            # Protect against mixing datasets.
            if tc.dataset is not dataset:
                raise tornado.web.HTTPError(400)

            testcases.append(tc)

        # Delete all selected testcases.
        for tc in testcases:
            self.sql_session.delete(tc)

        # Handle OutputOnly tasks
        if dataset.active and dataset.task_type == "OutputOnly":
            for tc in testcases:
                dataset.testcases.pop(tc.codename, None)
            try:
                task.set_default_output_only_submission_format()
            except Exception as e:
                raise RuntimeError(
                    f"Couldn't create default submission format for task {task.id}, "
                    f"dataset {dataset.id}") from e

        if self.try_commit():
            # max_score and/or extra_headers might have changed.
            self.service.proxy_service.reinitialize()
        self.write("./%d" % task_id)


class DownloadTestcasesHandler(BaseHandler):
    """Download all testcases in a zip file.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_page = self.url("task", task.id)

        # Get zip file name, input/output file names templates,
        # or use default ones.
        zip_filename: str = self.get_argument("zip_filename", "testcases.zip")
        input_template: str = self.get_argument("input_template", "input.*")
        output_template: str = self.get_argument("output_template", "output.*")

        # Template validations
        error = validate_template(input_template, "input")
        if error is None:
            error = validate_template(output_template, "output")
        if error is not None:
            self.service.add_notification(
                make_datetime(),
                "Invalid template format",
                error)
            self.redirect(fallback_page)
            return

        # Replace input/output template placeholder with the python format.
        input_template = input_template.strip().replace("*", "%s")
        output_template = output_template.strip().replace("*", "%s")

        # FIXME When Tornado will stop having the WSGI adapter buffer
        # the whole response, we could use a tempfile.TemporaryFile so
        # to avoid having the whole ZIP file in memory at once.
        temp_file = io.BytesIO()
        with zipfile.ZipFile(temp_file, "w") as zip_file:
            for testcase in dataset.testcases.values():
                # Copy input file
                with zip_file.open(input_template % testcase.codename, 'w') as fout:
                    self.service.file_cacher.get_file_to_fobj(testcase.input, fout)
                # Copy output file
                with zip_file.open(output_template % testcase.codename, 'w') as fout:
                    self.service.file_cacher.get_file_to_fobj(testcase.output, fout)

        self.set_header("Content-Type", "application/zip")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s\"" % zip_filename)

        self.write(temp_file.getvalue())


class AddGeneratorHandler(BaseHandler):
    """Add a generator to a dataset."""
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_page = self.url("task", task.id)
        task_name = task.name

        generator_file = self.request.files.get("generator")
        if not generator_file:
            self.service.add_notification(
                make_datetime(),
                "No generator file",
                "Please upload a generator source file.")
            self.redirect(fallback_page)
            return

        generator_file = generator_file[0]
        filename = generator_file["filename"]
        body = generator_file["body"]

        input_filename_template = self.get_argument(
            "input_filename_template", "input.*").strip()
        output_filename_template = self.get_argument(
            "output_filename_template", "output.*").strip()

        error = validate_template(input_filename_template, "input")
        if error is None:
            error = validate_template(output_filename_template, "output")
        if error is not None:
            self.service.add_notification(
                make_datetime(),
                "Invalid template",
                error)
            self.redirect(fallback_page)
            return

        # Get language from form (explicit selection) instead of auto-detection
        # This allows distinguishing between languages with the same extension
        # (e.g., PyPy vs CPython for .py files)
        language_name = self.get_argument("language", "").strip()
        if not language_name:
            # Fallback to auto-detection if no language selected
            language = filename_to_language(filename)
            if language is None:
                self.service.add_notification(
                    make_datetime(),
                    "Unknown language",
                    "Could not detect language for file '%s'." % filename)
                self.redirect(fallback_page)
                return
            language_name = language.name
        else:
            try:
                language = get_language(language_name)
            except KeyError:
                self.service.add_notification(
                    make_datetime(),
                    "Unknown language",
                    "Language '%s' is not supported." % language_name)
                self.redirect(fallback_page)
                return

        if not isinstance(language, CompiledLanguage):
            self.service.add_notification(
                make_datetime(),
                "Invalid language",
                "Generator must be a compiled language, not '%s'." %
                language.name)
            self.redirect(fallback_page)
            return

        self.sql_session.close()

        compiled_filename = "generator"

        def notify(title, text):
            self.service.add_notification(make_datetime(), title, text)

        success, compiled_bytes, _stats = compile_manager_bytes(
            self.service.file_cacher,
            filename,
            body,
            compiled_filename,
            sandbox_name="admin_compile",
            for_evaluation=True,
            notify=notify,
            language_name=language_name
        )

        if not success:
            self.redirect(fallback_page)
            return

        try:
            source_digest = self.service.file_cacher.put_file_content(
                body, "Generator source for %s" % task_name)
        except Exception as error:
            self.service.add_notification(
                make_datetime(),
                "Generator storage failed",
                "Error storing source: %s" % repr(error))
            self.redirect(fallback_page)
            return

        executable_digest = None
        if compiled_bytes is not None:
            try:
                executable_digest = self.service.file_cacher.put_file_content(
                    compiled_bytes, "Compiled generator for %s" % task_name)
            except Exception as error:
                self.service.add_notification(
                    make_datetime(),
                    "Generator storage failed",
                    "Error storing executable: %s" % repr(error))
                self.redirect(fallback_page)
                return

        self.sql_session = Session()
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        existing_generator = dataset.generators.get(filename)
        if existing_generator is not None:
            existing_generator.digest = source_digest
            existing_generator.executable_digest = executable_digest
            existing_generator.input_filename_template = input_filename_template
            existing_generator.output_filename_template = output_filename_template
            existing_generator.language_name = language_name
        else:
            generator = Generator(
                filename=filename,
                digest=source_digest,
                executable_digest=executable_digest,
                input_filename_template=input_filename_template,
                output_filename_template=output_filename_template,
                language_name=language_name,
                dataset=dataset)
            self.sql_session.add(generator)

        if self.try_commit():
            self.redirect(self.url("task", task.id))
        else:
            self.redirect(fallback_page)


class EditGeneratorHandler(BaseHandler):
    """Edit a generator's filename templates."""
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id, generator_id):
        generator = self.safe_get_item(Generator, generator_id)
        dataset = self.safe_get_item(Dataset, dataset_id)

        if generator.dataset is not dataset:
            raise tornado.web.HTTPError(404)

        task = dataset.task
        fallback_page = self.url("task", task.id)

        input_filename_template = self.get_argument(
            "input_filename_template", "input.*").strip()
        output_filename_template = self.get_argument(
            "output_filename_template", "output.*").strip()

        error = validate_template(input_filename_template, "input")
        if error is None:
            error = validate_template(output_filename_template, "output")
        if error is not None:
            self.service.add_notification(
                make_datetime(),
                "Invalid template",
                error)
            self.redirect(fallback_page)
            return

        generator.input_filename_template = input_filename_template
        generator.output_filename_template = output_filename_template

        if self.try_commit():
            self.redirect(self.url("task", task.id))
        else:
            self.redirect(fallback_page)


class DeleteGeneratorHandler(BaseHandler):
    """Delete a generator.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, dataset_id, generator_id):
        generator = self.safe_get_item(Generator, generator_id)
        dataset = self.safe_get_item(Dataset, dataset_id)

        if generator.dataset is not dataset:
            raise tornado.web.HTTPError(404)

        task_id = dataset.task_id
        self.sql_session.delete(generator)

        self.try_commit()
        self.write("./%d" % task_id)


class GenerateTestcasesHandler(BaseHandler):
    """Generate testcases using a generator.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id, generator_id):
        generator = self.safe_get_item(Generator, generator_id)
        dataset = self.safe_get_item(Dataset, dataset_id)

        if generator.dataset is not dataset:
            raise tornado.web.HTTPError(404)

        task = dataset.task
        fallback_page = self.url("task", task.id)

        if generator.executable_digest is None:
            self.service.add_notification(
                make_datetime(),
                "Generator not compiled",
                "The generator has not been compiled successfully.",
            )
            self.redirect(fallback_page)
            return

        overwrite = self.get_argument("overwrite", "") == "on"
        public = self.get_argument("public", "") == "on"
        output_source = self.get_argument("output_source", "generator")
        stdin_input = self.get_argument("stdin_input", "")

        input_template = generator.input_filename_template
        output_template = generator.output_filename_template
        task_time_limit = dataset.time_limit

        # Check if we're using a model solution for output generation
        # (only allowed for Batch tasks)
        model_solution_meta = None
        model_solution_result = None
        use_empty_outputs = False
        if output_source.startswith("model_solution_"):
            if dataset.task_type != "Batch":
                self.service.add_notification(
                    make_datetime(),
                    "Invalid output source",
                    "Model solution output generation is only supported "
                    "for Batch tasks.")
                self.redirect(fallback_page)
                return
            try:
                meta_id = int(output_source.replace("model_solution_", ""))
                model_solution_meta = self.safe_get_item(
                    ModelSolutionMeta, meta_id)
                if model_solution_meta.dataset_id != dataset.id:
                    raise tornado.web.HTTPError(400, "Invalid model solution")
                model_solution_result = model_solution_meta.submission.get_result(
                    dataset)
                if model_solution_result is None or \
                        not model_solution_result.executables:
                    self.service.add_notification(
                        make_datetime(),
                        "Model solution not compiled",
                        "The selected model solution has not been compiled.")
                    self.redirect(fallback_page)
                    return
            except (ValueError, TypeError):
                self.service.add_notification(
                    make_datetime(),
                    "Invalid output source",
                    "The selected output source is invalid.")
                self.redirect(fallback_page)
                return
        elif output_source == "empty":
            use_empty_outputs = True

        self.sql_session.close()

        # Use stored language_name if available, otherwise fall back to auto-detection
        language = None
        if generator.language_name:
            try:
                language = get_language(generator.language_name)
            except KeyError:
                logger.debug(
                    "Stored language '%s' not found for generator %s, "
                    "falling back to auto-detection",
                    generator.language_name, generator.filename)
        if language is None:
            language = filename_to_language(generator.filename)

        exe_name = "generator"
        if language is not None and isinstance(language, CompiledLanguage):
            exe_name += language.executable_extension

        sandbox = None
        try:
            sandbox = create_sandbox(self.service.file_cacher,
                                     name="admin_generate")

            sandbox.create_file_from_storage(exe_name,
                                             generator.executable_digest,
                                             executable=True)

            cmd = ["./" + exe_name]
            if language is not None:
                try:
                    cmds = language.get_evaluation_commands(exe_name)
                    if cmds:
                        cmd = cmds[0]
                except Exception as e:
                    logger.debug(
                        "get_evaluation_commands failed for %s: %s, using default",
                        generator.filename, e)

            # Apply resource limits to prevent runaway generators
            set_sandbox_resource_limits(sandbox)

            if task_time_limit is not None:
                effective_timeout = max(
                    sandbox.timeout, task_time_limit, 30.0)
                sandbox.timeout = effective_timeout
                sandbox.wallclock_timeout = effective_timeout * 2

            # If stdin input was provided, write it to a file and
            # configure the sandbox to pipe it to the generator.
            if stdin_input:
                sandbox.create_file_from_string(
                    "stdin.txt", stdin_input.encode("utf-8"))
                sandbox.stdin_file = "stdin.txt"

            # Set stdout/stderr files so they are created during execution
            sandbox.stdout_file = "stdout.txt"
            sandbox.stderr_file = "stderr.txt"

            box_success = sandbox.execute_without_std(cmd, wait=True)

            # Read stdout/stderr (best-effort, may not exist)
            stdout = ""
            stderr = ""
            try:
                stdout = sandbox.get_file_to_string("stdout.txt", maxlen=65536)
            except FileNotFoundError:
                pass
            try:
                stderr = sandbox.get_file_to_string("stderr.txt", maxlen=65536)
            except FileNotFoundError:
                pass

            if not box_success:
                self.service.add_notification(
                    make_datetime(),
                    "Generator execution failed",
                    "Sandbox error during execution.\nStdout:\n%s\nStderr:\n%s"
                    % (stdout, stderr))
                self.redirect(fallback_page)
                return

            exit_status = sandbox.get_exit_status()
            if exit_status != sandbox.EXIT_OK:
                self.service.add_notification(
                    make_datetime(),
                    "Generator execution failed",
                    "Exit status: %s\nStdout:\n%s\nStderr:\n%s" %
                    (exit_status, stdout, stderr))
                self.redirect(fallback_page)
                return

            input_re = compile_template_regex(input_template)
            output_re = compile_template_regex(output_template)

            # Create a temporary directory to store generated files
            temp_dir = tempfile.mkdtemp(prefix="cms_generate_")

            # Collect files from generator sandbox to temp directory
            sandbox_home = sandbox.relative_path("")
            for root, _dirs, files in os.walk(sandbox_home):
                for filename in files:
                    if filename in [exe_name, "stdout.txt", "stderr.txt",
                                    "stdin.txt"]:
                        continue
                    rel_path = os.path.relpath(
                        os.path.join(root, filename), sandbox_home)
                    content = sandbox.get_file_to_string(rel_path, maxlen=None)
                    dest_path = os.path.join(temp_dir, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, "wb") as f:
                        if isinstance(content, str):
                            f.write(content.encode("utf-8"))
                        else:
                            f.write(content)

        except Exception as error:
            self.service.add_notification(
                make_datetime(),
                "Generator execution error",
                repr(error))
            self.redirect(fallback_page)
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return
        finally:
            if sandbox:
                sandbox.cleanup(delete=True)

        try:
            # If using model solution for outputs, generate them now
            if model_solution_meta is not None:
                success = self._generate_outputs_with_model_solution(
                    temp_dir,
                    input_re,
                    output_template,
                    model_solution_result,
                    model_solution_meta.submission.language,
                    dataset.task_type_parameters,
                    dataset.time_limit,
                    dataset.memory_limit,
                    fallback_page)
                if not success:
                    # Error already reported, redirect already done
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return

            # If using empty outputs, generate them now
            if use_empty_outputs:
                self._generate_empty_outputs(
                    temp_dir,
                    input_re,
                    output_template)

            # Create zip from temp directory
            temp_zip = io.BytesIO()
            with zipfile.ZipFile(temp_zip, "w") as zf:
                for root, _dirs, files in os.walk(temp_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, rel_path)
            temp_zip.seek(0)
        except Exception as error:
            self.service.add_notification(
                make_datetime(),
                "Output generation error",
                repr(error))
            self.redirect(fallback_page)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.sql_session = Session()
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        try:
            successful_subject, successful_text = import_testcases_from_zipfile(
                self.sql_session,
                self.service.file_cacher,
                dataset,
                temp_zip,
                input_re,
                output_re,
                overwrite,
                public)
            self.service.add_notification(
                make_datetime(),
                successful_subject,
                successful_text)
        except Exception as error:
            self.service.add_notification(
                make_datetime(),
                "Testcase import failed",
                repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # max_score and/or extra_headers might have changed.
            self.service.proxy_service.reinitialize()
            self.redirect(self.url("task", task.id))
        else:
            self.redirect(fallback_page)

    def _generate_outputs_with_model_solution(
            self,
            temp_dir,
            input_re,
            output_template,
            model_solution_result,
            language_name,
            task_type_parameters,
            time_limit,
            memory_limit,
            fallback_page):
        """Generate output files by running a model solution on input files.

        temp_dir: path to temporary directory containing generated files
        input_re: compiled regex for matching input files
        output_template: template for output filenames (e.g., "output.*")
        model_solution_result: SubmissionResult with compiled executables
        language_name: language name of the model solution
        task_type_parameters: task type parameters for I/O configuration
        time_limit: time limit in seconds (from dataset)
        memory_limit: memory limit in bytes (from dataset)
        fallback_page: URL to redirect to on error

        return: True on success, False on error
        """
        # Get the executable
        if not model_solution_result.executables:
            self.service.add_notification(
                make_datetime(),
                "Model solution not compiled",
                "The model solution has no compiled executables.")
            self.redirect(fallback_page)
            return False

        exe_filename = next(iter(model_solution_result.executables.keys()))
        exe_digest = model_solution_result.executables[exe_filename].digest

        # Get language for evaluation commands
        sol_language = None
        if language_name:
            try:
                sol_language = get_language(language_name)
            except KeyError:
                logger.debug(
                    "Language '%s' not found for model solution, "
                    "using default execution",
                    language_name)

        # Parse task type parameters to determine I/O mode
        # Default to stdin/stdout if parameters are not available
        input_filename = ""
        output_filename = ""
        if task_type_parameters and len(task_type_parameters) >= 2:
            io_params = task_type_parameters[1]
            if isinstance(io_params, (list, tuple)) and len(io_params) >= 2:
                input_filename = io_params[0] or ""
                output_filename = io_params[1] or ""

        # Determine actual input/output filenames
        actual_input = input_filename if input_filename else "input.txt"
        actual_output = output_filename if output_filename else "output.txt"

        # Find input files in temp directory
        input_files = {}  # codename -> file_path
        for root, _dirs, files in os.walk(temp_dir):
            for filename in files:
                rel_path = os.path.relpath(
                    os.path.join(root, filename), temp_dir)
                match = input_re.match(rel_path)
                if match:
                    codename = match.group(1)
                    input_files[codename] = os.path.join(root, filename)

        if not input_files:
            self.service.add_notification(
                make_datetime(),
                "No input files found",
                "The generator did not produce any files matching the "
                "input template.")
            self.redirect(fallback_page)
            return False

        # Generate output for each input file
        for codename, input_file_path in input_files.items():
            output_filename_for_tc = output_template.replace("*", codename)

            sandbox = None
            try:
                sandbox = create_sandbox(self.service.file_cacher,
                                         name="admin_model_solution")

                # Copy executable
                sandbox.create_file_from_storage(exe_filename, exe_digest,
                                                 executable=True)

                # Copy input file
                with open(input_file_path, "rb") as f:
                    input_content = f.read()
                sandbox.create_file_from_string(actual_input, input_content)

                # Prepare execution command
                main_name = os.path.splitext(exe_filename)[0]
                if sol_language is not None:
                    cmd = sol_language.get_evaluation_commands(
                        exe_filename, main=main_name)
                    if cmd:
                        cmd = cmd[0]
                    else:
                        cmd = ["./" + exe_filename]
                else:
                    cmd = ["./" + exe_filename]

                # Set up I/O redirection
                stdin_redirect = None
                stdout_redirect = None
                if not input_filename:  # Use stdin
                    stdin_redirect = actual_input
                if not output_filename:  # Use stdout
                    stdout_redirect = actual_output

                sandbox.stdin_file = stdin_redirect
                sandbox.stdout_file = stdout_redirect
                sandbox.stderr_file = "stderr.txt"

                # Apply task time/memory limits
                if time_limit is not None:
                    sandbox.timeout = time_limit
                    sandbox.wallclock_timeout = time_limit * 2
                if memory_limit is not None:
                    sandbox.address_space = memory_limit

                box_success = sandbox.execute_without_std(cmd, wait=True)

                if not box_success:
                    stderr = ""
                    try:
                        stderr = sandbox.get_file_to_string(
                            "stderr.txt", maxlen=65536)
                    except FileNotFoundError:
                        pass
                    self.service.add_notification(
                        make_datetime(),
                        "Model solution execution failed",
                        "Sandbox error for testcase '%s'.\nStderr:\n%s" %
                        (codename, stderr))
                    self.redirect(fallback_page)
                    return False

                exit_status = sandbox.get_exit_status()
                if exit_status != sandbox.EXIT_OK:
                    stderr = ""
                    try:
                        stderr = sandbox.get_file_to_string(
                            "stderr.txt", maxlen=65536)
                    except FileNotFoundError:
                        pass
                    self.service.add_notification(
                        make_datetime(),
                        "Model solution execution failed",
                        "Exit status '%s' for testcase '%s'.\nStderr:\n%s" %
                        (exit_status, codename, stderr))
                    self.redirect(fallback_page)
                    return False

                # Read output
                if not sandbox.file_exists(actual_output):
                    self.service.add_notification(
                        make_datetime(),
                        "Model solution produced no output",
                        "No output file '%s' for testcase '%s'." %
                        (actual_output, codename))
                    self.redirect(fallback_page)
                    return False

                output_content = sandbox.get_file_to_string(
                    actual_output, maxlen=None)

                # Write output to temp directory
                output_path = os.path.join(temp_dir, output_filename_for_tc)
                with open(output_path, "wb") as f:
                    if isinstance(output_content, str):
                        f.write(output_content.encode("utf-8"))
                    else:
                        f.write(output_content)

            finally:
                if sandbox:
                    sandbox.cleanup(delete=True)

        return True

    def _generate_empty_outputs(
            self,
            temp_dir,
            input_re,
            output_template):
        """Generate empty output files for each input file.

        This is useful when outputs are not needed or will be generated
        separately.

        temp_dir: path to temporary directory containing generated files
        input_re: compiled regex for matching input files
        output_template: template for output filenames (e.g., "output.*")
        """
        for root, _dirs, files in os.walk(temp_dir):
            for filename in files:
                rel_path = os.path.relpath(
                    os.path.join(root, filename), temp_dir)
                match = input_re.match(rel_path)
                if match:
                    codename = match.group(1)
                    output_filename = output_template.replace("*", codename)
                    output_path = os.path.join(temp_dir, output_filename)
                    open(output_path, "wb").close()  # Create empty file


class RenameTestcaseHandler(BaseHandler):
    """Rename a testcase's codename.

    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id, testcase_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        testcase = self.safe_get_item(Testcase, testcase_id)
        task = dataset.task

        # Protect against URLs providing incompatible parameters.
        if testcase.dataset is not dataset:
            raise tornado.web.HTTPError(404)

        # Support redirect back to subtask details page if subtask_index is provided
        subtask_index = self.get_argument("subtask_index", None)
        if subtask_index is not None:
            fallback_page = self.url("dataset", dataset_id, "subtask", subtask_index, "details")
        else:
            fallback_page = self.url("task", task.id)

        new_codename = self.get_argument("new_codename", "").strip()
        if not new_codename:
            self.service.add_notification(
                make_datetime(),
                "Invalid codename",
                "Codename cannot be empty.")
            self.redirect(fallback_page)
            return

        old_codename = testcase.codename

        # Check if the new codename already exists in this dataset
        if new_codename != old_codename and new_codename in dataset.testcases:
            self.service.add_notification(
                make_datetime(),
                "Codename already exists",
                "A testcase with codename '%s' already exists in this dataset." % new_codename)
            self.redirect(fallback_page)
            return

        # Update the codename
        # First remove from the collection (keyed by old codename)
        del dataset.testcases[old_codename]
        # Update the codename
        testcase.codename = new_codename
        # Re-add to the collection (keyed by new codename)
        dataset.testcases[new_codename] = testcase

        # Update submission format for OutputOnly tasks
        if dataset.active and dataset.task_type == "OutputOnly":
            try:
                task.set_default_output_only_submission_format()
            except Exception as e:
                raise RuntimeError(
                    f"Couldn't create default submission format for task {task.id}, "
                    f"dataset {dataset.id}") from e

        if self.try_commit():
            self.service.add_notification(
                make_datetime(),
                "Testcase renamed",
                "Testcase renamed from '%s' to '%s'." % (old_codename, new_codename))
        self.redirect(fallback_page)


def _apply_codename_mapping(dataset, testcases, new_codenames, sql_session):
    """Apply a codename mapping to testcases using two-phase DB update.

    This uses a two-phase approach with temporary intermediate names to safely
    handle cases where a new codename equals another selected testcase's old
    codename, avoiding DB UNIQUE constraint violations during chained updates.

    Args:
        dataset: The dataset containing the testcases
        testcases: List of testcases being renamed
        new_codenames: Dict mapping testcase.id to new codename
        sql_session: SQLAlchemy session for flushing (optional, but recommended
                     to avoid UNIQUE constraint violations)

    Returns:
        Number of testcases actually renamed (where codename changed)
    """
    # Identify testcases that are actually changing
    changing_testcases = []
    for tc in testcases:
        new_codename = new_codenames.get(tc.id)
        if new_codename is not None and tc.codename != new_codename:
            changing_testcases.append((tc, new_codename))

    if not changing_testcases:
        return 0

    # Collect all existing codenames to ensure temp names don't collide
    existing_codenames = set(dataset.testcases.keys())
    final_codenames = {new_cn for _, new_cn in changing_testcases}

    # Phase 1: Assign unique temporary codenames and flush to DB
    temp_mappings = []  # (tc, temp_codename, final_codename)
    for tc, final_codename in changing_testcases:
        # Generate a unique temp codename that doesn't collide with existing
        # or final codenames
        while True:
            temp_codename = f"__tmp_{uuid.uuid4().hex[:12]}__"
            if (
                temp_codename not in existing_codenames
                and temp_codename not in final_codenames
            ):
                break

        del dataset.testcases[tc.codename]
        tc.codename = temp_codename
        dataset.testcases[temp_codename] = tc
        existing_codenames.add(temp_codename)
        temp_mappings.append((tc, temp_codename, final_codename))

    # Flush to DB to persist temp names before applying final names
    sql_session.flush()

    # Phase 2: Update to final codenames and flush again
    for tc, temp_codename, final_codename in temp_mappings:
        del dataset.testcases[temp_codename]
        tc.codename = final_codename
        dataset.testcases[final_codename] = tc

    sql_session.flush()

    return len(changing_testcases)


def _add_prefix_if_missing(codename, prefix):
    """Add prefix to codename only if it's not already a substring."""
    if prefix in codename:
        return codename
    return prefix + codename


def _batch_rename_testcases(
    handler, dataset, task, testcases, codename_modifier, fallback_page
):
    """Common logic for batch renaming testcases.

    Args:
        handler: The request handler (for notifications, commit, redirect)
        dataset: The dataset containing the testcases
        task: The task owning the dataset
        testcases: List of testcases to rename
        codename_modifier: Function(testcase) -> (new_codename, error_msg)
                          Returns new codename or (None, error_msg) on failure
        fallback_page: URL to redirect to

    Returns:
        (success, renamed_count) tuple. If success is False, handler has
        already been redirected with an error notification.
    """
    # Build the new codename mapping
    testcase_set = set(testcases)
    new_codenames = {}
    seen_codenames = {}  # new_codename -> tc, for duplicate detection

    for tc in testcases:
        new_codename, error_msg = codename_modifier(tc)
        if error_msg is not None:
            handler.service.add_notification(make_datetime(), "Rename error", error_msg)
            handler.redirect(fallback_page)
            return (False, 0)

        # Check for duplicates within the mapping itself
        if new_codename in seen_codenames:
            handler.service.add_notification(
                make_datetime(),
                "Codename conflict",
                "Renaming would create duplicate codename '%s'." % new_codename,
            )
            handler.redirect(fallback_page)
            return (False, 0)
        seen_codenames[new_codename] = tc

        # Check for conflicts with existing testcases not in the selection
        if new_codename in dataset.testcases:
            existing_tc = dataset.testcases[new_codename]
            if existing_tc not in testcase_set:
                handler.service.add_notification(
                    make_datetime(),
                    "Codename conflict",
                    "Renaming would create duplicate codename '%s'." % new_codename,
                )
                handler.redirect(fallback_page)
                return (False, 0)

        new_codenames[tc.id] = new_codename

    # Apply the rename using two-phase approach with DB flush
    renamed_count = _apply_codename_mapping(
        dataset, testcases, new_codenames, handler.sql_session
    )

    # Update submission format for OutputOnly tasks
    if dataset.active and dataset.task_type == "OutputOnly":
        try:
            task.set_default_output_only_submission_format()
        except Exception as e:
            raise RuntimeError(
                f"Couldn't create default submission format for task {task.id}, "
                f"dataset {dataset.id}"
            ) from e

    return (True, renamed_count)


class BatchRenameTestcasesHandler(BaseHandler):
    """Batch rename testcases - add prefix or remove common substring."""

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task

        # Support redirect back to subtask details page if subtask_index is provided
        subtask_index = self.get_argument("subtask_index", None)
        if subtask_index is not None:
            fallback_page = self.url(
                "dataset", dataset_id, "subtask", subtask_index, "details"
            )
        else:
            fallback_page = self.url("task", task.id)

        # Get the operation type and value
        operation = self.get_argument("operation", "")
        value = self.get_argument("value", "")

        # Collect selected testcase IDs from the request
        id_strings = self.get_arguments("testcase_id")

        if not id_strings:
            self.service.add_notification(
                make_datetime(),
                "No testcases selected",
                "Please select at least one testcase.",
            )
            self.redirect(fallback_page)
            return

        if operation not in ("add_prefix", "remove_substring"):
            self.service.add_notification(
                make_datetime(),
                "Invalid operation",
                "Unknown operation: %s" % operation,
            )
            self.redirect(fallback_page)
            return

        # Gather testcases
        testcases = []
        for id_str in id_strings:
            try:
                tid = int(id_str)
            except ValueError:
                raise tornado.web.HTTPError(400)
            tc = self.safe_get_item(Testcase, tid)

            # Protect against mixing datasets
            if tc.dataset is not dataset:
                raise tornado.web.HTTPError(400)

            testcases.append(tc)

        if operation == "add_prefix":
            # Add prefix to all selected testcases
            if not value:
                self.service.add_notification(
                    make_datetime(), "Invalid prefix", "Prefix cannot be empty."
                )
                self.redirect(fallback_page)
                return

            def add_prefix_modifier(tc):
                return (_add_prefix_if_missing(tc.codename, value), None)

            success, renamed_count = _batch_rename_testcases(
                self,
                dataset,
                task,
                testcases,
                add_prefix_modifier,
                fallback_page,
            )
            if not success:
                return

            # Check if user wants to update the subtask regex
            update_regex = self.get_argument("update_regex", "") == "true"
            regex_updated = False
            regex_already_exists = False
            if update_regex and subtask_index is not None:
                try:
                    subtask_idx = int(subtask_index)
                    score_type_obj = dataset.score_type_object
                    if hasattr(score_type_obj, "parameters"):
                        params = list(score_type_obj.parameters)
                        if 0 <= subtask_idx < len(params):
                            param = list(params[subtask_idx])
                            # Check if using regex (string pattern)
                            if len(param) >= 2 and isinstance(param[1], str):
                                old_regex = param[1]
                                # Add a term to match testcases containing the prefix
                                # Use .*prefix pattern to match substring
                                import re

                                new_term = ".*%s(?#CMS)" % re.escape(value)
                                # Check if the term already exists in the regex
                                if new_term in old_regex:
                                    regex_already_exists = True
                                else:
                                    # Combine with existing regex using |
                                    new_regex = "%s|%s" % (old_regex, new_term)
                                    param[1] = new_regex
                                    params[subtask_idx] = param
                                    dataset.score_type_parameters = params
                                    regex_updated = True
                except (ValueError, AttributeError, IndexError) as e:
                    logger.warning(
                        "Could not update regex for subtask %s: %s", subtask_index, e
                    )

            if self.try_commit():
                msg = "Added prefix '%s' to %d testcases." % (value, renamed_count)
                if regex_updated:
                    msg += (
                        " Subtask regex updated to match testcases containing '%s'."
                        % value
                    )
                elif regex_already_exists:
                    msg += " Regex term for '%s' already exists in the pattern." % value
                self.service.add_notification(make_datetime(), "Testcases renamed", msg)

        elif operation == "remove_substring":
            # Remove a common substring from all selected testcases
            substring = value

            if not substring:
                self.service.add_notification(
                    make_datetime(), "Invalid substring", "Substring cannot be empty."
                )
                self.redirect(fallback_page)
                return

            def remove_substring_modifier(tc):
                if substring not in tc.codename:
                    return (
                        None,
                        "Testcase '%s' does not contain substring '%s'."
                        % (tc.codename, substring),
                    )
                new_codename = tc.codename.replace(substring, "", 1)
                if not new_codename:
                    return (
                        None,
                        "Removing substring from '%s' would result in empty codename."
                        % tc.codename,
                    )
                return (new_codename, None)

            success, renamed_count = _batch_rename_testcases(
                self,
                dataset,
                task,
                testcases,
                remove_substring_modifier,
                fallback_page,
            )
            if not success:
                return

            if self.try_commit():
                self.service.add_notification(
                    make_datetime(),
                    "Testcases renamed",
                    "Removed substring '%s' from %d testcases." % (substring, renamed_count))

        self.redirect(fallback_page)


class ApplySubtaskPrefixesHandler(BaseHandler):
    """Apply STi_ prefixes to all testcases based on subtask membership.

    For each subtask i, sets the regex to .*STi_(?#CMS) and prepends
    STi_ to all testcases belonging to that subtask (sorted descending).

    Before applying new prefixes, all existing STi_ substrings are stripped
    from every testcase name so that re-running this operation after changing
    subtask regex/order produces correct results instead of accumulating
    stale prefixes.
    """

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, dataset_id):
        dataset = self.safe_get_item(Dataset, dataset_id)
        task = dataset.task
        fallback_page = self.url("task", task.id)

        from cms.grading.scoretypes import ScoreTypeGroup

        score_type_obj = dataset.score_type_object
        if not isinstance(score_type_obj, ScoreTypeGroup):
            self.service.add_notification(
                make_datetime(), "Not supported",
                "This operation requires a group-based score type.")
            self.redirect(fallback_page)
            return

        # Build testcase -> subtask mapping BEFORE stripping prefixes,
        # because score_type_obj.public_testcases holds the current
        # (pre-strip) codenames.  We key by testcase *id* so the mapping
        # survives Phase 1's rename.
        try:
            from cms.server.util import build_tc_to_subtasks_mapping

            tc_to_subtasks_by_name = build_tc_to_subtasks_mapping(
                score_type_obj)
        except (KeyError, ValueError, TypeError, re.error) as e:
            self.service.add_notification(
                make_datetime(), "Error",
                "Could not retrieve subtask info: %s" % str(e)
            )
            self.redirect(fallback_page)
            return

        # Translate codename-keyed mapping to testcase-id-keyed mapping
        tc_id_to_subtasks = {}
        for tc in dataset.testcases.values():
            subtask_indices = tc_to_subtasks_by_name.get(
                tc.codename, set())
            if subtask_indices:
                tc_id_to_subtasks[tc.id] = subtask_indices

        # Phase 1: Strip all existing STi_ prefixes from all testcase names.
        # This uses the existing remove_substring batch rename logic so that
        # re-running after adding/removing subtasks produces clean results.
        all_testcases = list(dataset.testcases.values())
        _ST_PREFIX_RE = re.compile(r"ST\d+_")

        def strip_st_modifier(tc):
            new_codename = _ST_PREFIX_RE.sub("", tc.codename)
            if not new_codename:
                # Shouldn't happen in practice, but guard against it
                return (tc.codename, None)
            return (new_codename, None)

        success, _ = _batch_rename_testcases(
            self, dataset, task, all_testcases, strip_st_modifier, fallback_page
        )
        if not success:
            return

        # Phase 2: Add STi_ prefixes based on subtask membership
        # Re-fetch testcases since codenames may have changed in phase 1
        all_testcases = list(dataset.testcases.values())

        def subtask_prefix_modifier(tc):
            subtask_indices = tc_id_to_subtasks.get(tc.id, set())
            new_codename = tc.codename
            for i in sorted(subtask_indices, reverse=True):
                new_codename = _add_prefix_if_missing(
                    new_codename, "ST%d_" % i)
            return (new_codename, None)

        success, renamed_count = _batch_rename_testcases(
            self, dataset, task, all_testcases,
            subtask_prefix_modifier, fallback_page)
        if not success:
            return

        # Override each subtask's regex to .*ST{i}_(?#CMS)
        params = [list(p) for p in score_type_obj.parameters]
        for idx in range(len(params)):
            params[idx][1] = ".*ST%d_(?#CMS)" % idx
        dataset.score_type_parameters = params

        if self.try_commit():
            self.service.add_notification(
                make_datetime(), "Subtask prefixes applied",
                "Applied subtask prefixes to %d testcases and updated "
                "%d subtask regexes." % (renamed_count, len(params)))

        self.redirect(fallback_page)
