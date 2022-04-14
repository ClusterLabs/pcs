from typing import (
    Iterable,
    List,
    Set,
)

from pcs.cli.common.tools import print_to_stderr
from pcs.common.reports import (
    ReportItem,
    ReportItemDto,
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.reports.types import SeverityLevel

from .messages import report_item_msg_from_dto
from .output import (
    deprecation_warning,
    error,
    prepare_force_text,
    warn,
)


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self._ignore_severities: Set[SeverityLevel] = set()
        self.debug = debug

    def _do_report(self, report_item: ReportItem) -> None:
        report_item_dto = report_item.to_dto()
        if report_item_dto.severity.level in self._ignore_severities:
            return
        print_report(report_item_dto)

    def suppress_reports_of_severity(
        self, severity_list: Iterable[SeverityLevel]
    ) -> None:
        self._ignore_severities = set(severity_list)
        if self.debug:
            self._ignore_severities -= {ReportItemSeverity.DEBUG}
        else:
            self._ignore_severities |= {ReportItemSeverity.DEBUG}


def print_report(report_item_dto: ReportItemDto) -> None:
    msg = report_item_msg_from_dto(report_item_dto.message).message
    if report_item_dto.context:
        msg = f"{report_item_dto.context.node}: {msg}"
    if not msg:
        return

    severity = report_item_dto.severity.level
    if severity == ReportItemSeverity.ERROR:
        error(
            "{msg}{force}".format(
                msg=msg,
                force=prepare_force_text(
                    ReportItemSeverity.from_dto(report_item_dto.severity)
                ),
            )
        )
    elif severity == ReportItemSeverity.WARNING:
        warn(msg)
    elif severity == ReportItemSeverity.DEPRECATION:
        deprecation_warning(msg)
    else:
        print_to_stderr(msg)


def has_errors(report_list_dto: List[ReportItemDto]) -> bool:
    for report_item_dto in report_list_dto:
        if _is_error(report_item_dto):
            return True
    return False


def _is_error(report_item_dto: ReportItemDto) -> bool:
    return report_item_dto.severity.level == ReportItemSeverity.ERROR
