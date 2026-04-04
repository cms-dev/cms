#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Luca Versari <veluca93@gmail.com>
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


import json
import logging
import os
import sys
from functools import reduce

from cms.grading.Sandbox import Sandbox, wait_without_std
from cms.grading.steps.evaluation import (
    evaluation_step_before_run,
    evaluation_step_after_run,
    human_evaluation_message,
)
from cms.grading.steps.stats import merge_execution_stats
from cms.grading.steps import trusted_step

# Note: we keep a separate interactive keeper (running in a separate
# process) to avoid opening many file descriptors in the main worker.
# This both makes cleanup easier, and avoids potential deadlocks if
# there ever happen to be multiple threads in the worker and one of
# those threads fork()s at the wrong moment.

# Configure logging to stderr for critical errors only
logger = logging.getLogger("interactive_keeper")


def get_controller_text(sandbox):
    score = None
    text = []
    admin_text = None
    with sandbox.get_file_text("stderr.txt") as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith("SCORE: "):
                assert score is None
                score = float(line[len("SCORE: ") :].strip())
            elif line.startswith("USER_MESSAGE: "):
                assert not text
                text = [line[len("USER_MESSAGE: ") :].strip()]
            elif line.startswith("ADMIN_MESSAGE: "):
                assert admin_text is None
                admin_text = line[len("ADMIN_MESSAGE: ") :].strip()
            else:
                raise ValueError(f"Unknown controller feedback command {f}")

    return score, text, admin_text


