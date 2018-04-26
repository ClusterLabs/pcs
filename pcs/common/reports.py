import abc


class SimpleReportProcessorInterface(abc.ABC):
    def report(self, report_item):
        return self.report_list([report_item])

    @abc.abstractmethod
    def report_list(self, report_list):
        raise NotImplementedError()


class SimpleReportProcessor(SimpleReportProcessorInterface):
    """
    This class is a wrapper for a report processor class and at the same time
    implements interface of a simple report processor. This class interface for
    easy checking if some errors have been reported.
    """
    def __new__(cls, report_processor):
        if isinstance(report_processor, cls):
            # There is no point in wrapping the same object multiple times
            return report_processor
        self = super().__new__(cls)
        self.__init__(report_processor)
        return self

    def __init__(self, report_processor):
        self._report_processor = report_processor
        self._error_list = []

    def report_list(self, report_list):
        error_list = self._report_processor.report_list(report_list)
        self._error_list.extend(error_list)
        return error_list

    @property
    def has_errors(self):
        return bool(self._error_list)

    def clear_errors(self):
        self._error_list = []
