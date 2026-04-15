from dataclasses import asdict, fields, is_dataclass
from enum import Enum, EnumType
from types import NoneType, UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    NewType,
    TypeVar,
    Union,
    get_type_hints,
)
from typing import get_args as get_type_args
from typing import get_origin as get_type_origin

import dacite

import pcs.common.async_tasks.types as async_tasks_types
import pcs.common.permissions.types as permissions_types
from pcs.common import types

if TYPE_CHECKING:
    from _typeshed import DataclassInstance  # pylint: disable=import-error
else:

    class DataclassInstance:
        pass


PrimitiveType = Union[str, int, float, bool, None]
DtoPayload = dict[str, "SerializableType"]
SerializableType = Union[
    PrimitiveType, DtoPayload, Iterable["SerializableType"]
]

T = TypeVar("T")

ToDictMetaKey = NewType("ToDictMetaKey", str)
META_NAME = ToDictMetaKey("META_NAME")


DTO_TYPE_HOOKS_MAP: dict[type[Any], Callable[[Any], Any]] = {
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


class PayloadConversionError(Exception):
    pass


class _UnionNotAllowed(Exception):
    pass


class DataTransferObject(DataclassInstance):
    pass


def meta(name: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if name:
        metadata[META_NAME] = name
    return metadata


# _type is Any - in reality, it is either one of:
# * type
# * enum.EnumType
# * something defined in typing module, e.g. typing._GenericAlias, typing.Union
# Especially the typing module changes with new Python versions.
# Properly typing (rather metatyping, since its input and output are types)
# this function doesn't bring any benefits.
def _extract_type_from_optional(_type: Any) -> Any:
    # Dataclass fields may be typed as 'Optional[some_type]' or
    # 'Union[some_type, None]' or 'some_type | None'. This function extracts
    # the inner type from an Optional, and thus allows to properly detect types
    # of such dataclass fields. It raises an exception if a Union contains more
    # than one type other than None, because in that case it is unclear which
    # one is the correct type. However, such a field should never be defined in
    # a dataclass, because field type must be unambiguous.

    # Internal representation of Union and Optional is different in Python 3.12
    # and 3.14. To be able to handle the differences, typing.get_origin is
    # used. It transforms all the representations to Union or UnionType.
    # https://docs.python.org/3/library/typing.html#typing.Union
    _type_origin = get_type_origin(_type)
    if not (_type_origin is Union or _type_origin is UnionType):
        return _type

    inner_types_without_none = [
        inner_type
        for inner_type in get_type_args(_type)
        if inner_type is not NoneType
    ]
    if len(inner_types_without_none) == 1:
        return inner_types_without_none[0]
    raise _UnionNotAllowed()


# _type is Any - in reality, it is either one of:
# * type
# * enum.EnumType
# * something defined in typing module, e.g. typing._GenericAlias, typing.Union
# Especially the typing module changes with new Python versions.
# Properly typing (rather metatyping, since its input and output are types)
# this function doesn't bring any benefits.
def _is_compatible_type(_type: Any, arg_index: int) -> bool:
    return (
        hasattr(_type, "__args__")
        and len(_type.__args__) >= arg_index
        and is_dataclass(_type.__args__[arg_index])
    )


# _type is Any - in reality, it is either one of:
# * type
# * enum.EnumType
# * something defined in typing module, e.g. typing._GenericAlias, typing.Union
# Especially the typing module changes with new Python versions.
# Properly typing (rather metatyping, since its input and output are types)
# this function doesn't bring any benefits.
def _is_enum_type(_type: Any, arg_index: int) -> bool:
    return (
        hasattr(_type, "__args__")
        and len(_type.__args__) >= arg_index
        and type(_type.__args__[arg_index]) is EnumType
    )


# returns Any as the type of enum value can be anything and it can be different
# for each Enum
def _convert_enum(value: Enum) -> Any:
    return value.value


def _convert_dict(
    klass: type[DataTransferObject], obj_dict: DtoPayload
) -> DtoPayload:
    new_dict = {}
    # resolve forward references in type hints, because type-detecting
    # functions do not work with forward references
    type_hints = get_type_hints(klass)
    for _field in fields(klass):
        try:
            _type = _extract_type_from_optional(type_hints[_field.name])
        except _UnionNotAllowed as e:
            raise AssertionError(
                f"Field '{_field.name}' in class '{klass}' is a Union: "
                f"{_field.type}. "
                "Dataclass fields cannot be Unions, unless they are a Union of "
                "one type and None (which is equal to Optional)."
            ) from e
        value = obj_dict[_field.name]

        new_value: SerializableType
        if value is None:
            # None must be handled here, other checks fail if they get None
            new_value = value
        elif is_dataclass(_type):
            new_value = _convert_dict(_type, value)  # type: ignore
        elif isinstance(value, list) and _is_compatible_type(_type, 0):
            new_value = [
                _convert_dict(_type.__args__[0], item) for item in value
            ]
        elif isinstance(value, list) and _is_enum_type(_type, 0):
            new_value = [_convert_enum(item) for item in value]
        elif isinstance(value, dict) and _is_compatible_type(_type, 1):
            new_value = {
                item_key: _convert_dict(_type.__args__[1], item_val)  # type: ignore[arg-type]
                for item_key, item_val in value.items()
            }
        elif isinstance(value, Enum):
            new_value = _convert_enum(value)
        else:
            new_value = value
        new_dict[_field.metadata.get(META_NAME, _field.name)] = new_value
    return new_dict


def to_dict(obj: DataTransferObject) -> DtoPayload:
    return _convert_dict(obj.__class__, asdict(obj))


DTOTYPE = TypeVar("DTOTYPE", bound=DataTransferObject)


def _convert_payload(klass: type[DTOTYPE], data: DtoPayload) -> DtoPayload:
    try:
        new_dict = dict(data)
    except ValueError as e:
        raise PayloadConversionError() from e
    # resolve forward references in type hints, because type-detecting
    # functions do not work with forward references
    type_hints = get_type_hints(klass)
    for _field in fields(klass):
        new_name = _field.metadata.get(META_NAME, _field.name)
        if new_name not in data:
            continue

        try:
            _type = _extract_type_from_optional(type_hints[_field.name])
        except _UnionNotAllowed as e:
            raise AssertionError(
                f"Field '{_field.name}' in class '{klass}' is a Union: "
                f"{_field.type}. "
                "Dataclass fields cannot be Unions, unless they are a Union of "
                "one type and None (which is equal to Optional)."
            ) from e
        value = data[new_name]

        new_value: SerializableType
        if value is None:
            # None must be handled here, other checks fail if they get None
            new_value = value
        elif is_dataclass(_type):
            new_value = _convert_payload(_type, value)  # type: ignore
        elif isinstance(value, list) and _is_compatible_type(_type, 0):
            new_value = [
                _convert_payload(_type.__args__[0], item) for item in value
            ]
        elif isinstance(value, dict) and _is_compatible_type(_type, 1):
            new_value = {
                item_key: _convert_payload(_type.__args__[1], item_val)  # type: ignore[arg-type]
                for item_key, item_val in value.items()
            }
        else:
            new_value = value
        del new_dict[new_name]
        new_dict[_field.name] = new_value
    return new_dict


def from_dict(
    cls: type[DTOTYPE], data: DtoPayload, strict: bool = False
) -> DTOTYPE:
    return dacite.from_dict(
        data_class=cls,
        data=_convert_payload(cls, data),
        # NOTE: all enum types has to be listed here in key cast
        # see: https://github.com/konradhalas/dacite#casting
        config=dacite.Config(
            cast=[
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
            ],
            type_hooks=DTO_TYPE_HOOKS_MAP,
            strict=strict,
        ),
    )


class ImplementsToDto:
    def to_dto(self) -> Any:
        raise NotImplementedError()


class ImplementsFromDto:
    @classmethod
    def from_dto(cls: type[T], dto_obj: Any) -> T:
        raise NotImplementedError()
