import abc
from .item_old import ReportItemSeverity, ReportItem, ReportItemList


class ReportProcessor(abc.ABC):
    def __init__(self):
        self._has_errors = False

    @property
    def has_errors(self) -> bool:
        return self._has_errors

    def report(self, report_item: ReportItem) -> "ReportProcessor":
        if report_item.severity == ReportItemSeverity.ERROR:
            self._has_errors = True
        self._do_report(report_item)
        return self

    def report_list(self, report_list: ReportItemList) -> "ReportProcessor":
        for report_item in report_list:
            self.report(report_item)
        return self

    @abc.abstractmethod
    def _do_report(self, report_item: ReportItem) -> None:
        raise NotImplementedError()


def has_errors(report_list: ReportItemList) -> bool:
    for report_item in report_list:
        if report_item.severity == ReportItemSeverity.ERROR:
            return True
    return False
