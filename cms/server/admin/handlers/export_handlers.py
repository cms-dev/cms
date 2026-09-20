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

"""Export handlers for AWS - allows exporting tasks, contests and
training programs to zip files in YamlLoader format.

"""

import logging
import os
import shutil
import tempfile
import zipfile

import yaml

from cms.db import Contest, Task, TrainingProgram
from cms.grading.languagemanager import SOURCE_EXTS, get_language
from cms.grading.tasktypes.util import get_allowed_manager_basenames
from cmscommon.datetime import make_datetime
from cmscontrib.loaders.base_loader import LANGUAGE_MAP

from .base import BaseHandler, require_permission
from .trainingprogram_transfer import build_training_program_config, \
    write_training_program_yaml


logger = logging.getLogger(__name__)

LANGUAGE_CODE_TO_NAME = {code: name for name, code in LANGUAGE_MAP.items()}


def _expand_codename_with_language(filename: str, language_name: str | None) -> str:
    """Expand %l placeholder in filename to actual source extension.

    filename: the filename, possibly ending with .%l
    language_name: the language name (e.g., "C++17 / g++"), or None

    return: the filename with .%l replaced by the actual extension,
            or the original filename if no expansion is possible.
    """
    if not filename.endswith(".%l") or not language_name:
        return filename
    try:
        language_obj = get_language(language_name)
    except KeyError:
        return filename
    extension = language_obj.source_extension
    if not extension:
        return filename
    return filename[:-3] + extension


def _zip_directory(src_dir: str, zip_path: str, base_dir: str) -> None:
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _dirs, files in os.walk(src_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, base_dir)
                zipf.write(file_path, arcname)


def _write_zip_response(handler: BaseHandler, zip_path: str, download_name: str) -> None:
    handler.set_header('Content-Type', 'application/zip')
    handler.set_header('Content-Disposition',
                      f'attachment; filename="{download_name}"')

    with open(zip_path, 'rb') as f:
        handler.write(f.read())

    handler.finish()


