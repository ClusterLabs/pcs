from typing import (
    Dict,
    Optional,
)

from pcs.common.tools import get_all_subclasses

from . import messages
from .dto import (
    ReportItemDto,
    ReportItemMessageDto,
)
from .item import (
    ReportItem,
    ReportItemContext,
    ReportItemSeverity,
)


def report_dto_to_item(
    dto_obj: ReportItemDto,
    context: Optional[ReportItemContext] = None,
) -> ReportItem:
    return ReportItem(
        severity=ReportItemSeverity.from_dto(dto_obj.severity),
        message=report_item_msg_from_dto(dto_obj.message),
        context=(
            context
            if context
            else (
                ReportItemContext.from_dto(dto_obj.context)
                if dto_obj.context
                else None
            )
        ),
    )


def _create_report_msg_map() -> Dict[str, type]:
    result: Dict[str, type] = {}
    for report_msg_cls in get_all_subclasses(messages.ReportItemMessage):
        code = report_msg_cls._code  # pylint: disable=protected-access # noqa: SLF001
        if code:
            if code in result:
                raise AssertionError()
            result[code] = report_msg_cls
    return result


REPORT_MSG_MAP = _create_report_msg_map()


def report_item_msg_from_dto(
    obj: ReportItemMessageDto,
) -> messages.ReportItemMessage:
    try:
        return REPORT_MSG_MAP[obj.code](**obj.payload)
    except KeyError:
        return messages.LegacyCommonMessage(obj.code, obj.payload, obj.message)
