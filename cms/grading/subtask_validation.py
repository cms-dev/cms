#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2024 IOI-ISR
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

"""Subtask validator execution logic.

This module contains the core logic for running subtask validators,
including background execution with proper cancellation support.
The handlers that use this logic are in cms/server/admin/handlers/.
"""

import errno
import logging

import gevent
from gevent.lock import RLock
from gevent.pool import Pool

from cms import config
from cms.db import Dataset, Session, SubtaskValidationResult, SubtaskValidator
from cms.grading.tasktypes.util import create_sandbox
from cms.grading.languagemanager import filename_to_language
from cms.grading.language import CompiledLanguage
from cms.grading.steps import safe_get_str
from cmscommon.datetime import make_datetime


logger = logging.getLogger(__name__)


# Track running validation jobs by validator_id
# Maps validator_id to the greenlet running the validation.
# Entries are removed when validation completes (success, error, or cancellation).
_running_validations: dict[int, gevent.Greenlet] = {}
_running_validations_lock = RLock()

# Global concurrency limiter for validator operations
# Configurable: maximum number of validators running concurrently
# Adjust this value based on system resources and typical validator load
# Higher values = more parallel validation but higher resource usage
# Lower values = less resource contention but slower overall validation
_VALIDATOR_CONCURRENCY_LIMIT = 8
_validator_pool = Pool(size=_VALIDATOR_CONCURRENCY_LIMIT)

# Number of times to retry a testcase execution when "Text file busy" is
# detected (ETXTBSY from execve). This transient error occurs when many
# validators run concurrently and the kernel hasn't finished closing the
# file after it was written to the sandbox.
_TEXT_FILE_BUSY_MAX_RETRIES = 3
_TEXT_FILE_BUSY_RETRY_DELAY = 0.3


def _is_text_file_busy_error(exc):
    """Check if an exception is related to ETXTBSY (text file busy)."""
    if isinstance(exc, OSError) and exc.errno in (errno.ETXTBSY, errno.EBUSY):
        return True
    return "text file busy" in str(exc).lower()


def set_sandbox_resource_limits(sandbox):
    """Set resource limits for a sandbox to prevent runaway processes.

    This function applies the same resource limits used for generators
    to validators and other sandboxed processes to ensure consistency
    and prevent system resource exhaustion.

    Args:
        sandbox: The sandbox object to configure
    """
    sandbox.timeout = config.sandbox.trusted_sandbox_max_time_s
    sandbox.wallclock_timeout = config.sandbox.trusted_sandbox_max_time_s * 2
    sandbox.address_space = \
        config.sandbox.trusted_sandbox_max_memory_kib * 1024
    sandbox.max_processes = config.sandbox.trusted_sandbox_max_processes


def get_running_validator_ids() -> set[int]:
    """Return set of validator IDs that are currently running.

    This is used by the UI to show "Validating..." status.
    """
    with _running_validations_lock:
        return set(_running_validations.keys())


def is_validator_running(validator_id: int) -> bool:
    """Check if a specific validator is currently running."""
    with _running_validations_lock:
        return validator_id in _running_validations


def cancel_validator(validator_id: int) -> bool:
    """Cancel a running validator.

    This function does NOT wait for the greenlet to finish. Instead, it:
    1. Removes the validator from the tracking dict
    2. Calls kill() to schedule GreenletExit (will be raised at next yield)

    The old greenlet will check _check_if_cancelled() and stop processing
    since its entry has been removed.

    Returns True if the validator was running and was cancelled,
    False if it wasn't running.
    """
    with _running_validations_lock:
        if validator_id not in _running_validations:
            return False

        greenlet = _running_validations.pop(validator_id)
        if greenlet is not None and not greenlet.dead:
            # Schedule GreenletExit to be raised in the old greenlet
            # This is non-blocking - the exception will be raised at the next yield
            greenlet.kill(block=False)
            return True

    return False


