import abc

from .item import (
    ReportItem,
    ReportItemList,
    ReportItemSeverity,
)


class ReportProcessor(abc.ABC):
    def __init__(self) -> None:
        self._has_errors = False

    @property
    def has_errors(self) -> bool:
        return self._has_errors

    def report(self, report_item: ReportItem) -> "ReportProcessor":
        if _is_error(report_item):
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
    return any(_is_error(report_item) for report_item in report_list)


def _is_error(report_item: ReportItem) -> bool:
    return report_item.severity.level == ReportItemSeverity.ERROR
