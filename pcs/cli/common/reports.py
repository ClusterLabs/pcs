from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs.cli.constraint_all.console_report import duplicit_constraints_report
from pcs.lib import error_codes as codes
from pcs.lib.errors import ReportItemSeverity


__CODE_BUILDER_MAP = {
    codes.DUPLICIT_CONSTRAINTS_EXIST: duplicit_constraints_report,
}

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

        sys.stderr.write('Error: {0}{1}\n'.format(
            #TODO in future this will be needed 1) extend for other severities
            #2) probably lazy loading modules
            __CODE_BUILDER_MAP[report_item.code](report_item)
                if report_item.code in __CODE_BUILDER_MAP else
                report_item.message
            ,
            ", use --force to override" if report_item.forceable else ''
        ))
        critical_error = True

    if critical_error:
        sys.exit(1)
