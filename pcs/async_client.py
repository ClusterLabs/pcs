import json
import os
import signal
import sys
from dataclasses import dataclass
from time import sleep
from typing import List

import pycurl

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, os.path.join(PACKAGE_DIR, "pcs_bundled", "packages"))
sys.path.insert(0, os.path.dirname(CURRENT_DIR))

from pcs.cli.reports.processor import ReportProcessorToConsole
from pcs.common.async_tasks import dto
from pcs.common.async_tasks.types import TaskState
from pcs.common.interface.dto import (
    from_dict,
    to_dict,
)
from pcs.common.reports import ReportItemDto
from pcs.common.reports.item import ReportItemMessage
from pcs.common.reports.types import MessageCode


@dataclass(frozen=True)
class ReportItemMessageResponse(ReportItemMessage):
    _message: str
    _code: MessageCode

    @property
    def code(self) -> MessageCode:
        return self._code

    @property
    def message(self) -> str:
        return self._message


def _make_api_request(endpoint) -> pycurl.Curl:
    c = pycurl.Curl()
    c.setopt(pycurl.URL, f"https://localhost:2224/async_api/{endpoint}")
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    return c


def make_api_request_get(endpoint: str, params: str) -> str:
    c = _make_api_request(endpoint + params)
    response = c.perform_rs()
    c.close()
    return response


def make_api_request_post(
    endpoint: str,
    json_body: str,
) -> str:
    c = _make_api_request(endpoint)
    c.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])
    c.setopt(pycurl.POSTFIELDS, json_body)
    response = c.perform_rs()
    c.close()
    return response


def signal_handler(sig, frame):
    if sig == signal.SIGINT:
        try:
            task_ident_dto = frame.f_locals["task_ident_dto"]
        except KeyError:
            raise SystemExit(1) from None

        # Kill task request
        response = make_api_request_post(
            "task/kill", json.dumps(to_dict(task_ident_dto))
        )
        # task_result_dto = from_dict(
        #    dto.TaskIdentDto, json.loads(c.perform_rs())
        # )
        print(response)


def perform_command(command: str, params: dict):
    command_dto = dto.CommandDto(command, params)
    response = make_api_request_post(
        "task/create", json.dumps(to_dict(command_dto))
    )
    task_ident_dto = from_dict(dto.TaskIdentDto, json.loads(response))

    task_state = TaskState.CREATED
    # Reuse PCS CLI report processor for printing reports
    cli_report_processor = ReportProcessorToConsole()
    report_list: List[ReportItemDto] = []
    return_value = None
    while task_state != TaskState.FINISHED:
        response = make_api_request_get(
            "task/result", f"?task_ident={task_ident_dto.task_ident}"
        )
        task_result_dto = from_dict(dto.TaskResultDto, json.loads(response))
        task_state = task_result_dto.state

        # Only print new reports - picks only reports not in report_list
        cli_report_processor.report_list_dto(
            task_result_dto.reports[
                len(report_list) : len(task_result_dto.reports)
                - len(report_list)
            ]
        )
        report_list = task_result_dto.reports
        return_value = task_result_dto.result
        # Wait for updates and continue until the task is finished
        sleep(300 / 1000)  # 300ms

    if return_value:
        print(return_value)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    perform_command("cluster status", {})


main()
