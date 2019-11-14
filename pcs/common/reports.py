import abc

from pcs.lib.errors import ReportItem, ReportItemList


class SimpleReportProcessorInterface(abc.ABC):
    def report(self, report_item: ReportItem) -> ReportItemList:
        return self.report_list([report_item])

    @abc.abstractmethod
    def report_list(self, report_list: ReportItemList) -> ReportItemList:
        raise NotImplementedError()


class SimpleReportProcessor(SimpleReportProcessorInterface):
    """
    This class is a wrapper for a report processor class and at the same time
    implements interface of a simple report processor. This class interface for
    easy checking if some errors have been reported.
    """
    def __new__(cls, report_processor: SimpleReportProcessorInterface):
        if isinstance(report_processor, cls):
            # There is no point in wrapping the same object multiple times
            return report_processor
        self = super().__new__(cls)
        self.__init__(report_processor)
        return self

    def __init__(self, report_processor: SimpleReportProcessorInterface):
        self._report_processor = report_processor
        self._error_list: ReportItemList = []

    def report_list(self, report_list: ReportItemList) -> ReportItemList:
        error_list = self._report_processor.report_list(report_list)
        self._error_list.extend(error_list)
        return error_list

    @property
    def has_errors(self) -> bool:
        return bool(self._error_list)

    def clear_errors(self) -> None:
        self._error_list = []
