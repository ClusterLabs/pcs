from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.errors import LibraryError, ReportItemSeverity

class MockLibraryReportProcessor(object):
    def __init__(self):
        self.report_item_list = []

    def process(self, report_item):
        self.process_list([report_item])

    def process_list(self, report_item_list):
        self.report_item_list.extend(report_item_list)
        errors = [
            item for item in report_item_list
            if item.severity == ReportItemSeverity.ERROR
        ]
        if errors:
            raise LibraryError(*errors)
