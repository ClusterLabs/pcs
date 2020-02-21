from typing import (
    Any,
    Mapping,
)

from pcs.common.reports import (
    dto,
    item,
    messages,
)
from pcs.common.tools import get_all_subclasses


class CliReportMessage:
    def __init__(self, dto_obj: dto.ReportItemMessageDto) -> None:
        self._dto_obj = dto_obj

    @property
    def code(self) -> str:
        return self._dto_obj.code

    @property
    def message(self) -> str:
        return self._dto_obj.message

    @property
    def payload(self) -> Mapping[str, Any]:
        return self._dto_obj.payload


class CliReportMessageCustom(CliReportMessage):
    # pylint: disable=no-member
    _obj: item.ReportItemMessage
    def __init__(self, dto_obj: dto.ReportItemMessageDto) -> None:
        super().__init__(dto_obj)
        self._obj = self.__class__.__annotations__.get("_obj")( # type: ignore
            **dto_obj.payload
        )

    @property
    def message(self) -> str:
        raise NotImplementedError()


class CorosyncLinkDoesNotExistCannotUpdate(CliReportMessageCustom):
    _obj: messages.CorosyncLinkDoesNotExistCannotUpdate

    @property
    def message(self) -> str:
        return f"{self._dto_obj.message}{self._obj.existing_link_list}"


class ResourceManagedNoMonitorEnabled(CliReportMessageCustom):
    _obj: messages.ResourceManagedNoMonitorEnabled

    @property
    def message(self) -> str:
        return (
            f"Resource '{self._obj.resource_id}' has no enabled monitor "
            "operations. Re-run with '--monitor' to enable them."
        )


def _create_report_msg_map() -> Mapping[str, type]:
    result = {}
    for report_msg_cls in get_all_subclasses(CliReportMessageCustom):
        # pylint: disable=protected-access
        code = report_msg_cls.__annotations__.get(
            "_obj", item.ReportItemMessage
        )._code
        if code:
            result[code] = report_msg_cls
    return result


REPORT_MSG_MAP = _create_report_msg_map()


def report_item_msg_from_dto(
    obj: dto.ReportItemMessageDto
) -> CliReportMessage:
    return REPORT_MSG_MAP.get(obj.code, CliReportMessage)(obj)
