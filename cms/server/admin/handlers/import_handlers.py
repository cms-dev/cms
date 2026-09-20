#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
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

"""Import handlers for AWS - allows importing tasks, contests and
training programs from zip files.

"""

import logging
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager

import yaml

from cmscommon.datetime import make_datetime
from cmscommon.zip import safe_extract_zip
from cmscontrib.ImportTask import TaskImporter
from cmscontrib.ImportContest import ContestImporter
from cmscontrib.importing import ImportDataError
from cmscontrib.loaders import choose_loader
from cmscontrib.loaders.base_loader import LoaderValidationError

from .base import BaseHandler, require_permission
from .dataset import validate_template
from .trainingprogram_transfer import TrainingProgramImporter, \
    load_training_program_yaml


logger = logging.getLogger(__name__)


@contextmanager
def _extract_uploaded_zip(uploaded_file, temp_prefix, zip_filename):
    """Write an uploaded zip to disk, extract it, and yield the root path."""
    temp_dir = tempfile.mkdtemp(prefix=temp_prefix)
    try:
        zip_path = os.path.join(temp_dir, zip_filename)
        with open(zip_path, "wb") as f:
            f.write(uploaded_file["body"])

        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            safe_extract_zip(zip_ref, extract_dir)

        contents = os.listdir(extract_dir)
        if len(contents) == 1 and \
                os.path.isdir(os.path.join(extract_dir, contents[0])):
            root_path = os.path.join(extract_dir, contents[0])
        else:
            root_path = extract_dir

        yield root_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _validate_zip_upload(handler, file_key, fallback_page):
    """Validate that a zip file was uploaded.

    Args:
        handler: The request handler instance.
        file_key: The form field name for the uploaded file.
        fallback_page: URL to redirect to on validation failure.

    Returns:
        The uploaded file dict if valid, None if validation failed
        (redirect already issued).
    """
    if file_key not in handler.request.files:
        handler.service.add_notification(
            make_datetime(),
            "No file uploaded",
            "Please select a zip file to upload.")
        handler.redirect(fallback_page)
        return None

    uploaded_file = handler.request.files[file_key][0]

    if not uploaded_file["filename"].lower().endswith(".zip"):
        handler.service.add_notification(
            make_datetime(),
            "Invalid file format",
            "The uploaded file must be a .zip file.")
        handler.redirect(fallback_page)
        return None

    return uploaded_file


def _setup_importer_with_notifier(importer, service):
    """Set up the notifier callback on an importer if supported.

    Args:
        importer: The importer instance (TaskImporter or ContestImporter).
        service: The service instance for adding notifications.
    """
    if hasattr(importer.loader, 'set_notifier'):
        def notify(title, text):
            service.add_notification(make_datetime(), title, text)
        importer.loader.set_notifier(notify)


def _handle_import_result(handler, success, entity_type, success_redirect,
                          fallback_page):
    """Handle the result of an import operation.

    Args:
        handler: The request handler instance.
        success: Whether the import succeeded.
        entity_type: "Task" or "Contest" for notification messages.
        success_redirect: URL to redirect to on success.
        fallback_page: URL to redirect to on failure.
    """
    if success:
        handler.service.add_notification(
            make_datetime(),
            f"{entity_type} imported successfully",
            "")
        handler.redirect(success_redirect)
    else:
        handler.service.add_notification(
            make_datetime(),
            f"{entity_type} import failed",
            "Import failed. Please check the logs for details.")
        handler.redirect(fallback_page)


def _handle_import_error(handler, error, entity_type, fallback_page,
                         log_error=False):
    """Handle an import error by notifying and redirecting.

    Args:
        handler: The request handler instance.
        error: The exception that occurred.
        entity_type: "Task" or "Contest" for notification messages.
        fallback_page: URL to redirect to on failure.
        log_error: If True, log the error with traceback.
    """
    if log_error:
        logger.error("%s import failed: %s", entity_type, error, exc_info=True)
    handler.service.add_notification(
        make_datetime(),
        f"{entity_type} import failed",
        str(error))
    handler.redirect(fallback_page)


