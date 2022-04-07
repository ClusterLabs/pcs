from typing import List

from pcs.cli.common.tools import print_to_stderr
from pcs.common.reports import (
    ReportItem,
    ReportItemDto,
    ReportItemSeverity,
    ReportProcessor,
)

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
        self._ignore_severities: List[ReportItemSeverity] = []
        self.debug = debug

    def report_list_dto(
        self, report_list_dto: List[ReportItemDto]
    ) -> "ReportProcessorToConsole":
        for report_item_dto in report_list_dto:
            self.report_dto(report_item_dto)
        return self

    def report_dto(
        self, report_item_dto: ReportItemDto
    ) -> "ReportProcessorToConsole":
        if _is_error(report_item_dto):
            self._has_errors = True
        self._do_report_dto(report_item_dto)
        return self

    def _do_report_dto(self, report_item_dto: ReportItemDto) -> None:
        msg = report_item_msg_from_dto(report_item_dto.message).message
        if report_item_dto.context:
            msg = f"{report_item_dto.context.node}: {msg}"
        severity = report_item_dto.severity.level

        if severity in self._ignore_severities:
            # DEBUG overrides ignoring severities for debug reports
            if msg and self.debug and severity == ReportItemSeverity.DEBUG:
                print_to_stderr(msg)
            return

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
        elif msg and (self.debug or severity != ReportItemSeverity.DEBUG):
            print_to_stderr(msg)

    def _do_report(self, report_item: ReportItem) -> None:
        report_dto = report_item.to_dto()
        self._do_report_dto(report_dto)

    def suppress_reports_of_severity(
        self, severity_list: List[ReportItemSeverity]
    ) -> None:
        self._ignore_severities = list(severity_list)


def has_errors(report_list_dto: List[ReportItemDto]) -> bool:
    for report_item_dto in report_list_dto:
        if _is_error(report_item_dto):
            return True
    return False


def _is_error(report_item_dto: ReportItemDto) -> bool:
    return report_item_dto.severity.level == ReportItemSeverity.ERROR