def main():
    config = json.loads(sys.argv[1])

    controller_command = config["controller_command"]
    solution_commands = config["solution_commands"]
    controller_files = config["controller_files"]
    solution_files = config["solution_files"]
    controller_wall_limit = config.get("controller_wall_limit")
    controller_time_limit = config.get("controller_time_limit")
    controller_memory_limit = config.get("controller_memory_limit")
    solution_time_limit = config.get("solution_time_limit")
    solution_memory_limit = config.get("solution_memory_limit")
    process_limit = config.get("process_limit")
    concurrent = config.get("concurrent")
    temp_dir = config.get("temp_dir")
    shard = config.get("shard")
    delete_sandbox = config.get("delete_sandbox")

    pipes = []
    for i in range(process_limit):
        c_to_u_r, c_to_u_w = os.pipe()
        u_to_c_r, u_to_c_w = os.pipe()
        os.set_inheritable(c_to_u_r, True)
        os.set_inheritable(c_to_u_w, True)
        os.set_inheritable(u_to_c_r, True)
        os.set_inheritable(u_to_c_w, True)
        pipes.append({"c_to_u": (c_to_u_r, c_to_u_w), "u_to_c": (u_to_c_r, u_to_c_w)})

    controller_sandbox = Sandbox(0, shard, name="controller", temp_dir=temp_dir)
    for path in controller_files:
        with controller_sandbox.create_file(path, executable=True) as f:
            with open(os.path.join(temp_dir, path), "rb") as g:
                f.write(g.read())

    controller_proc = evaluation_step_before_run(
        controller_sandbox,
        controller_command,
        time_limit=controller_time_limit,
        memory_limit=controller_memory_limit,
        wall_limit=controller_wall_limit,
        stdin_redirect=None,
        stdout_redirect=None,
        multiprocess=True,
        close_fds=False,
        wait=False,
    )

    assert not isinstance(controller_proc, bool)

    for p in pipes:
        os.close(p["c_to_u"][1])
        os.close(p["u_to_c"][0])

    next_process_index = 0
    solution_sandboxes = []
    solution_procs = []

    while True:
        line = controller_proc.stdout.readline()
        if not line:
            break
        line = line.decode("utf-8").strip()
        if line == "START_SOLUTION":
            if next_process_index >= process_limit:
                break

            p = pipes[next_process_index]
            sandbox_sol = Sandbox(
                1 + next_process_index,
                shard,
                name="solution_%d" % next_process_index,
                temp_dir=temp_dir,
            )
            for path in solution_files:
                with sandbox_sol.create_file(path, executable=True) as f:
                    with open(os.path.join(temp_dir, path), "rb") as g:
                        f.write(g.read())

            # Matches Communication's handling of multi-command executions.
            if len(solution_commands) > 1:
                trusted_step(sandbox_sol, solution_commands[:-1])
            sol_proc = evaluation_step_before_run(
                sandbox_sol,
                solution_commands[-1],
                time_limit=solution_time_limit,
                memory_limit=solution_memory_limit,
                stdin_redirect=p["c_to_u"][0],
                stdout_redirect=p["u_to_c"][1],
                multiprocess=False,
                close_fds=False,
                wait=False,
            )

            os.close(p["c_to_u"][0])
            os.close(p["u_to_c"][1])

            try:
                controller_proc.stdin.write(
                    ("%d %d\n" % (p["c_to_u"][1], p["u_to_c"][0])).encode("utf-8")
                )
                controller_proc.stdin.flush()
            except BrokenPipeError:
                # If the controller dies before we can write back the pipes,
                # the keeper should not die.
                pass

            solution_sandboxes.append(sandbox_sol)
            solution_procs.append(sol_proc)
            next_process_index += 1
        else:
            result = {
                "success": False,
                "outcome": 0.0,
                "text": "Invalid command from controller: " + line,
                "admin_text": None,
                "stats": None,
            }
            print(json.dumps(result), flush=True)
            sys.exit(0)

    # Close controller pipes explicitly before result collection
    if controller_proc.stdin:
        controller_proc.stdin.close()
    if controller_proc.stdout:
        controller_proc.stdout.close()

    # Wait for all the sandboxes to exit before collecting results.
    wait_without_std([controller_proc] + solution_procs)

    success_mgr, evaluation_success_mgr, stats_mgr = evaluation_step_after_run(
        controller_sandbox
    )

    print(success_mgr, evaluation_success_mgr, stats_mgr, file=sys.stderr)

    user_results = [evaluation_step_after_run(s) for s in solution_sandboxes]
    box_success_user = all(r[0] for r in user_results)
    evaluation_success_user = all(r[1] for r in user_results)

    valid_stats = [r[2] for r in user_results if r[2] is not None]

    def do_merge(a, b):
        return merge_execution_stats(a, b, concurrent=concurrent)

    if valid_stats:
        stats_user = reduce(do_merge, valid_stats)
    else:
        stats_user = {
            "execution_time": 0.0,
            "execution_memory": 0,
            "execution_wall_clock_time": 0.0,
            "exit_status": "ok",
        }

    outcome = None
    text = None
    admin_text = None
    success = True

    try:
        score, controller_text, admin_text = get_controller_text(controller_sandbox)
    except Exception as e:
        success = False
        text = ["Internal error"]
        admin_text = [f"Internal error: {e}"]

    if not success:
        pass
    elif not (success_mgr and box_success_user):
        success = False
    else:
        if not evaluation_success_user:
            outcome = 0.0
            text = human_evaluation_message(stats_user)
            if controller_text:
                text = (
                    [controller_text[0] + f" (may be caused by {text[0]})"]
                    + controller_text[1:]
                    + text[1:]
                )
        elif not evaluation_success_mgr:
            outcome = 0.0
            text = ["Controller failed"] + (controller_text if controller_text else [])
        else:
            outcome = score if score is not None else 0.0
            text = controller_text

    result = {
        "success": success,
        "outcome": outcome,
        "text": text,
        "admin_text": admin_text,
        "stats": stats_user,
    }
    # Communicate results back to the worker
    print(json.dumps(result), flush=True)

    controller_sandbox.cleanup(delete=delete_sandbox)
    for s in solution_sandboxes:
        s.cleanup(delete=delete_sandbox)


if __name__ == "__main__":
    main()
