import abc

from typing import (
    List,
)

class ReportItemSeverity:
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class ReportItem:
    @classmethod
    def error(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.ERROR, **kwargs)

    @classmethod
    def warning(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.WARNING, **kwargs)

    @classmethod
    def info(cls, code, **kwargs):
        # pylint: disable=method-hidden
        # this is classmethod so it is ok
        return cls(code, ReportItemSeverity.INFO, **kwargs)

    @classmethod
    def debug(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.DEBUG, **kwargs)

    @classmethod
    def from_dict(cls, report_dict):
        return cls(
            report_dict["code"],
            report_dict["severity"],
            forceable=report_dict["forceable"],
            info=report_dict["info"]
        )

    def __init__(
        self, code, severity, forceable=None, info=None
    ):
        self.code = code
        self.severity = severity
        self.forceable = forceable
        self.info = info if info else dict()

    def __repr__(self):
        return "{severity} {code}: {info} forceable: {forceable}".format(
            severity=self.severity,
            code=self.code,
            info=self.info,
            forceable=self.forceable,
        )


ReportItemList = List[ReportItem]


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
