import json
import os
import signal
import sys
from textwrap import dedent
from time import sleep
from typing import List

import pycurl

from pcs.cli.reports.processor import print_report
from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
    TaskIdentDto,
    TaskResultDto,
)
from pcs.common.async_tasks.types import (
    TaskFinishType,
    TaskState,
)
from pcs.common.interface.dto import (
    from_dict,
    to_dict,
)
from pcs.common.node_communicator import (
    HostNotFound,
    NodeTargetFactory,
)
from pcs.common.reports import ReportItemDto
from pcs.utils import read_known_hosts_file

task_ident = ""
report_list: List[ReportItemDto] = []
kill_requested = False


def get_token_for_localhost() -> str:
    try:
        return (
            NodeTargetFactory(read_known_hosts_file())
            .get_target("localhost")
            .token
        )
    except HostNotFound as e:
        error(f"No token found for '{e.name}'")
        raise SystemExit(1) from e


def get_signal_handler(token: str):
    def signal_handler(sig, frame):
        # pylint: disable=global-statement
        del frame
        if sig == signal.SIGINT:
            global kill_requested
            if not task_ident:
                error("no task to kill")
                raise SystemExit(1) from None
            if kill_requested:
                raise SystemExit(1)

            kill_requested = True
            # Kill task request
            task_ident_dto = TaskIdentDto(task_ident)
            make_api_request_post(
                "task/kill", json.dumps(to_dict(task_ident_dto)), token
            )
            print("Task kill request sent...")
            task_result_dto = fetch_task_result(task_ident_dto, token)
            print_command_return_value(task_result_dto)
            print_task_details(task_result_dto)
            raise SystemExit(0)

    return signal_handler


# REQUEST FUNCTIONS
def _handle_api_error(curl: pycurl.Curl, response: str) -> None:
    if curl.getinfo(pycurl.RESPONSE_CODE) != 200:
        try:
            error_response = json.loads(response)
            error(error_response.error_message)
        except AttributeError:
            error(response)
        curl.close()
        raise SystemExit(1)
    curl.close()


def _make_api_request(endpoint) -> pycurl.Curl:
    curl = pycurl.Curl()
    curl.setopt(pycurl.URL, f"https://localhost:2224/api/v2/{endpoint}")
    curl.setopt(pycurl.SSL_VERIFYPEER, 0)
    curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    return curl


def make_api_request_get(endpoint: str, params: str, auth_token: str) -> str:
    curl = _make_api_request(endpoint + params)
    curl.setopt(pycurl.COOKIE, f"token={auth_token};".encode("utf-8"))
    response = curl.perform_rs()
    _handle_api_error(curl, response)
    return response


def make_api_request_post(
    endpoint: str,
    json_body: str,
    auth_token: str,
) -> str:
    curl = _make_api_request(endpoint)
    curl.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])
    curl.setopt(pycurl.POSTFIELDS, json_body)
    curl.setopt(pycurl.COOKIE, f"token={auth_token};".encode("utf-8"))
    response = curl.perform_rs()
    _handle_api_error(curl, response)
    return response


# PRETTY PRINT
def print_command_return_value(task_result_dto: TaskResultDto) -> None:
    print(task_result_dto.result)


def print_task_details(task_result_dto: TaskResultDto) -> None:
    print(
        dedent(
            f"""
                --------------------------
                Task ident: {task_result_dto.task_ident}
                Task finish type: {task_result_dto.task_finish_type}
                Task kill reason: {task_result_dto.kill_reason}
                """
        )
    )


def error(text: str) -> None:
    print(f"Error: {text}")


# COMMAND CALL
def fetch_task_result(
    task_ident_dto: TaskIdentDto, auth_token: str, sleep_interval: float = 0.3
) -> TaskResultDto:
    # pylint: disable=global-statement
    # Using global report list to recall reports in signal handler
    global report_list
    task_state = TaskState.CREATED
    while task_state != TaskState.FINISHED:
        response = make_api_request_get(
            "task/result",
            f"?task_ident={task_ident_dto.task_ident}",
            auth_token,
        )
        task_result_dto = from_dict(TaskResultDto, json.loads(response))
        task_state = task_result_dto.state

        # Only print new reports - picks only reports not in report_list
        for report_item_dto in task_result_dto.reports[
            len(report_list) : len(task_result_dto.reports) - len(report_list)
        ]:
            print_report(report_item_dto)
        report_list = task_result_dto.reports
        # Wait for updates and continue until the task is finished
        sleep(sleep_interval)  # 300ms
    global task_ident
    task_ident = ""
    return task_result_dto


def perform_command(command_dto: CommandDto, auth_token: str) -> TaskResultDto:
    # pylint: disable=global-statement
    global task_ident
    response = make_api_request_post(
        "task/create", json.dumps(to_dict(command_dto)), auth_token
    )
    task_ident_dto = from_dict(TaskIdentDto, json.loads(response))
    task_ident = task_ident_dto.task_ident

    task_result_dto = fetch_task_result(task_ident_dto, auth_token)

    return task_result_dto


def run_command_synchronously(
    command_dto: CommandDto, auth_token: str
) -> TaskResultDto:
    print("Running command synchronously")
    response = make_api_request_post(
        "task/run", json.dumps(to_dict(command_dto)), auth_token
    )
    task_result_dto = from_dict(TaskResultDto, json.loads(response))
    for report_item_dto in task_result_dto.reports:
        print_report(report_item_dto)
    return task_result_dto


def main():
    entrypoint = sys.argv.pop(0)
    if len(sys.argv) not in (1, 2, 3):
        error(f"Usage: {entrypoint} [--sync] <command> [<payload>]")
        raise SystemExit(1)
    run_fn = perform_command
    if sys.argv[0] == "--sync":
        sys.argv.pop(0)
        run_fn = run_command_synchronously
    if len(sys.argv) == 2:
        payload = sys.argv[1]
    else:
        payload = sys.stdin.read()
    token = os.environ.get("PCS_TOKEN", None)
    if token is None:
        token = get_token_for_localhost()
    signal.signal(signal.SIGINT, get_signal_handler(token))
    result = run_fn(
        CommandDto(
            sys.argv[0],
            json.loads(payload),
            options=CommandOptionsDto(
                request_timeout=None,
                # effective_username="custom_user",
                # effective_groups=["custom_group1", "custom_group2"],
            ),
        ),
        token,
    )
    print_command_return_value(result)
    print_task_details(result)
    if result.task_finish_type != TaskFinishType.SUCCESS:
        raise SystemExit(1)
