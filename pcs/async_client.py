# pylint: disable=global-statement
import json
import signal
import sys
from textwrap import dedent
from time import sleep
from typing import List

import pycurl

from pcs.cli.reports.processor import print_report
from pcs.common.async_tasks.dto import (
    CommandDto,
    TaskIdentDto,
    TaskResultDto,
)
from pcs.common.async_tasks.types import TaskState
from pcs.common.interface.dto import (
    from_dict,
    to_dict,
)
from pcs.common.reports import ReportItemDto

LONG_OPTIONS = [
    "resource_or_tag_ids=",
    "wait=",
]
task_ident = ""
report_list: List[ReportItemDto] = []


def signal_handler(sig, frame):
    # pylint: disable=unused-argument
    if sig == signal.SIGINT:
        if not task_ident:
            error("no task to kill")
            raise SystemExit(1) from None

        # Kill task request
        task_ident_dto = TaskIdentDto(task_ident)
        make_api_request_post("task/kill", json.dumps(to_dict(task_ident_dto)))
        print("Task kill request sent...")
        task_result_dto = fetch_task_result(task_ident_dto)
        print_command_return_value(task_result_dto)
        print_task_details(task_result_dto)
        raise SystemExit(0)


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
    curl.setopt(pycurl.URL, f"https://localhost:2224/async_api/{endpoint}")
    curl.setopt(pycurl.SSL_VERIFYPEER, 0)
    curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    return curl


def make_api_request_get(endpoint: str, params: str) -> str:
    curl = _make_api_request(endpoint + params)
    response = curl.perform_rs()
    _handle_api_error(curl, response)
    return response


def make_api_request_post(
    endpoint: str,
    json_body: str,
) -> str:
    curl = _make_api_request(endpoint)
    curl.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])
    curl.setopt(pycurl.POSTFIELDS, json_body)
    response = curl.perform_rs()
    _handle_api_error(curl, response)
    return response


# PRETTY PRINT
def print_command_return_value(task_result_dto: TaskResultDto) -> None:
    return_value = task_result_dto.result
    if return_value:
        print(return_value)


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
    task_ident_dto: TaskIdentDto, sleep_interval: float = 0.3
) -> TaskResultDto:
    task_state = TaskState.CREATED
    # Using global report list to recall reports in signal handler
    global report_list
    while task_state != TaskState.FINISHED:
        response = make_api_request_get(
            "task/result", f"?task_ident={task_ident_dto.task_ident}"
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


def perform_command(command: str, params: dict) -> TaskResultDto:
    command_dto = CommandDto(command, params)
    response = make_api_request_post(
        "task/create", json.dumps(to_dict(command_dto))
    )
    task_ident_dto = from_dict(TaskIdentDto, json.loads(response))
    global task_ident
    task_ident = task_ident_dto.task_ident

    task_result_dto = fetch_task_result(task_ident_dto)

    return task_result_dto


def main():
    signal.signal(signal.SIGINT, signal_handler)
    if len(sys.argv) not in (2, 3):
        error(f"Usage: {sys.argv[0]} <command> [<payload>]")
        raise SystemExit(1)
    if len(sys.argv) == 3:
        payload = sys.argv[2]
    else:
        payload = sys.stdin.read()
    result = perform_command(sys.argv[1], json.loads(payload))
    print_command_return_value(result)
    print_task_details(result)