def _inject_templates_into_yaml(task_path, input_template, output_template):
    """Inject input/output templates into task.yaml if not already present."""
    if not input_template and not output_template:
        return

    task_yaml_path = os.path.join(task_path, "task.yaml")
    if not os.path.exists(task_yaml_path):
        return

    try:
        with open(task_yaml_path, "r", encoding="utf-8") as f:
            task_config = yaml.safe_load(f) or {}

        if input_template and "input_template" not in task_config:
            task_config["input_template"] = input_template
        if output_template and "output_template" not in task_config:
            task_config["output_template"] = output_template

        with open(task_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(task_config, f, default_flow_style=False,
                      allow_unicode=True)
    except Exception as e:
        logger.warning("Failed to inject templates into task.yaml: %s", e)


class ImportTaskHandler(BaseHandler):
    """Handler for importing a task from a zip file.

    GET redirects to the tasks list (the old import_task.html page has
    been replaced by an inline modal on the tasks page).
    POST processes the uploaded zip archive.

    Model solutions found in the task archive are imported with default
    expected score ranges (0-100) if no metadata is provided in task.yaml.
    Admins can configure the expected ranges after import via the model
    solutions configuration page.
    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self):
        self.redirect(self.url("tasks"))

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = self.url("tasks")

        task_file = _validate_zip_upload(self, "task_file", fallback_page)
        if task_file is None:
            return

        update = bool(self.get_argument("update", False))
        no_statement = bool(self.get_argument("no_statement", False))
        contest_id_str = self.get_argument("contest_id", None)
        if contest_id_str and contest_id_str != "":
            contest_id = int(contest_id_str)
        else:
            contest_id = None
        loader_name = self.get_argument("loader", None)
        if loader_name == "":
            loader_name = None

        input_template = self.get_argument("input_template", "").strip()
        output_template = self.get_argument("output_template", "").strip()

        # Validate templates if provided
        if input_template:
            error = validate_template(input_template, "input")
            if error:
                self.service.add_notification(
                    make_datetime(), "Invalid template", error)
                self.redirect(fallback_page)
                return
        if output_template:
            error = validate_template(output_template, "output")
            if error:
                self.service.add_notification(
                    make_datetime(), "Invalid template", error)
                self.redirect(fallback_page)
                return

        try:
            with _extract_uploaded_zip(
                    task_file, "cms_import_task_", "task.zip") as task_path:
                # Inject templates if provided
                _inject_templates_into_yaml(
                    task_path, input_template, output_template)

                def error_callback(msg):
                    raise ValueError(msg)

                loader_class = choose_loader(
                    loader_name, task_path, error_callback)

                importer = TaskImporter(
                    path=task_path,
                    update=update,
                    no_statement=no_statement,
                    contest_id=contest_id,
                    prefix=None,
                    override_name=None,
                    loader_class=loader_class,
                    raise_import_errors=True
                )

                _setup_importer_with_notifier(importer, self.service)

                try:
                    success = importer.do_import()
                    if not success:
                        self.service.add_notification(
                            make_datetime(),
                            "Task import failed",
                            "Import failed. Please check the logs for details.")
                        self.redirect(fallback_page)
                        return

                    # Check if there are model solutions that need configuration
                    pending_ids = getattr(
                        importer, "model_solution_meta_ids_missing_metadata", [])
                    task_id = getattr(importer, "imported_task_id", None)

                    if pending_ids and task_id is not None:
                        # Redirect to configuration page for model solutions
                        # that were imported with defaults
                        ids_str = ",".join(str(i) for i in pending_ids)
                        self.service.add_notification(
                            make_datetime(),
                            "Task imported",
                            "Some model solutions need configuration.")
                        self.redirect(self.url(
                            "task", task_id, "model_solutions", "configure"
                        ) + f"?ids={ids_str}")
                    else:
                        self.service.add_notification(
                            make_datetime(),
                            "Task imported successfully",
                            "")
                        self.redirect(self.url("tasks"))
                except (LoaderValidationError, ImportDataError) as e:
                    _handle_import_error(self, e, "Task", fallback_page)

        except Exception as error:
            _handle_import_error(self, error, "Task", fallback_page,
                                 log_error=True)


class ImportContestHandler(BaseHandler):
    """Handler for importing a contest from a zip file.

    GET redirects to the contests list (the old import_contest.html page
    has been replaced by an inline modal on the contests page).
    POST processes the uploaded zip archive.
    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self):
        self.redirect(self.url("contests"))

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = self.url("contests")

        contest_file = _validate_zip_upload(self, "contest_file", fallback_page)
        if contest_file is None:
            return

        import_tasks = bool(self.get_argument("import_tasks", False))
        update_contest = bool(self.get_argument("update_contest", False))
        update_tasks = bool(self.get_argument("update_tasks", False))
        no_statements = bool(self.get_argument("no_statements", False))
        loader_name = self.get_argument("loader", None)
        if loader_name == "":
            loader_name = None

        try:
            with _extract_uploaded_zip(
                    contest_file, "cms_import_contest_", "contest.zip") \
                    as contest_path:
                def error_callback(msg):
                    raise ValueError(msg)

                loader_class = choose_loader(
                    loader_name, contest_path, error_callback)

                importer = ContestImporter(
                    path=contest_path,
                    yes=True,
                    zero_time=False,
                    import_tasks=import_tasks,
                    update_contest=update_contest,
                    update_tasks=update_tasks,
                    no_statements=no_statements,
                    delete_stale_participations=False,
                    loader_class=loader_class,
                    raise_import_errors=True
                )

                _setup_importer_with_notifier(importer, self.service)

                try:
                    success = importer.do_import()
                    _handle_import_result(
                        self, success, "Contest",
                        self.url("contests"), fallback_page)
                except (LoaderValidationError, ImportDataError) as e:
                    _handle_import_error(self, e, "Contest", fallback_page)

        except Exception as error:
            _handle_import_error(self, error, "Contest", fallback_page,
                                 log_error=True)


