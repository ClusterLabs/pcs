import getopt
import json
import os
import signal
import sys
from textwrap import dedent
from time import sleep
from typing import (
    Dict,
    List,
    Union,
)

import pycurl

# Put pcs in path to make imports work
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(CURRENT_DIR))

from pcs.cli.common import parse_args
from pcs.cli.reports.processor import ReportProcessorToConsole
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
from pcs.daemon.async_tasks.command_mapping import command_map

LONG_OPTIONS = [
    "resource_or_tag_ids=",
]


def signal_handler(sig, frame):
    if sig == signal.SIGINT:
        try:
            task_ident_dto = frame.f_locals["task_ident_dto"]
        except KeyError:
            error("no task to kill")
            raise SystemExit(1) from None

        # Kill task request
        response = make_api_request_post(
            "task/kill", json.dumps(to_dict(task_ident_dto))
        )
        task_result_dto = from_dict(TaskResultDto, json.loads(response))

        print_command_return_value(task_result_dto)
        print_task_details(task_result_dto)


# REQUEST FUNCTIONS
def _handle_api_error(c: pycurl.Curl, response: str) -> None:
    if c.getinfo(pycurl.RESPONSE_CODE) != 200:
        error_response = json.loads(response)
        print(error_response.error_msg)

    c.close()


def _make_api_request(endpoint) -> pycurl.Curl:
    c = pycurl.Curl()
    c.setopt(pycurl.URL, f"https://localhost:2224/async_api/{endpoint}")
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    return c


def make_api_request_get(endpoint: str, params: str) -> str:
    c = _make_api_request(endpoint + params)
    response = c.perform_rs()
    _handle_api_error(c, response)
    return response


def make_api_request_post(
    endpoint: str,
    json_body: str,
) -> str:
    c = _make_api_request(endpoint)
    c.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])
    c.setopt(pycurl.POSTFIELDS, json_body)
    response = c.perform_rs()
    _handle_api_error(c, response)
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
def perform_command(command: str, params: dict) -> TaskResultDto:
    command_dto = CommandDto(command, params)
    response = make_api_request_post(
        "task/create", json.dumps(to_dict(command_dto))
    )
    task_ident_dto = from_dict(TaskIdentDto, json.loads(response))

    task_state = TaskState.CREATED
    # Reuse PCS CLI report processor for printing reports
    cli_report_processor = ReportProcessorToConsole()
    report_list: List[ReportItemDto] = []
    while task_state != TaskState.FINISHED:
        response = make_api_request_get(
            "task/result", f"?task_ident={task_ident_dto.task_ident}"
        )
        task_result_dto = from_dict(TaskResultDto, json.loads(response))
        task_state = task_result_dto.state

        # Only print new reports - picks only reports not in report_list
        cli_report_processor.report_list_dto(
            task_result_dto.reports[
                len(report_list) : len(task_result_dto.reports)
                - len(report_list)
            ]
        )
        report_list = task_result_dto.reports
        # Wait for updates and continue until the task is finished
        sleep(300 / 1000)  # 300ms

    return task_result_dto


# MAIN
signal.signal(signal.SIGINT, signal_handler)
argv = sys.argv[1:]

# Very simple argument parsing
try:
    options, cmd = getopt.gnu_getopt(
        argv,
        "",
        LONG_OPTIONS,
    )
except getopt.GetoptError as err:
    error(str(err))
    raise SystemExit(1) from None

# Check that daemon supports the command
cmd_str = " ".join(cmd)
if cmd_str not in command_map:
    error("this command is not supported")
    raise SystemExit(1)

# Call the new daemon and print results
option_dict: Dict[str, Union[str, List[str]]] = {}
for opt in options:
    # Accepting lib command argument names as options and values as JSON
    # for easy parsing
    option_dict[opt[0][2:]] = json.loads(opt[1])
result = perform_command(cmd_str, option_dict)
print_command_return_value(result)
print_task_details(result)
