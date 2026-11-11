import sys
from collections.abc import Callable, Iterable

from pcs.cli.common.tools import print_to_stderr
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.reports import codes as reports_codes
from pcs.common.reports.dto import ReportItemDto
from pcs.common.reports.types import SeverityLevel
from pcs.common.reports.utils import add_context_to_message

from .messages import report_item_msg_from_dto
from .output import deprecation_warning, error, warn

ReportItemPreprocessor = Callable[[ReportItem], ReportItem | None]


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self.debug = debug
        self._ignore_severities = self._get_ignored_severities([])
        self._report_item_preprocessor: ReportItemPreprocessor = lambda x: x
        self._has_waiting_timeout_error = False

    def _do_report(self, report_item: ReportItem) -> None:
        filtered_report_item = self._report_item_preprocessor(report_item)
        if not filtered_report_item:
            return
        report_item_dto = filtered_report_item.to_dto()
        if (
            report_item_dto.severity.level == ReportItemSeverity.ERROR
            and report_item_dto.message.code
            == reports_codes.WAIT_FOR_IDLE_TIMED_OUT
        ):
            self._has_waiting_timeout_error = True
        if report_item_dto.severity.level not in self._ignore_severities:
            print_report(report_item_dto)

    def _get_ignored_severities(
        self, suppressed_severity_list: Iterable[SeverityLevel]
    ) -> set[SeverityLevel]:
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

    @property
    def has_waiting_timeout_error(self) -> bool:
        return self._has_waiting_timeout_error


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
    elif severity == ReportItemSeverity.DEPRECATION:
        deprecation_warning(msg)
    else:
        print_to_stderr(msg)


def has_errors(report_list_dto: list[ReportItemDto]) -> bool:
    for report_item_dto in report_list_dto:
        if _is_error(report_item_dto):
            return True
    return False


def _is_error(report_item_dto: ReportItemDto) -> bool:
    return report_item_dto.severity.level == ReportItemSeverity.ERROR


# DEPRECATED
# This function exists for the needs of already existing code and should not be
# used. It duplicates errors and reports handling which is meant to be done in
# app.py.
def report_and_exit_on_error(
    report_processor: ReportProcessorToConsole, report_item_list: ReportItemList
) -> None:
    if not report_item_list:
        raise error("Errors have occurred, therefore pcs is unable to continue")
    report_processor.report_list(report_item_list)
    # These flags are cumulative: once the report processor has seen an error
    # or a timeout, report_and_exit_on_error exits even when the passed report
    # list itself contains no error.
    if report_processor.has_waiting_timeout_error:
        sys.exit(2)
    if report_processor.has_errors:
        sys.exit(1)
