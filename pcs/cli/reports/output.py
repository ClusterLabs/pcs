import sys
from typing import Optional

from pcs.cli.common.tools import print_to_stderr
from pcs.common.reports import (
    ReportItemList,
    ReportItemSeverity,
)
from pcs.common.reports.dto import ReportItemContextDto

from .messages import report_item_msg_from_dto


def warn(message: str) -> None:
    print_to_stderr(f"Warning: {message}")


def deprecation_warning(message: str) -> None:
    print_to_stderr(f"Deprecation Warning: {message}")


def error(message: str) -> SystemExit:
    print_to_stderr(f"Error: {message}")
    return SystemExit(1)


def add_context_to_message(
    msg: str, context: Optional[ReportItemContextDto]
) -> str:
    if context:
        msg = f"{context.node}: {msg}"
    return msg


def process_library_reports(
    report_item_list: ReportItemList, exit_on_error: bool = True
) -> None:
    if not report_item_list:
        raise error("Errors have occurred, therefore pcs is unable to continue")

    critical_error = False
    for report_item in report_item_list:
        report_dto = report_item.to_dto()
        cli_report_msg = report_item_msg_from_dto(report_dto.message)
        msg = add_context_to_message(cli_report_msg.message, report_dto.context)
        severity = report_dto.severity.level

        if severity == ReportItemSeverity.WARNING:
            warn(msg)
            continue

        if severity == ReportItemSeverity.DEPRECATION:
            deprecation_warning(msg)
            continue

        if severity != ReportItemSeverity.ERROR:
            print_to_stderr(msg)
            continue

        error(
            add_context_to_message(
                cli_report_msg.get_message_with_force_text(
                    report_item.severity.force_code
                ),
                report_dto.context,
            )
        )
        critical_error = True

    if critical_error and exit_on_error:
        sys.exit(1)
