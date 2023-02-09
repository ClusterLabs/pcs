from typing import (
    Callable,
    Iterable,
    Optional,
    Set,
)

from pcs.common.reports import (
    ReportItem,
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.reports.dto import ReportItemDto
from pcs.common.reports.types import SeverityLevel

from .messages import report_item_msg_from_dto
from .output import (
    add_context_to_message,
    error,
    warn,
)

ReportItemPreprocessor = Callable[[ReportItem], Optional[ReportItem]]


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self.debug = debug
        self._ignore_severities = self._get_ignored_severities([])
        self._report_item_preprocessor: ReportItemPreprocessor = lambda x: x

    def _do_report(self, report_item: ReportItem) -> None:
        filtered_report_item = self._report_item_preprocessor(report_item)
        if not filtered_report_item:
            return
        report_item_dto = filtered_report_item.to_dto()
        if report_item_dto.severity.level not in self._ignore_severities:
            print_report(report_item_dto)

    def _get_ignored_severities(
        self, suppressed_severity_list: Iterable[SeverityLevel]
    ) -> Set[SeverityLevel]:
        ignore_severities = set(suppressed_severity_list)
        if self.debug:
            ignore_severities -= {ReportItemSeverity.DEBUG}
        else:
            ignore_severities |= {ReportItemSeverity.DEBUG}
        return ignore_severities

    def suppress_reports_of_severity(
        self, severity_list: Iterable[SeverityLevel]
    ) -> None:
        self._ignore_severities = self._get_ignored_severities(severity_list)

    def set_report_item_preprocessor(
        self,
        report_item_preprocessor: ReportItemPreprocessor,
    ) -> None:
        self._report_item_preprocessor = report_item_preprocessor


def print_report(report_item_dto: ReportItemDto) -> None:
    cli_report_msg = report_item_msg_from_dto(report_item_dto.message)
    msg = cli_report_msg.message
    if not msg:
        return
    msg = add_context_to_message(msg, report_item_dto.context)
    severity = report_item_dto.severity.level

    if severity == ReportItemSeverity.ERROR:
        error(
            add_context_to_message(
                cli_report_msg.get_message_with_force_text(
                    report_item_dto.severity.force_code
                ),
                report_item_dto.context,
            )
        )
    elif severity == ReportItemSeverity.WARNING:
        warn(msg)
    else:
        print(msg, flush=True)
