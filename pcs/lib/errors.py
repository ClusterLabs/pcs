from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

class LibraryError(Exception):
    pass

class ReportItemSeverity(object):
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'

class ReportItem(object):
    @classmethod
    def error(cls, code, message_pattern, **kwargs):
        return cls(code, ReportItemSeverity.ERROR, message_pattern, **kwargs)

    @classmethod
    def warning(cls, code, message_pattern, **kwargs):
        return cls(code, ReportItemSeverity.WARNING, message_pattern, **kwargs)

    @classmethod
    def info(cls, code, message_pattern, **kwargs):
        return cls(code, ReportItemSeverity.INFO, message_pattern, **kwargs)

    def __init__(
        self, code, severity, message_pattern, forceable=False, info=None
    ):
        self.code = code
        self.severity = severity
        self.forceable = forceable
        self.message_pattern=message_pattern
        self.info = info if info else dict()
        self.message = self.message_pattern.format(**self.info)

    def __repr__(self):
        return self.code+": "+str(self.info)
