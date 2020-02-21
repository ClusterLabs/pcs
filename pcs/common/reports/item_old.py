from typing import (
    List,
)

from .item import ReportItemSeverity as Severity


class ReportItemSeverity:
    ERROR = Severity.ERROR
    WARNING = Severity.WARNING
    INFO = Severity.INFO
    DEBUG = Severity.DEBUG


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
