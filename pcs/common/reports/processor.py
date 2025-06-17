import abc
from logging import Logger

from pcs.common.reports.utils import add_context_to_message

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


class ReportProcessorToLog(ReportProcessor):
    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def _do_report(self, report_item: ReportItem) -> None:
        severity = report_item.severity.level

        context_dto = None
        if report_item.context:
            context_dto = report_item.context.to_dto()

        msg = add_context_to_message(report_item.message.message, context_dto)

        if severity == ReportItemSeverity.ERROR:
            self._logger.error(msg)
        elif severity in (
            ReportItemSeverity.WARNING,
            ReportItemSeverity.DEPRECATION,
        ):
            self._logger.warning(msg)
        elif severity == ReportItemSeverity.INFO:
            self._logger.info(msg)
        elif severity == ReportItemSeverity.DEBUG:
            self._logger.debug(msg)
        else:
            raise AssertionError("Unknown report severity")


class ReportProcessorInMemory(ReportProcessor):
    def __init__(self) -> None:
        super().__init__()
        self._reports: list[ReportItem] = []

    def _do_report(self, report_item: ReportItem) -> None:
        self._reports.append(report_item)

    @property
    def reports(self) -> ReportItemList:
        return self._reports
