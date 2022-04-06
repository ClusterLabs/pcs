import json
import signal
from time import sleep
from typing import List
from dataclasses import dataclass
import pycurl

from pcs.cli.reports.processor import ReportProcessorToConsole
from pcs.common.async_tasks import dto
from pcs.common.async_tasks.types import TaskState
from pcs.common.interface.dto import (
    from_dict,
    to_dict,
)
from pcs.common.reports.types import MessageCode
from pcs.common.reports import (
    ReportItem,
    ReportItemDto,
)
from pcs.common.reports.item import ReportItemSeverity, ReportItemMessage, ReportItemContext

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


def signal_handler(sig, frame):
    if sig == signal.SIGINT:
        try:
            task_ident_dto = frame.f_locals["task_ident_dto"]
        except KeyError:
            raise SystemExit(1) from None

        # Kill task request
        c = pycurl.Curl()
        c.setopt(pycurl.URL, "https://localhost:2224/async_api/task/kill")
        c.setopt(pycurl.SSL_VERIFYPEER, 0)
        c.setopt(pycurl.SSL_VERIFYHOST, 0)
        c.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])

        c.setopt(pycurl.POSTFIELDS, json.dumps(to_dict(task_ident_dto)))
        # task_result_dto = from_dict(dto.TaskIdentDto, json.loads(c.perform_rs()))
        print(c.perform_rs())
        c.close()


def perform_command(command: str, params: dict):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, "https://localhost:2224/async_api/task/create")
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(pycurl.HTTPHEADER, ["Content-Type: application/json"])

    command_dto = dto.CommandDto(command, params)
    c.setopt(pycurl.POSTFIELDS, json.dumps(to_dict(command_dto)))
    task_ident_dto = from_dict(dto.TaskIdentDto, json.loads(c.perform_rs()))
    c.close()

    task_state = TaskState.CREATED
    report_list: List[ReportItemDto] = []
    return_value = None
    while task_state != TaskState.FINISHED:
        c = pycurl.Curl()
        c.setopt(
            pycurl.URL,
            f"https://localhost:2224/async_api/task/"
            f"result?task_ident={task_ident_dto.task_ident}",
        )
        c.setopt(pycurl.SSL_VERIFYPEER, 0)
        c.setopt(pycurl.SSL_VERIFYHOST, 0)

        task_result_dto = from_dict(
            dto.TaskResultDto, json.loads(c.perform_rs())
        )
        c.close()
        task_state = task_result_dto.state

        # Print new reports through CLI report processor
        cli_report_processor = ReportProcessorToConsole()
        # Only print new reports - picks only reports not in report_list
        new_reports_dto = task_result_dto.reports[
            len(report_list) : len(task_result_dto.reports) - len(report_list)
        ]
        # Create ReportItem from DTO and put into report processor
        for report_item in new_reports_dto:
            report_item_severity = ReportItemSeverity.from_dto(report_item.severity)
            report_item_message = ReportItemMessageResponse(report_item.message.message, report_item.message.code)
            report_item_context = ReportItemContext.from_dto(report_item.context) if report_item.context else None
            cli_report_processor.report(
                ReportItem(report_item_severity, report_item_message,
                           report_item_context)
            )
        report_list = task_result_dto.reports
        return_value = task_result_dto.result
        # Wait for updates and continue if the task is unfinished
        sleep(300 / 1000)  # 300ms

    if return_value:
        print(return_value)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    perform_command("cluster status", {})


main()
