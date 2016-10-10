from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

class LibraryError(Exception):
    pass

class LibraryEnvError(LibraryError):
    def __init__(self, *args, **kwargs):
        super(LibraryEnvError, self).__init__(*args, **kwargs)
        self.processed = []

    def sign_processed(self, report):
        self.processed.append(report)

    @property
    def unprocessed(self):
        return [report for report in self.args if report not in self.processed]



class ReportItemSeverity(object):
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'

class ReportItem(object):
    @classmethod
    def error(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.ERROR, **kwargs)

    @classmethod
    def warning(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.WARNING, **kwargs)

    @classmethod
    def info(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.INFO, **kwargs)

    @classmethod
    def debug(cls, code, **kwargs):
        return cls(code, ReportItemSeverity.DEBUG, **kwargs)

    def __init__(
        self, code, severity, forceable=None, info=None
    ):
        self.code = code
        self.severity = severity
        self.forceable = forceable
        self.info = info if info else dict()

    def __repr__(self):
        return "{severity} {code}: {info}".format(
            severity=self.severity,
            code=self.code,
            info=self.info
        )
