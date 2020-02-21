import abc
from typing import (
    List,
    Union,
)

from . import item, item_old


ReportItem = Union[item.ReportItem, item_old.ReportItem]
ReportItemList = List[ReportItem]


class ReportProcessor(abc.ABC):
    def __init__(self):
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
    for report_item in report_list:
        if _is_error(report_item):
            return True
    return False


def _is_error(report_item: ReportItem,) -> bool:
    if isinstance(report_item, item_old.ReportItem):
        return report_item.severity == item.ReportItemSeverity.ERROR
    return report_item.severity.level == item.ReportItemSeverity.ERROR
