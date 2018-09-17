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

class ReportListAnalyzer(object):
    def __init__(self, report_list):
        self.__error_list = None
        self.__report_list = report_list

    def reports_with_severities(self, severity_list):
        return [
            report_item for report_item in self.report_list
            if report_item.severity in severity_list
        ]

    @property
    def report_list(self):
        return self.__report_list

    @property
    def error_list(self):
        if self.__error_list is None:
            self.__error_list = self.reports_with_severities(
                [ReportItemSeverity.ERROR]
            )
        return self.__error_list
