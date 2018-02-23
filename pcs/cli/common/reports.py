import sys
import inspect
from functools import partial

from pcs.cli.booth.console_report import (
    CODE_TO_MESSAGE_BUILDER_MAP as BOOTH_CODE_TO_MESSAGE_BUILDER_MAP
)
from pcs.cli.common.console_report import (
    CODE_TO_MESSAGE_BUILDER_MAP,
    error,
    warn,
)
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

    message = code_builder_map[report_item.code]
    #Sometimes report item info is not needed for message building.
    #In that case the message is a string. Otherwise the message is a callable.
    if not callable(message):
        return message + force_text

    try:
        # Object functools.partial cannot be used with inspect because it is not
        # regular python function. We have to use original function for that.
        if isinstance(message, partial):
            keywords = message.keywords if message.keywords is not None else {}
            args = inspect.getfullargspec(message.func).args
            del args[:len(message.args)]
            args = [arg for arg in args if arg not in keywords]
        else:
            args = inspect.getfullargspec(message).args
        if "force_text" in args:
            return message(report_item.info, force_text)
        return message(report_item.info) + force_text
    except(TypeError, KeyError):
        return build_default_message_from_report(report_item, force_text)



build_report_message = partial(build_message_from_report, __CODE_BUILDER_MAP)

class LibraryReportProcessorToConsole(object):
    def __init__(self, debug=False):
        self.debug = debug
        self.items = []

    def append(self, report_item):
        self.items.append(report_item)
        return self

    def extend(self, report_item_list):
        self.items.extend(report_item_list)
        return self

    @property
    def errors_count(self):
        return len([
            item for item in self.items
            if item.severity == ReportItemSeverity.ERROR
        ])

    def report(self, report_item):
        return self.report_list([report_item])

    def report_list(self, report_item_list):
        return self._send(report_item_list)

    def process(self, report_item):
        self.append(report_item)
        self.send()

    def process_list(self, report_item_list):
        self.extend(report_item_list)
        self.send()

    def _send(self, report_item_list, print_errors=True):
        errors = []
        for report_item in report_item_list:
            if report_item.severity == ReportItemSeverity.ERROR:
                if print_errors:
                    error(build_report_message(report_item))
                errors.append(report_item)
            elif report_item.severity == ReportItemSeverity.WARNING:
                warn(build_report_message(report_item))
            elif self.debug or report_item.severity != ReportItemSeverity.DEBUG:
                print(build_report_message(report_item))
        return errors

    def send(self):
        errors = self._send(self.items, print_errors=False)
        self.items = []
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
    if not report_item_list:
        raise error("Errors have occurred, therefore pcs is unable to continue")

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
