from collections.abc import Callable, Iterable
from dataclasses import asdict
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

import dacite

import pcs.common.async_tasks.types as async_tasks_types
import pcs.common.permissions.types as permissions_types
from pcs.common import types
from pcs.common.str_tools import format_list

if TYPE_CHECKING:
    from _typeshed import DataclassInstance
else:

    class DataclassInstance:
        pass


PrimitiveType = str | int | float | bool | None
DtoPayload = dict[str, "SerializableType"]
SerializableType = PrimitiveType | DtoPayload | Iterable["SerializableType"]


class PayloadConversionError(Exception):
    pass


class DataTransferObject(DataclassInstance):
    pass


T = TypeVar("T")
E = TypeVar("E", bound=Enum)
DTOTYPE = TypeVar("DTOTYPE", bound=DataTransferObject)


def _safe_enum_cast(enum_class: type[E]) -> Callable[[Any], E]:
    def _cast_value(value: Any) -> E:
        try:
            return enum_class(value)
        except ValueError as e:
            valid_values = format_list([f.value for f in enum_class])
            raise PayloadConversionError(
                f"Invalid value '{value}' for Enum '{enum_class.__name__}', "
                f"expected one of {valid_values}"
            ) from e

    return _cast_value


DTO_TYPE_HOOKS_MAP: dict[type[Any], Callable[[Any], Any]] = {
    # Dacite does not convert Enums automatically. We previously used simple
    # casting: https://github.com/konradhalas/dacite#casting, but that is not
    # sufficient, since it does not do proper handling of values that cannot
    # be converted to enums.
    #
    # All enum types used in lib command parameters must be listed here!
    **{
        enum_type: _safe_enum_cast(enum_type)
        for enum_type in [
            types.CibRuleExpressionType,
            types.CibRuleInEffectStatus,
            types.CorosyncNodeAddressType,
            types.CorosyncTransportType,
            types.DrRole,
            types.ResourceRelationType,
            async_tasks_types.TaskFinishType,
            async_tasks_types.TaskState,
            async_tasks_types.TaskKillReason,
            permissions_types.PermissionGrantedType,
            permissions_types.PermissionTargetType,
        ]
    },
    #
    # JSON does not support tuples, only lists. However, tuples are
    # used e.g. to express fixed-length structures. If a tuple is
    # expected and a list is provided, we convert it to a tuple.
    # Unfortunately, we cannot apply this rule generically to all
    # tuples, so we must handle specific cases manually.
    #
    # Covered cases:
    # * acl.create_role:
    #   permission_info_list: list[tuple[str, str, str]]
    tuple[str, str, str]: lambda v: tuple(v) if isinstance(v, list) else v,
    # Covered cases:
    # * resource.get_cibsecrets:
    #   queries: Sequence[tuple[str, str]]
    tuple[str, str]: lambda v: tuple(v) if isinstance(v, list) else v,
}


def from_dict(
    cls: type[DTOTYPE], data: DtoPayload, strict: bool = False
) -> DTOTYPE:
    return dacite.from_dict(
        data_class=cls,
        data=data,
        config=dacite.Config(
            type_hooks=DTO_TYPE_HOOKS_MAP,
            strict=strict,
        ),
    )


def to_dict(obj: DataTransferObject) -> DtoPayload:
    return asdict(obj)


class ImplementsToDto:
    def to_dto(self) -> Any:
        raise NotImplementedError()


class ImplementsFromDto:
    @classmethod
    def from_dto(cls: type[T], dto_obj: Any) -> T:
        raise NotImplementedError()
