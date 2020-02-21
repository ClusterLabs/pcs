from functools import partial
from typing import Union
import inspect
import sys

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
from pcs.cli.reports.messages import report_item_msg_from_dto
from pcs.common.reports import (
    codes,
    # types as reports_types,
    item as reports_item,
    item_old as reports_item_old,
    ReportProcessor,
    ReportItemSeverity,
)
ReportItem = Union[reports_item.ReportItem, reports_item_old.ReportItem]
ReportItemList = Union[
    reports_item.ReportItemList, reports_item_old.ReportItemList
]


CODE_BUILDER_MAP = {}
CODE_BUILDER_MAP.update(CODE_TO_MESSAGE_BUILDER_MAP)
CODE_BUILDER_MAP.update(CONSTRAINT_CODE_TO_MESSAGE_BUILDER_MAP)
CODE_BUILDER_MAP.update(BOOTH_CODE_TO_MESSAGE_BUILDER_MAP)


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


build_report_message = partial(build_message_from_report, CODE_BUILDER_MAP)


class ReportProcessorToConsole(ReportProcessor):
    def __init__(self, debug=False):
        super().__init__()
        self.debug = debug

    def _do_report(self, report_item: ReportItem) -> None:
        if isinstance(report_item, reports_item_old.ReportItem):
            severity = report_item.severity
            if severity == ReportItemSeverity.ERROR:
                error(build_report_message(
                    report_item,
                    _prepare_force_text(report_item)
                ))
            elif severity == ReportItemSeverity.WARNING:
                warn(build_report_message(report_item))
            elif self.debug or (
                severity != ReportItemSeverity.DEBUG
            ):
                msg = build_report_message(report_item)
                if msg:
                    print(msg)
        else:
            report_dto = report_item.to_dto()
            msg = report_item_msg_from_dto(report_dto.message).message
            severity = report_dto.severity.level
            if severity == ReportItemSeverity.ERROR:
                error(
                    "{msg}{force}".format(
                        msg=msg,
                        force=_prepare_force_text(report_item),
                    )
                )
            elif severity == ReportItemSeverity.WARNING:
                warn(msg)
            elif msg and (self.debug or severity == ReportItemSeverity.DEBUG):
                print(msg)


def _prepare_force_text(report_item: ReportItem) -> str:
    force_text_map = {
        codes.SKIP_OFFLINE_NODES: ", use --skip-offline to override",
    }
    force_code = None
    if isinstance(report_item, reports_item_old.ReportItem):
        force_code = report_item.forceable
    elif isinstance(report_item, reports_item.ReportItem):
        force_code = report_item.severity.force_code
    if force_code:
        return force_text_map.get(force_code, ", use --force to override")
    return ""


def process_library_reports(report_item_list: ReportItemList) -> None:
    """
    report_item_list list of ReportItem
    """
    if not report_item_list:
        raise error("Errors have occurred, therefore pcs is unable to continue")

    critical_error = False
    for report_item in report_item_list:
        if isinstance(report_item, reports_item_old.ReportItem):
            severity = report_item.severity
            if severity == ReportItemSeverity.WARNING:
                warn(build_report_message(report_item))
                continue

            if severity != ReportItemSeverity.ERROR:
                print(build_report_message(report_item))
                continue

            error(build_report_message(
                report_item,
                _prepare_force_text(report_item)
            ))
            critical_error = True
        else:
            report_dto = report_item.to_dto()
            msg = report_item_msg_from_dto(report_dto.message).message
            severity = report_dto.severity.level

            if severity == ReportItemSeverity.WARNING:
                warn(msg)
                continue

            if severity != ReportItemSeverity.ERROR:
                print(msg)
                continue

            error(
                "{msg}{force}".format(
                    msg=msg,
                    force=_prepare_force_text(report_item),
                )
            )
            critical_error = True

    if critical_error:
        sys.exit(1)
