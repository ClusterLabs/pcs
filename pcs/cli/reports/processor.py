from typing import List

from pcs.common.reports import (
    ReportItem,
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.cli.common.tools import print_to_stderr

from .output import (
    error,
    prepare_force_text,
    warn,
)
from .messages import report_item_msg_from_dto


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self._ignore_severities: List[ReportItemSeverity] = []
        self.debug = debug

    def _do_report(self, report_item: ReportItem) -> None:
        report_dto = report_item.to_dto()
        msg = report_item_msg_from_dto(report_dto.message).message
        if report_dto.context:
            msg = f"{report_dto.context.node}: {msg}"
        severity = report_dto.severity.level

        if severity in self._ignore_severities:
            # DEBUG overrides ignoring severities for debug reports
            if msg and self.debug and severity == ReportItemSeverity.DEBUG:
                print_to_stderr(msg)
            return

        if severity == ReportItemSeverity.ERROR:
            error(
                "{msg}{force}".format(
                    msg=msg,
                    force=prepare_force_text(report_item),
                )
            )
        elif severity == ReportItemSeverity.WARNING:
            warn(msg)
        elif msg and (self.debug or severity != ReportItemSeverity.DEBUG):
            print_to_stderr(msg)

    def suppress_reports_of_severity(
        self, severity_list: List[ReportItemSeverity]
    ) -> None:
        self._ignore_severities = list(severity_list)
