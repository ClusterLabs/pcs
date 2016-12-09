from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.reports import LibraryReportProcessorToConsole
from pcs.lib.errors import LibraryError, ReportItemSeverity

class MockLibraryReportProcessor(LibraryReportProcessorToConsole):
    @property
    def report_item_list(self):
        return self.items

    def send(self):
        errors = []
        for report_item in self.items:
            if report_item.severity == ReportItemSeverity.ERROR:
                errors.append(report_item)
        if errors:
            raise LibraryError(*errors)
