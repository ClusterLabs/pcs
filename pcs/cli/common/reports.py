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
    def __init__(self, debug=False):
        self.debug = debug

    def process(self, report_item):
        self.process_list([report_item])

    def process_list(self, report_item_list):
        errors = []
        for report_item in report_item_list:
            if report_item.severity == ReportItemSeverity.ERROR:
                errors.append(report_item)
            elif report_item.severity == ReportItemSeverity.WARNING:
                print("Warning: " + _build_report_message(report_item))
            elif self.debug or report_item.severity != ReportItemSeverity.DEBUG:
                print(report_item.message)
        if errors:
            raise LibraryError(*errors)

def _prepare_force_text(report_item):
    if report_item.forceable == codes.SKIP_OFFLINE_NODES:
        return ", use --skip-offline to override"
    return ", use --force to override" if report_item.forceable else ""

def _build_report_message(report_item, force_text=""):
    get_template = __CODE_BUILDER_MAP.get(
        report_item.code,
        lambda report_item: report_item.message + "{force}"
    )

    return get_template(report_item).format(force=force_text)

def process_library_reports(report_item_list):
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

        sys.stderr.write('Error: {0}\n'.format(_build_report_message(
            report_item,
            _prepare_force_text(report_item)
        )))
        critical_error = True

    if critical_error:
        sys.exit(1)