def _create_sandbox_with_retry(
    file_cacher, name="admin_validate", max_retries=3, retry_delay=0.5
):
    """Create a sandbox with retry logic to handle isolate state issues.

    When a greenlet is cancelled mid-execution, the isolate sandbox may be
    left in a bad state. This function retries sandbox creation with delays
    to allow isolate to recover.
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return create_sandbox(file_cacher, name=name)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.debug(
                    "Sandbox creation failed (attempt %d/%d): %s, retrying...",
                    attempt + 1, max_retries, e)
                gevent.sleep(retry_delay)
            else:
                logger.warning(
                    "Sandbox creation failed after %d attempts: %s",
                    max_retries, e)
    raise last_error


def _run_validator(file_cacher, filename, executable_digest, testcase_data):
    """Run a validator against testcases and return validation results.

    This is the shared core logic for running validators in background.
    All validation runs through run_validator_in_background which spawns
    a greenlet to execute this function.

    Args:
        file_cacher: FileCacher instance for accessing stored files
        filename: Validator source filename (used to determine language)
        executable_digest: Digest of the compiled validator executable
        testcase_data: List of dicts with keys: id, input, output

    Returns:
        List of dicts with keys: testcase_id, passed, exit_status, exit_code, stderr
        - passed: True if validator ran successfully and returned exit code 0
        - exit_status: Sandbox exit status ('ok', 'timeout', 'signal', etc.)
        - exit_code: Exit code from validator (when exit_status is 'ok' or 'nonzero return')
        Raises Exception on error (caller handles notification/logging)
    """
    language = filename_to_language(filename)

    exe_name = "validator"
    if language is not None and isinstance(language, CompiledLanguage):
        exe_name += language.executable_extension

    # Build command once outside the loop - same for all testcases
    cmd = ["./" + exe_name, "input.txt", "output.txt"]
    if language is not None:
        try:
            cmds = language.get_evaluation_commands(exe_name)
            if cmds:
                cmd = cmds[0] + ["input.txt", "output.txt"]
        except Exception as e:
            logger.debug(
                "get_evaluation_commands failed for validator %s: %s, using default",
                filename, e)

    validation_results = []
    sandbox = None

    try:
        for tc_data in testcase_data:
            # Check for cancellation between testcases
            gevent.sleep(0)

            passed = False
            exit_status = None
            exit_code = None
            stderr = None

            for attempt in range(_TEXT_FILE_BUSY_MAX_RETRIES + 1):
                sandbox = _create_sandbox_with_retry(file_cacher)

                try:
                    sandbox.create_file_from_storage(
                        exe_name, executable_digest, executable=True
                    )
                    sandbox.create_file_from_storage("input.txt", tc_data["input"])
                    sandbox.create_file_from_storage("output.txt", tc_data["output"])

                    set_sandbox_resource_limits(sandbox)

                    sandbox.stdin_file = "input.txt"
                    sandbox.stdout_file = "stdout.txt"
                    sandbox.stderr_file = "stderr.txt"

                    box_success = sandbox.execute_without_std(cmd, wait=True)
                except Exception as exc:
                    if (
                        _is_text_file_busy_error(exc)
                        and attempt < _TEXT_FILE_BUSY_MAX_RETRIES
                    ):
                        logger.info(
                            "Text file busy (exception) for testcase "
                            "%s (attempt %d/%d), retrying...",
                            tc_data["id"],
                            attempt + 1,
                            _TEXT_FILE_BUSY_MAX_RETRIES + 1,
                        )
                        try:
                            sandbox.cleanup(delete=True)
                        except Exception as cleanup_error:
                            logger.debug(
                                "Sandbox cleanup error (non-fatal): %s", cleanup_error
                            )
                        sandbox = None
                        gevent.sleep(_TEXT_FILE_BUSY_RETRY_DELAY * (attempt + 1))
                        continue
                    raise

                stderr = safe_get_str(sandbox, "stderr.txt")

                if box_success:
                    exit_status = sandbox.get_exit_status()
                    exit_code = sandbox.get_exit_code()
                    if exit_status == sandbox.EXIT_OK and exit_code == 0:
                        passed = True
                    elif exit_status == sandbox.EXIT_NONZERO_RETURN:
                        passed = False
                else:
                    exit_status = "sandbox error"

                # Cleanup sandbox before potential retry
                try:
                    sandbox.cleanup(delete=True)
                except Exception as cleanup_error:
                    logger.debug(
                        "Sandbox cleanup error (non-fatal): %s", cleanup_error)
                sandbox = None

                # Detect "Text file busy" (ETXTBSY) and retry
                if (stderr and "text file busy" in stderr.lower()
                        and attempt < _TEXT_FILE_BUSY_MAX_RETRIES):
                    logger.info(
                        "Text file busy for testcase %s (attempt %d/%d), "
                        "retrying...",
                        tc_data["id"], attempt + 1,
                        _TEXT_FILE_BUSY_MAX_RETRIES + 1)
                    gevent.sleep(
                        _TEXT_FILE_BUSY_RETRY_DELAY * (attempt + 1))
                    continue

                break

            validation_results.append(
                {
                    "testcase_id": tc_data["id"],
                    "passed": passed,
                    "exit_status": exit_status,
                    "exit_code": exit_code,
                    "stderr": stderr or None,
                }
            )

    finally:
        if sandbox:
            try:
                sandbox.cleanup(delete=True)
            except Exception:
                logger.debug("Final sandbox cleanup failed (non-fatal)")

    return validation_results


def _store_validation_results(sql_session, validator, dataset, validation_results):
    """Store validation results in the database, replacing any existing results.

    Args:
        sql_session: SQLAlchemy session
        validator: SubtaskValidator instance
        dataset: Dataset instance
        validation_results: List of dicts with keys: testcase_id, passed,
                           exit_status, exit_code, stderr

    Returns:
        Tuple of (passed_count, failed_count, error_count)
    """
    # Bulk delete existing results for this validator
    sql_session.query(SubtaskValidationResult).filter(
        SubtaskValidationResult.validator_id == validator.id
    ).delete(synchronize_session=False)
    sql_session.flush()

    testcase_ids = {r["testcase_id"] for r in validation_results}
    testcases_by_id = {tc.id: tc for tc in dataset.testcases.values()
                      if tc.id in testcase_ids}

    for result_data in validation_results:
        testcase = testcases_by_id.get(result_data["testcase_id"])
        if testcase is None:
            continue
        result = SubtaskValidationResult(
            validator=validator,
            testcase=testcase,
            passed=result_data["passed"],
            exit_status=result_data.get("exit_status"),
            exit_code=result_data.get("exit_code"),
            stderr=result_data["stderr"]
        )
        sql_session.add(result)

    passed_count = 0
    failed_count = 0
    error_count = 0
    for r in validation_results:
        exit_status = r.get("exit_status")
        if r["passed"]:
            passed_count += 1
        elif exit_status in ("ok", "nonzero return"):
            # Validator ran to completion but returned non-zero
            failed_count += 1
        else:
            # Validator had an error (timeout, signal, sandbox error, None, etc.)
            error_count += 1
    return passed_count, failed_count, error_count


def _clear_running_validation(validator_id):
    """Remove a validator from the running validations dict.

    Only removes if the current greenlet is the active one for this validator.
    This prevents a cancelled/replaced greenlet from removing the entry
    of a newly started greenlet.
    """
    with _running_validations_lock:
        if validator_id not in _running_validations:
            return

        # Only allow the current greenlet to remove the entry.
        # If the greenlet in the dict is different, it means we have been
        # replaced/cancelled and a new job has started.
        if _running_validations[validator_id] == gevent.getcurrent():
            del _running_validations[validator_id]


def _check_if_cancelled(validator_id):
    """Check if a validator has been cancelled. Returns True if cancelled.

    Returns True if the entry has been removed from _running_validations
    (meaning we've been cancelled) or if the current greenlet is not the
    active one for this validator (meaning we've been replaced by a new run).
    """
    with _running_validations_lock:
        if validator_id not in _running_validations:
            return True  # If record is gone, we've been cancelled

        # If I am not the active greenlet, I am effectively cancelled
        if _running_validations[validator_id] != gevent.getcurrent():
            return True

        return False


def _run_single_validator_task(service, file_cacher, validator_id, dataset_id,
                               filename, executable_digest, subtask_index,
                               testcase_data, send_notification=True):
    """Run a single validator and store results.

    This function is the core validation task that runs in a greenlet.
    It handles validation, database storage, and error handling.

    Args:
        service: The service object for notifications
        file_cacher: FileCacher for accessing files
        validator_id: ID of the validator to run
        dataset_id: ID of the dataset
        filename: Validator filename
        executable_digest: Digest of the compiled validator
        subtask_index: Index of the subtask being validated
        testcase_data: List of testcase dicts with id, input, output
        send_notification: Whether to send notifications (default True)

    Returns:
        Tuple of (passed_count, failed_count, error_count, error_message)
        where error_message is None on success or a string on error.
    """
    try:
        # Check if cancelled before starting
        if _check_if_cancelled(validator_id):
            return (0, 0, 0, None)

        validation_results = _run_validator(
            file_cacher, filename, executable_digest, testcase_data)

    except gevent.GreenletExit:
        # Greenlet was killed - this is expected for cancellation
        logger.info("Validator %d was cancelled", validator_id)
        return (0, 0, 0, None)

    except Exception as error:
        logger.exception("Validation execution error for validator %d",
                         validator_id)
        _clear_running_validation(validator_id)
        if send_notification:
            service.add_notification(
                make_datetime(), "Validation error",
                "Validator for subtask %d failed: %s" % (subtask_index, repr(error)))
        return (0, 0, 0, "Validator %d: %s" % (subtask_index, repr(error)))

    # Check if cancelled before storing results
    if _check_if_cancelled(validator_id):
        return (0, 0, 0, None)

    sql_session = Session()
    try:
        validator = sql_session.query(SubtaskValidator).get(validator_id)
        if validator is None:
            _clear_running_validation(validator_id)
            return (0, 0, 0, None)

        dataset = sql_session.query(Dataset).get(dataset_id)
        if dataset is None:
            _clear_running_validation(validator_id)
            return (0, 0, 0, "Validator %d: Dataset not found" % subtask_index)

        passed_count, failed_count, error_count = _store_validation_results(
            sql_session, validator, dataset, validation_results)

        sql_session.commit()

        msg = "Subtask %d: %d passed, %d failed" % (subtask_index, passed_count, failed_count)
        if error_count > 0:
            msg += ", %d errors" % error_count

        _clear_running_validation(validator_id)

        if send_notification:
            service.add_notification(make_datetime(), "Validation complete", msg)

        return (passed_count, failed_count, error_count, None)

    except gevent.GreenletExit:
        # Greenlet was killed during database operations
        logger.info("Validator %d was cancelled during DB operations", validator_id)
        sql_session.rollback()
        return (0, 0, 0, None)

    except Exception as error:
        logger.exception("Database error for validator %d",
                         validator_id)
        _clear_running_validation(validator_id)
        sql_session.rollback()
        if send_notification:
            service.add_notification(
                make_datetime(), "Validation error",
                "Database error for subtask %d: %s" % (subtask_index, repr(error)))
        return (0, 0, 0, "Validator %d DB error: %s" % (subtask_index, repr(error)))
    finally:
        sql_session.close()


def run_validator_in_background(service, file_cacher, validator_id, dataset_id,
                                filename, executable_digest, subtask_index,
                                testcase_data, send_notification=True):
    """Start a validator running in the background.

    If the validator is already running, it will be cancelled first and
    a new run will be started.

    Args:
        service: The service object for notifications
        file_cacher: FileCacher for accessing files
        validator_id: ID of the validator to run
        dataset_id: ID of the dataset
        filename: Validator filename
        executable_digest: Digest of the compiled validator
        subtask_index: Index of the subtask being validated
        testcase_data: List of testcase dicts with id, input, output
        send_notification: Whether to send notifications (default True)

    """
    # Cancel any existing run for this validator
    cancel_validator(validator_id)

    # Build the (unstarted) greenlet up front so we can register it while
    # holding the lock, but start it through the pool *outside* the lock.
    #
    # Starting a greenlet through the pool blocks when the pool is full
    # (_VALIDATOR_CONCURRENCY_LIMIT greenlets already running). Running
    # validators need _running_validations_lock to deregister themselves when
    # they finish (see _clear_running_validation), which is how they free
    # their pool slot. If we held the lock while the pool blocked waiting for
    # a slot, those greenlets could never deregister, the pool would never
    # free a slot, and the process would deadlock. This happened whenever more
    # than _VALIDATOR_CONCURRENCY_LIMIT validators were launched together,
    # e.g. "Rerun validators" with 9 validators and a limit of 8.
    greenlet = gevent.Greenlet(
        _run_single_validator_task,
        service,
        file_cacher,
        validator_id,
        dataset_id,
        filename,
        executable_digest,
        subtask_index,
        testcase_data,
        send_notification,
    )

    # Register the greenlet atomically before starting it.
    with _running_validations_lock:
        # Double-check that no other greenlet started while we were waiting
        if validator_id in _running_validations:
            return
        _running_validations[validator_id] = greenlet

    # Start the greenlet through the pool *without* holding the lock, from a
    # detached greenlet. _validator_pool.start blocks until a slot is free once
    # the pool is full; dispatching it from a detached greenlet keeps that wait
    # off the caller, so the "Rerun validators" handler (which loops over every
    # validator) can return promptly instead of blocking on the last launches.
    # The pool still bounds concurrency to _VALIDATOR_CONCURRENCY_LIMIT, and
    # because the lock is released before the wait, running validators can
    # deregister and free their slots, so the pool cannot deadlock.
    gevent.spawn(_validator_pool.start, greenlet)
