from dataclasses import dataclass

from pcs.common.reports.item import ReportItemMessage
from pcs.common.reports.types import MessageCode


@dataclass(frozen=True)
class StubReportItem(ReportItemMessage):
    """Use this function to test report handling"""

    _code = MessageCode("REPORT_STUB")

    @property
    def message(self) -> str:
        return "This is a report item used for testing."
