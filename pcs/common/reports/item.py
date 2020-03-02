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
            level=self.level, force_code=self.force_code,
        )

    @classmethod
    def from_dto(cls, dto_obj: ReportItemSeverityDto) -> "ReportItemSeverity":
        return cls(level=dto_obj.level, force_code=dto_obj.force_code,)

    @classmethod
    def error(
        cls, force_code: Optional[ForceCode] = None
    ) -> "ReportItemSeverity":
        return cls(level=cls.ERROR, force_code=force_code)

    @classmethod
    def warning(cls) -> "ReportItemSeverity":
        return cls(level=cls.WARNING)

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


@dataclass(frozen=True, init=False)
class ReportItemMessage(ImplementsToDto):
    _code = MessageCode("")

    @property
    def message(self) -> str:
        raise NotImplementedError()

    @property
    def code(self) -> MessageCode:
        return self._code

    # TODO: tests
    def to_dto(self) -> ReportItemMessageDto:
        payload: Dict[str, Any] = {}
        if hasattr(self.__class__, "__annotations__"):
            try:
                annotations = self.__class__.__annotations__
            except AttributeError:
                raise AssertionError()
            for attr_name, attr_type in annotations.items():
                if attr_name.startswith("_") or attr_name in ("message",):
                    continue
                try:
                    if (
                        not hasattr(attr_type, "__origin__")
                        and getattr(attr_type, "__supertype__", None) is not str
                        and issubclass(attr_type, ReportItemMessage)
                    ):
                        payload[attr_name] = getattr(self, attr_name).to_dto()
                    else:
                        payload[attr_name] = getattr(self, attr_name)
                except:
                    # for debugging, TODO: remove when properly tested
                    print(self.__class__)
                    print(attr_type)
                    print(dir(attr_type))
                    print(attr_type.__supertype__)
                    raise

        return ReportItemMessageDto(
            code=self.code, message=self.message, payload=payload,
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