def _export_task_to_yaml_format(task, dataset, file_cacher, export_dir):
    """Export a task to YamlLoader (Italian YAML) format.

    task: Task object to export
    dataset: Dataset object to export (typically active_dataset)
    file_cacher: FileCacher instance for retrieving files
    export_dir: Directory to export to

    Creates the following structure:
    - task.yaml: Task configuration (including model_solutions section)
    - statements/: Statement PDFs
    - attachments/: Task attachments
    - tests.zip: Testcases (input/output pairs)
    - managers/: Manager files (checker, grader, etc.)
    - solutions/: Model solution source files (one subdirectory per solution)
    - generators/: Generator source files (if any)
    """

    statements_dir = os.path.join(export_dir, "statements")
    attachments_dir = os.path.join(export_dir, "attachments")
    managers_dir = os.path.join(export_dir, "managers")
    solutions_dir = os.path.join(export_dir, "solutions")

    os.makedirs(statements_dir, exist_ok=True)
    os.makedirs(attachments_dir, exist_ok=True)
    os.makedirs(managers_dir, exist_ok=True)

    for lang_code, statement in task.statements.items():
        lang_name = LANGUAGE_CODE_TO_NAME.get(lang_code, lang_code)
        statement_path = os.path.join(statements_dir, f"{lang_name}.pdf")
        file_cacher.get_file_to_path(statement.digest, statement_path)
        if statement.source_digest:
            if statement.source_extension:
                source_path = os.path.join(statements_dir, f"{lang_name}{statement.source_extension}")
            else:
                source_path = os.path.join(statements_dir, f"{lang_name}_source")
            file_cacher.get_file_to_path(statement.source_digest, source_path)

    for filename, attachment in task.attachments.items():
        attachment_path = os.path.join(attachments_dir, filename)
        file_cacher.get_file_to_path(attachment.digest, attachment_path)

    input_template = "input_*.txt"
    output_template = "output_*.txt"
    input_template_py = input_template.replace("*", "%s")
    output_template_py = output_template.replace("*", "%s")

    tests_zip_path = os.path.join(export_dir, "tests.zip")
    testcases = sorted(dataset.testcases.values(), key=lambda tc: tc.codename)
    with zipfile.ZipFile(tests_zip_path, 'w', zipfile.ZIP_DEFLATED) as tests_zip:
        for testcase in testcases:
            with tests_zip.open(input_template_py % testcase.codename, 'w') as fout:
                file_cacher.get_file_to_fobj(testcase.input, fout)
            with tests_zip.open(output_template_py % testcase.codename, 'w') as fout:
                file_cacher.get_file_to_fobj(testcase.output, fout)

    allowed_basenames = get_allowed_manager_basenames(dataset.task_type)
    manager_filenames = set(dataset.managers.keys())
    source_basenames = set()
    for filename in manager_filenames:
        basename, ext = os.path.splitext(filename)
        if ext in SOURCE_EXTS and basename in allowed_basenames:
            source_basenames.add(basename)

    for filename, manager in dataset.managers.items():
        basename, ext = os.path.splitext(filename)
        if basename in allowed_basenames and basename in source_basenames:
            if ext not in SOURCE_EXTS:
                continue
        manager_path = os.path.join(managers_dir, filename)
        file_cacher.get_file_to_path(manager.digest, manager_path)

    if task.primary_statements:
        primary_language = task.primary_statements[0]
    elif task.statements:
        # No statement marked as primary: fall back to the first
        # available statement language instead of assuming 'he'.
        primary_language = sorted(task.statements.keys())[0]
    else:
        primary_language = "he"

    task_config = {
        "name": task.name,
        "title": task.title,
        "primary_language": primary_language,
    }

    if dataset.description:
        task_config['version'] = dataset.description

    if task.submission_format:
        task_config['submission_format'] = task.submission_format

    if task.feedback_level:
        task_config['feedback_level'] = task.feedback_level

    if task.score_mode:
        task_config['score_mode'] = task.score_mode

    if task.allowed_languages is not None:
        task_config['allowed_languages'] = task.allowed_languages

    if task.token_mode:
        task_config['token_mode'] = task.token_mode
        if task.token_max_number is not None:
            task_config['token_max_number'] = task.token_max_number
        if task.token_min_interval is not None:
            task_config['token_min_interval'] = int(task.token_min_interval.total_seconds())
        if task.token_gen_initial is not None:
            task_config['token_gen_initial'] = task.token_gen_initial
        if task.token_gen_number is not None:
            task_config['token_gen_number'] = task.token_gen_number
        if task.token_gen_interval is not None:
            task_config['token_gen_interval'] = int(task.token_gen_interval.total_seconds())
        if task.token_gen_max is not None:
            task_config['token_gen_max'] = task.token_gen_max

    if task.max_submission_number is not None:
        task_config['max_submission_number'] = task.max_submission_number
    if task.max_user_test_number is not None:
        task_config['max_user_test_number'] = task.max_user_test_number
    if task.min_submission_interval is not None:
        task_config['min_submission_interval'] = int(task.min_submission_interval.total_seconds())
    if task.min_user_test_interval is not None:
        task_config['min_user_test_interval'] = int(task.min_user_test_interval.total_seconds())

    if task.score_precision is not None:
        task_config['score_precision'] = task.score_precision

    if dataset.time_limit is not None:
        task_config['time_limit'] = dataset.time_limit
    if dataset.memory_limit is not None:
        task_config['memory_limit'] = dataset.memory_limit // (1024 * 1024)

    if dataset.task_type:
        task_config['task_type'] = dataset.task_type
        if dataset.task_type_parameters:
            if dataset.task_type in ("Batch", "BatchAndOutput") and len(dataset.task_type_parameters) >= 3:
                # Export compilation parameter (alone/grader)
                task_config['compilation'] = dataset.task_type_parameters[0]
                task_config['infile'] = dataset.task_type_parameters[1][0]
                task_config['outfile'] = dataset.task_type_parameters[1][1]
                # Export output_eval parameter (diff/comparator/realprecision)
                task_config['output_eval'] = dataset.task_type_parameters[2]
                if len(dataset.task_type_parameters) >= 4 and dataset.task_type_parameters[2] == "realprecision":
                    task_config['exponent'] = dataset.task_type_parameters[3]
                if dataset.task_type == "BatchAndOutput":
                    output_only_testcases = dataset.task_type_parameters[-1]
                    if output_only_testcases:
                        task_config['output_only_testcases'] = output_only_testcases
            elif dataset.task_type == "OutputOnly" and len(dataset.task_type_parameters) >= 1:
                # Export output_eval parameter for OutputOnly
                task_config['output_eval'] = dataset.task_type_parameters[0]
                if len(dataset.task_type_parameters) >= 2 and dataset.task_type_parameters[0] == "realprecision":
                    task_config['exponent'] = dataset.task_type_parameters[1]
            elif dataset.task_type == "TwoSteps" and len(dataset.task_type_parameters) >= 1:
                # Export output_eval parameter for TwoSteps
                task_config['output_eval'] = dataset.task_type_parameters[0]
            elif dataset.task_type == "Communication" and len(dataset.task_type_parameters) >= 3:
                task_config['num_processes'] = dataset.task_type_parameters[0]
                # Export compilation parameter for Communication (alone/stub)
                task_config['compilation'] = dataset.task_type_parameters[1]
                task_config['user_io'] = dataset.task_type_parameters[2]

    if dataset.score_type:
        task_config['score_type'] = dataset.score_type
        if dataset.score_type_parameters is not None:
            task_config['score_type_parameters'] = dataset.score_type_parameters

    task_config['n_input'] = len(testcases)

    task_config['input_template'] = input_template
    task_config['output_template'] = output_template

    public_testcases = [tc.codename for tc in testcases if tc.public]
    if public_testcases:
        if len(public_testcases) == len(testcases):
            task_config['public_testcases'] = 'all'
        else:
            # Use codenames directly - the import side handles both codenames and indices
            task_config['public_testcases'] = ','.join(public_testcases)

    # Export model solutions
    if dataset.model_solution_metas:
        os.makedirs(solutions_dir, exist_ok=True)
        model_solutions_config = []

        for meta in dataset.model_solution_metas:
            submission = meta.submission
            solution_config = {
                'name': meta.name,
                'description': meta.description,
                'expected_score_min': meta.expected_score_min,
                'expected_score_max': meta.expected_score_max,
            }

            if submission.language:
                solution_config['language'] = submission.language

            if meta.subtask_expected_scores:
                solution_config['subtask_expected_scores'] = meta.subtask_expected_scores

            # Export solution files
            files_list = []
            solution_subdir = os.path.join(solutions_dir, meta.name)
            os.makedirs(solution_subdir, exist_ok=True)

            for file_obj in submission.files.values():
                # Expand %l placeholder to actual source extension
                filename = _expand_codename_with_language(
                    file_obj.filename, submission.language)

                file_path = os.path.join(solution_subdir, filename)
                file_cacher.get_file_to_path(file_obj.digest, file_path)
                files_list.append(filename)

            solution_config['files'] = files_list
            model_solutions_config.append(solution_config)

        if model_solutions_config:
            task_config['model_solutions'] = model_solutions_config

    # Export generators
    if dataset.generators:
        generators_dir = os.path.join(export_dir, "generators")
        os.makedirs(generators_dir, exist_ok=True)
        generators_config = []

        for filename, generator in dataset.generators.items():
            # Export generator source file
            generator_path = os.path.join(generators_dir, filename)
            file_cacher.get_file_to_path(generator.digest, generator_path)

            # Add generator metadata to config
            generator_config = {
                'filename': filename,
                'input_template': generator.input_filename_template,
                'output_template': generator.output_filename_template,
            }

            if generator.language_name:
                generator_config['language'] = generator.language_name

            generators_config.append(generator_config)

        if generators_config:
            task_config['generators'] = generators_config

    # Export subtask validators
    if dataset.subtask_validators:
        validators_dir = os.path.join(export_dir, "validators")
        os.makedirs(validators_dir, exist_ok=True)
        validators_config = []

        # First pass: detect filename collisions
        # Count how many validators use each filename
        filename_counts = {}
        for validator in dataset.subtask_validators.values():
            filename_counts[validator.filename] = \
                filename_counts.get(validator.filename, 0) + 1

        # Track used export filenames to handle edge cases
        used_export_filenames = set()

        # Sort by subtask_index for stable, deterministic output
        for subtask_index in sorted(dataset.subtask_validators.keys()):
            validator = dataset.subtask_validators[subtask_index]
            original_filename = validator.filename

            # Determine export filename
            if filename_counts[original_filename] > 1:
                # Collision detected - add subtask index suffix
                stem, ext = os.path.splitext(original_filename)
                export_filename = f"{stem}_st{subtask_index}{ext}"
            else:
                # No collision - use original filename
                export_filename = original_filename

            # Handle edge case: export_filename already used (e.g., someone
            # named their file "validator_st0.cpp" and there's a collision)
            if export_filename in used_export_filenames:
                stem, ext = os.path.splitext(original_filename)
                counter = 1
                while export_filename in used_export_filenames:
                    export_filename = f"{stem}_st{subtask_index}_{counter}{ext}"
                    counter += 1

            used_export_filenames.add(export_filename)

            # Export validator source file with the (possibly renamed) filename
            validator_path = os.path.join(validators_dir, export_filename)
            file_cacher.get_file_to_path(validator.digest, validator_path)

            # Add validator metadata to config (use export filename, not original)
            validator_config = {
                'filename': export_filename,
                'subtask_index': subtask_index,
            }
            validators_config.append(validator_config)

        if validators_config:
            task_config['validators'] = validators_config

    task_yaml_path = os.path.join(export_dir, "task.yaml")
    with open(task_yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(task_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _export_contest_to_yaml_format(contest, file_cacher, export_dir):
    """Export a contest to YamlLoader (Italian YAML) format.

    contest: Contest object to export
    file_cacher: FileCacher instance for retrieving files
    export_dir: Directory to export to

    Creates the following structure:
    - contest.yaml: Contest configuration
    - task1/: First task directory
    - task2/: Second task directory
    - ...
    """

    contest_config = {
        'name': contest.name,
        'description': contest.description,
    }

    if contest.allowed_localizations:
        contest_config['allowed_localizations'] = contest.allowed_localizations

    if contest.languages:
        contest_config['languages'] = contest.languages

    if contest.submissions_download_allowed is not None:
        contest_config['submissions_download_allowed'] = contest.submissions_download_allowed
    if contest.allow_questions is not None:
        contest_config['allow_questions'] = contest.allow_questions
    if contest.allow_user_tests is not None:
        contest_config['allow_user_tests'] = contest.allow_user_tests

    if contest.score_precision is not None:
        contest_config['score_precision'] = contest.score_precision

    if contest.block_hidden_participations is not None:
        contest_config['block_hidden_participations'] = contest.block_hidden_participations
    if contest.allow_password_authentication is not None:
        contest_config['allow_password_authentication'] = contest.allow_password_authentication
    if contest.allow_registration is not None:
        contest_config['allow_registration'] = contest.allow_registration
    if contest.ip_restriction is not None:
        contest_config['ip_restriction'] = contest.ip_restriction
    if contest.ip_autologin is not None:
        contest_config['ip_autologin'] = contest.ip_autologin

    if contest.token_mode:
        contest_config['token_mode'] = contest.token_mode
        if contest.token_max_number is not None:
            contest_config['token_max_number'] = contest.token_max_number
        if contest.token_min_interval is not None:
            contest_config['token_min_interval'] = int(contest.token_min_interval.total_seconds())
        if contest.token_gen_initial is not None:
            contest_config['token_gen_initial'] = contest.token_gen_initial
        if contest.token_gen_number is not None:
            contest_config['token_gen_number'] = contest.token_gen_number
        if contest.token_gen_interval is not None:
            contest_config['token_gen_interval'] = int(contest.token_gen_interval.total_seconds())
        if contest.token_gen_max is not None:
            contest_config['token_gen_max'] = contest.token_gen_max

    if contest.start is not None:
        contest_config['start'] = contest.start.timestamp()
    if contest.stop is not None:
        contest_config['stop'] = contest.stop.timestamp()
    if contest.timezone:
        contest_config['timezone'] = contest.timezone
    if contest.per_user_time is not None:
        contest_config['per_user_time'] = int(contest.per_user_time.total_seconds())

    if contest.max_submission_number is not None:
        contest_config['max_submission_number'] = contest.max_submission_number
    if contest.max_user_test_number is not None:
        contest_config['max_user_test_number'] = contest.max_user_test_number
    if contest.min_submission_interval is not None:
        contest_config['min_submission_interval'] = int(contest.min_submission_interval.total_seconds())
    if contest.min_user_test_interval is not None:
        contest_config['min_user_test_interval'] = int(contest.min_user_test_interval.total_seconds())

    if contest.analysis_enabled is not None:
        contest_config['analysis_enabled'] = contest.analysis_enabled
    if contest.analysis_start is not None:
        contest_config['analysis_start'] = contest.analysis_start.timestamp()
    if contest.analysis_stop is not None:
        contest_config['analysis_stop'] = contest.analysis_stop.timestamp()

    # Use get_tasks() to support training days which have tasks separate from contest.tasks
    tasks = contest.get_tasks()
    if tasks:
        contest_config['tasks'] = [task.name for task in tasks]

    contest_yaml_path = os.path.join(export_dir, "contest.yaml")
    with open(contest_yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(contest_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    for task in tasks:
        task_dir = os.path.join(export_dir, task.name)
        os.makedirs(task_dir, exist_ok=True)

        dataset = task.active_dataset
        if dataset is None:
            logger.warning("Task %s has no active dataset, skipping", task.name)
            continue

        _export_task_to_yaml_format(task, dataset, file_cacher, task_dir)


class ExportTaskHandler(BaseHandler):
    """Handler for exporting a task to a zip file in YamlLoader format.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, task_id):
        task = self.safe_get_item(Task, task_id)

        if task.active_dataset is None:
            self.service.add_notification(
                make_datetime(),
                "Export failed",
                "Task has no active dataset to export.")
            self.redirect(self.url("task", task_id))
            return

        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="cms_export_task_")

            task_dir = os.path.join(temp_dir, task.name)
            os.makedirs(task_dir)

            _export_task_to_yaml_format(
                task,
                task.active_dataset,
                self.service.file_cacher,
                task_dir
            )

            zip_path = os.path.join(temp_dir, f"{task.name}.zip")
            _zip_directory(task_dir, zip_path, temp_dir)
            _write_zip_response(self, zip_path, f"{task.name}.zip")

        except Exception as error:
            logger.error("Task export failed: %s", error, exc_info=True)
            self.service.add_notification(
                make_datetime(),
                "Task export failed",
                str(error))
            self.redirect(self.url("task", task_id))

        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


class ExportContestHandler(BaseHandler):
    """Handler for exporting a contest or training program to a zip file.

    Supports both contest and training_program entity types via URL pattern:
    - /contest/{id}/export
    - /training_program/{id}/export

    For training programs, exports all tasks from the managing contest
    plus a training_program.yaml with students, archived training days
    and their ranking and attendance data.
    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, entity_type: str, entity_id: str):
        # Determine the contest and export name based on entity type
        training_program = None
        if entity_type == "training_program":
            training_program = self.safe_get_item(TrainingProgram, entity_id)
            contest = training_program.managing_contest
            export_name = training_program.name
            fallback_url = self.url("training_program", entity_id)
            error_prefix = "Training program"
        else:
            contest = self.safe_get_item(Contest, entity_id)
            export_name = contest.name
            fallback_url = self.url("contest", entity_id)
            error_prefix = "Contest"

        if training_program is not None:
            missing = [task.name for task in contest.tasks
                       if task.active_dataset is None]
            if missing:
                self.service.add_notification(
                    make_datetime(),
                    f"{error_prefix} export failed",
                    "Tasks without an active dataset cannot be exported: "
                    + ", ".join(missing))
                self.redirect(fallback_url)
                return

        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="cms_export_")

            contest_dir = os.path.join(temp_dir, export_name)
            os.makedirs(contest_dir)

            _export_contest_to_yaml_format(
                contest,
                self.service.file_cacher,
                contest_dir
            )

            if training_program is not None:
                config, skipped_days = build_training_program_config(
                    training_program)
                write_training_program_yaml(config, contest_dir)
                if skipped_days:
                    self.service.add_notification(
                        make_datetime(),
                        "Active training days not exported",
                        "Only archived training days are exported. "
                        "Skipped: " + ", ".join(
                            td.contest.name for td in skipped_days))

            zip_path = os.path.join(temp_dir, f"{export_name}.zip")
            _zip_directory(contest_dir, zip_path, temp_dir)
            _write_zip_response(self, zip_path, f"{export_name}.zip")

        except Exception as error:
            logger.error("%s export failed: %s", error_prefix, error, exc_info=True)
            self.service.add_notification(
                make_datetime(),
                f"{error_prefix} export failed",
                str(error))
            self.redirect(fallback_url)

        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
