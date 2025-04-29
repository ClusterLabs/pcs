from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pcs.common.interface.dto import (
    ImplementsFromDto,
    ImplementsToDto,
)

from .dto import (
    ReportItemContextDto,
    ReportItemDto,
    ReportItemMessageDto,
    ReportItemSeverityDto,
)
from .types import (
    ForceCode,
    ForceFlags,
    MessageCode,
    SeverityLevel,
)


@dataclass(frozen=True)
class ReportItemSeverity(ImplementsToDto, ImplementsFromDto):
    ERROR = SeverityLevel("ERROR")
    WARNING = SeverityLevel("WARNING")
    DEPRECATION = SeverityLevel("DEPRECATION")
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

    @classmethod
    def error(
        cls, force_code: Optional[ForceCode] = None
    ) -> "ReportItemSeverity":
        return cls(level=cls.ERROR, force_code=force_code)

    @classmethod
    def warning(cls) -> "ReportItemSeverity":
        return cls(level=cls.WARNING)

    @classmethod
    def deprecation(cls) -> "ReportItemSeverity":
        return cls(level=cls.DEPRECATION)

    @classmethod
    def info(cls) -> "ReportItemSeverity":
        return cls(level=cls.INFO)

    @classmethod
    def debug(cls) -> "ReportItemSeverity":
        return cls(level=cls.DEBUG)


def get_severity(
    force_code: Optional[ForceCode], is_forced: bool
) -> ReportItemSeverity:
    if is_forced:
        return ReportItemSeverity(ReportItemSeverity.WARNING)
    return ReportItemSeverity(ReportItemSeverity.ERROR, force_code)


def get_severity_from_flags(
    force_code: Optional[ForceCode], force_flags: ForceFlags
) -> ReportItemSeverity:
    """
    Returns warning/error severity for report creation depending on whether the
    force_code is in force_flags.

    force_code -- the force code by which the report can be overridden
    force_flags -- force flags specified to the command

    TODO: When pcs starts using other force codes than all-mighty force, this
    function can be expanded to allow for checking the weaker force code with
    automatic override by the all-mighty force. For example, if force_code is
    weak_force, and force_flags contain force but not weak_force, the function
    would return warning severity.
    """
    if force_code in force_flags:
        return ReportItemSeverity(ReportItemSeverity.WARNING)
    return ReportItemSeverity(ReportItemSeverity.ERROR, force_code)


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
        payload: Dict[str, Any] = {}
        if hasattr(self.__class__, "__annotations__"):
            try:
                annotations = self.__class__.__annotations__
            except AttributeError as e:
                raise AssertionError() from e
            for attr_name in annotations:
                if attr_name.startswith("_") or attr_name in ("message",):
                    continue
                attr_val = getattr(self, attr_name)
                if hasattr(attr_val, "to_dto"):
                    payload[attr_name] = attr_val.to_dto()
                else:
                    payload[attr_name] = attr_val

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
    def error(
        cls,
        message: ReportItemMessage,
        force_code: Optional[ForceCode] = None,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity.error(force_code),
            message=message,
            context=context,
        )

    @classmethod
    def warning(
        cls,
        message: ReportItemMessage,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity.warning(),
            message=message,
            context=context,
        )

    @classmethod
    def deprecation(
        cls,
        message: ReportItemMessage,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity.deprecation(),
            message=message,
            context=context,
        )

    @classmethod
    def info(
        cls,
        message: ReportItemMessage,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity.info(),
            message=message,
            context=context,
        )

    @classmethod
    def debug(
        cls,
        message: ReportItemMessage,
        context: Optional[ReportItemContext] = None,
    ) -> "ReportItem":
        return cls(
            severity=ReportItemSeverity.debug(),
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
