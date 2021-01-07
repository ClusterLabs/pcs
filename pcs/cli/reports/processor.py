from pcs.common.reports import (
    ReportItem,
    ReportItemSeverity,
    ReportProcessor,
)

from .output import (
    error,
    prepare_force_text,
    warn,
)
from .messages import report_item_msg_from_dto


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self.debug = debug

    def _do_report(self, report_item: ReportItem) -> None:
        report_dto = report_item.to_dto()
        msg = report_item_msg_from_dto(report_dto.message).message
        severity = report_dto.severity.level
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
            print(msg)