class ImportTrainingProgramHandler(BaseHandler):
    """Handler for importing a training program from a zip file produced
    by the training program exporter.

    The archive is a contest archive (managing contest and its tasks)
    plus training_program.yaml with students and archived training days.
    Everything is imported in a single transaction.
    """
    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self):
        self.redirect(self.url("training_programs"))

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self):
        fallback_page = self.url("training_programs")

        program_file = _validate_zip_upload(
            self, "training_program_file", fallback_page)
        if program_file is None:
            return

        no_statements = bool(self.get_argument("no_statements", False))

        def notify(title, text):
            self.service.add_notification(make_datetime(), title, text)

        try:
            with _extract_uploaded_zip(
                    program_file, "cms_import_training_program_",
                    "training_program.zip") as program_path:
                def error_callback(msg):
                    raise ValueError(msg)

                config = load_training_program_yaml(program_path)

                loader_class = choose_loader(
                    "italy_yaml", program_path, error_callback)

                importer = ContestImporter(
                    path=program_path,
                    yes=True,
                    zero_time=False,
                    import_tasks=True,
                    update_contest=False,
                    update_tasks=False,
                    no_statements=no_statements,
                    delete_stale_participations=False,
                    loader_class=loader_class,
                    raise_import_errors=True
                )

                _setup_importer_with_notifier(importer, self.service)

                tp_importer = TrainingProgramImporter(
                    self.sql_session, importer, config, notify)
                training_program = tp_importer.do_import()

            committed = self.try_commit()

        except (LoaderValidationError, ImportDataError) as error:
            self.sql_session.rollback()
            _handle_import_error(self, error, "Training program", fallback_page)
            return
        except Exception as error:
            self.sql_session.rollback()
            _handle_import_error(self, error, "Training program", fallback_page,
                                 log_error=True)
            return

        if not committed:
            self.redirect(fallback_page)
            return

        tp_importer.notify_skipped()
        importer.notify_model_solutions()
        try:
            self.service.proxy_service.reinitialize()
        except Exception:
            logger.exception("Proxy service reinitialization failed after "
                             "training program import")
        self.service.add_notification(
            make_datetime(),
            "Training program imported successfully",
            "")
        self.redirect(self.url("training_program", training_program.id))
