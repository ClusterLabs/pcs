import sys

from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportItemSeverity,
    codes,
)

from .messages import report_item_msg_from_dto


def warn(message: str, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    stream.write(f"Warning: {message}\n")


def error(message: str) -> SystemExit:
    sys.stderr.write(f"Error: {message}\n")
    return SystemExit(1)


def prepare_force_text(report_item: ReportItem) -> str:
    force_text_map = {
        codes.SKIP_OFFLINE_NODES: ", use --skip-offline to override",
    }
    force_code = report_item.severity.force_code
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

        if severity != ReportItemSeverity.ERROR:
            print(msg)
            continue

        error(
            "{msg}{force}".format(
                msg=msg,
                force=prepare_force_text(report_item),
            )
        )
        critical_error = True

    if critical_error:
        sys.exit(1)
