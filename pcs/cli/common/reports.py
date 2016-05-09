from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs.cli.constraint_all.console_report import duplicate_constraints_report
from pcs.common import report_codes as codes
from pcs.lib.errors import LibraryError, ReportItemSeverity


__CODE_BUILDER_MAP = {
    codes.DUPLICATE_CONSTRAINTS_EXIST: duplicate_constraints_report,
}


class LibraryReportProcessorToConsole(object):
    def process(self, report_item):
        self.process_list([report_item])

    def process_list(self, report_item_list):
        errors = []
        for report_item in report_item_list:
            if report_item.severity == ReportItemSeverity.ERROR:
                errors.append(report_item)
            elif report_item.severity == ReportItemSeverity.WARNING:
                print("Warning: " + report_item.message)
            else:
                print(report_item.message)
        if errors:
            raise LibraryError(*errors)


def _build_error_report(report_item):
    get_template = __CODE_BUILDER_MAP.get(
        report_item.code,
        lambda report_item: report_item.message + "{force}"
    )

    return get_template(report_item).format(
        force=", use --force to override" if report_item.forceable else ''
    )

def process_library_reports(report_item_list, is_forced=False):
    """
    report_item_list list of ReportItem
    """
    critical_error = False
    for report_item in report_item_list:
        if report_item.severity == ReportItemSeverity.WARNING:
            print("Warning: " + report_item.message)
            continue

        if report_item.severity != ReportItemSeverity.ERROR:
            print(report_item.message)
            continue

        if report_item.forceable and is_forced:
            # Let the user know what may be wrong even when --force is used,
            # as it may be used for override early errors hiding later
            # errors otherwise.
            print("Warning: " + report_item.message)
            continue

        sys.stderr.write(
            'Error: {0}\n'.format(_build_error_report(report_item))
        )
        critical_error = True

    if critical_error:
        sys.exit(1)
