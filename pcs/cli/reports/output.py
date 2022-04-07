import sys

from pcs.cli.common.tools import print_to_stderr
from pcs.common.reports import (
    ReportItemList,
    ReportItemSeverity,
    codes,
)

from .messages import report_item_msg_from_dto


def warn(message: str) -> None:
    print_to_stderr(f"Warning: {message}")


def deprecation_warning(message: str) -> None:
    print_to_stderr(f"Deprecation Warning: {message}")


def error(message: str) -> SystemExit:
    print_to_stderr(f"Error: {message}")
    return SystemExit(1)


def prepare_force_text(report_item_severity: ReportItemSeverity) -> str:
    force_text_map = {
        codes.SKIP_OFFLINE_NODES: ", use --skip-offline to override",
    }
    force_code = report_item_severity.force_code
    if force_code:
        return force_text_map.get(force_code, ", use --force to override")
    return ""


def process_library_reports(report_item_list: ReportItemList) -> None:
    if not report_item_list:
        raise error("Errors have occurred, therefore pcs is unable to continue")

    critical_error = False
    for report_item in report_item_list:
        report_dto = report_item.to_dto()
        msg = report_item_msg_from_dto(report_dto.message).message
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
            "{msg}{force}".format(
                msg=msg,
                force=prepare_force_text(report_item.severity),
            )
        )
        critical_error = True

    if critical_error:
        sys.exit(1)
