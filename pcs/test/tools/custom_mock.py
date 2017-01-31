from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.reports import LibraryReportProcessorToConsole
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.test.tools.assertions import  assert_report_item_list_equal

class MockLibraryReportProcessor(LibraryReportProcessorToConsole):
    def __init__(self, debug=False, raise_on_errors=True):
        super(MockLibraryReportProcessor, self).__init__(debug)
        self.raise_on_errors = raise_on_errors

    @property
    def report_item_list(self):
        return self.items

    def send(self):
        errors = []
        for report_item in self.items:
            if report_item.severity == ReportItemSeverity.ERROR:
                errors.append(report_item)
        if errors and self.raise_on_errors:
            raise LibraryError(*errors)

    def assert_reports(self, report_info_list):
        assert_report_item_list_equal(self.report_item_list, report_info_list)
