from dataclasses import dataclass
from typing import (
    Any,
    List,
    Dict,
    Optional,
)

from pcs.common.interface.dto import (
    ImplementsFromDto,
    ImplementsToDto,
)

from .types import (
    ForceCode,
    MessageCode,
    SeverityLevel,
)
from .dto import (
    ReportItemContextDto,
    ReportItemDto,
    ReportItemMessageDto,
    ReportItemSeverityDto,
)


@dataclass(frozen=True)
class ReportItemSeverity(ImplementsToDto, ImplementsFromDto):
    # pylint: disable=invalid-name
    ERROR = SeverityLevel("ERROR")
    WARNING = SeverityLevel("WARNING")
    INFO = SeverityLevel("INFO")
    DEBUG = SeverityLevel("DEBUG")

    level: SeverityLevel
    force_code: Optional[ForceCode] = None

    def to_dto(self) -> ReportItemSeverityDto:
        return ReportItemSeverityDto(
            level=self.level,
            force_code=self.force_code,
        )

    @classmethod
    def from_dto(cls, dto_obj: ReportItemSeverityDto) -> "ReportItemSeverity":
        return cls(
            level=dto_obj.level,
            force_code=dto_obj.force_code,
        )


@dataclass(frozen=True, init=False)
class ReportItemMessage(ImplementsToDto):
    _code = MessageCode("")

    @property
    def message(self) -> str:
        raise NotImplementedError()

    @property
    def code(self) -> MessageCode:
        return self._code

    def to_dto(self) -> ReportItemMessageDto:
        try:
            annotations = self.__class__.__annotations__
        except AttributeError:
            raise AssertionError() # TODO: msg

        payload: Dict[str, Any] = {}
        for attr_name, attr_type in annotations.items():
            if attr_name.startswith("_") or attr_name in ("code", "to_message"):
                continue
            if issubclass(attr_type, ReportItemMessage):
                # TODO: add support for Union
                payload[attr_name] = getattr(self, attr_name).to_dto()
            else:
                payload[attr_name] = getattr(self, attr_name)

        return ReportItemMessageDto(
            code=self.code,
            message=self.message,
            payload=payload,
        )


@dataclass(frozen=True)
class ReportItemContext(ImplementsToDto, ImplementsFromDto):
    node: str

    @classmethod
    def from_dto(cls, dto_obj: ReportItemContextDto) -> "ReportItemContext":
        return cls(node=dto_obj.node)

    def to_dto(self) -> ReportItemContextDto:
        return ReportItemContextDto(node=self.node)


@dataclass
class ReportItem(ImplementsToDto):
    severity: ReportItemSeverity
    message: ReportItemMessage
    context: Optional[ReportItemContext] = None

    @classmethod
    def error(cls,
        message: ReportItemMessage,
        force_code: Optional[ForceCode] = None,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity(
                ReportItemSeverity.ERROR, force_code=force_code,
            ),
            message=message,
            context=context,
        )

    @classmethod
    def warning(cls,
        message: ReportItemMessage,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity(ReportItemSeverity.WARNING),
            message=message,
            context=context,
        )

    def to_dto(self) -> ReportItemDto:
        return ReportItemDto(
            severity=self.severity.to_dto(),
            context=self.context.to_dto() if self.context else None,
            message=self.message.to_dto(),
        )


ReportItemList = List[ReportItem]
