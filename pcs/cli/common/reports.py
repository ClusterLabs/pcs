from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
from functools import partial

from pcs.cli.booth.console_report import (
    CODE_TO_MESSAGE_BUILDER_MAP as BOOTH_CODE_TO_MESSAGE_BUILDER_MAP
)
from pcs.cli.common.console_report import CODE_TO_MESSAGE_BUILDER_MAP
from pcs.cli.constraint_all.console_report import (
    CODE_TO_MESSAGE_BUILDER_MAP as CONSTRAINT_CODE_TO_MESSAGE_BUILDER_MAP
)
from pcs.common import report_codes as codes
from pcs.lib.errors import LibraryError, ReportItemSeverity


__CODE_BUILDER_MAP = {}
__CODE_BUILDER_MAP.update(CODE_TO_MESSAGE_BUILDER_MAP)
__CODE_BUILDER_MAP.update(CONSTRAINT_CODE_TO_MESSAGE_BUILDER_MAP)
__CODE_BUILDER_MAP.update(BOOTH_CODE_TO_MESSAGE_BUILDER_MAP)

def build_default_message_from_report(report_item, force_text):
    return "Unknown report: {0} info: {1}{2}".format(
        report_item.code,
        str(report_item.info),
        force_text,
    )


def build_message_from_report(code_builder_map, report_item, force_text=""):
    if report_item.code not in code_builder_map:
        return build_default_message_from_report(report_item, force_text)

    template = code_builder_map[report_item.code]
    #Sometimes report item info is not needed for message building.
    #In this case template is string. Otherwise, template is callable.
    if callable(template):
        try:
            template = template(report_item.info)
        except(TypeError, KeyError):
            return build_default_message_from_report(report_item, force_text)


    #Message can contain {force} placeholder if there is need to have it on
    #specific position. Otherwise is appended to the end (if necessary). This
    #removes the need to explicitly specify placeholder for each message.
    if force_text and "{force}" not in template:
        template += "{force}"

    return template.format(force=force_text)

build_report_message = partial(build_message_from_report, __CODE_BUILDER_MAP)

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
                print("Warning: " + build_report_message(report_item))
            elif self.debug or report_item.severity != ReportItemSeverity.DEBUG:
                print(build_report_message(report_item))
        if errors:
            raise LibraryError(*errors)

def _prepare_force_text(report_item):
    if report_item.forceable == codes.SKIP_OFFLINE_NODES:
        return ", use --skip-offline to override"
    return ", use --force to override" if report_item.forceable else ""

def process_library_reports(report_item_list):
    """
    report_item_list list of ReportItem
    """
    critical_error = False
    for report_item in report_item_list:
        if report_item.severity == ReportItemSeverity.WARNING:
            print("Warning: " + build_report_message(report_item))
            continue

        if report_item.severity != ReportItemSeverity.ERROR:
            print(build_report_message(report_item))
            continue

        sys.stderr.write('Error: {0}\n'.format(build_report_message(
            report_item,
            _prepare_force_text(report_item)
        )))
        critical_error = True

    if critical_error:
        sys.exit(1)
