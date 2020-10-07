from dataclasses import (
    asdict,
    fields,
    is_dataclass,
)
from typing import (
    Any,
    Dict,
    Iterable,
    NewType,
    Type,
    TypeVar,
    Union,
)
import dacite

import pcs.common.async_tasks.types as async_tasks_types
from pcs.common import types

PrimitiveType = Union[str, int, float, bool, None]
DtoPayload = Dict[str, "SerializableType"]  # type: ignore
SerializableType = Union[  # type: ignore
    PrimitiveType,
    DtoPayload,  # type: ignore
    Iterable["SerializableType"],  # type: ignore
]

T = TypeVar("T")

ToDictMetaKey = NewType("ToDictMetaKey", str)
META_NAME = ToDictMetaKey("META_NAME")


class DataTransferObject:
    pass


def meta(name: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if name:
        metadata[META_NAME] = name
    return metadata


def _is_compatible_type(_type: Type, arg_index: int) -> bool:
    return (
        hasattr(_type, "__args__")
        and len(_type.__args__) >= arg_index
        and is_dataclass(_type.__args__[arg_index])
    )


def _convert_dict(
    klass: Type[DataTransferObject], obj_dict: DtoPayload
) -> DtoPayload:
    new_dict = {}
    for _field in fields(klass):
        value = obj_dict[_field.name]
        if is_dataclass(_field.type):
            value = _convert_dict(_field.type, value)
        elif isinstance(value, list) and _is_compatible_type(_field.type, 0):
            value = [
                _convert_dict(_field.type.__args__[0], item) for item in value
            ]
        elif isinstance(value, dict) and _is_compatible_type(_field.type, 1):
            value = {
                item_key: _convert_dict(_field.type.__args__[1], item_val)
                for item_key, item_val in value.items()
            }
        new_dict[_field.metadata.get(META_NAME, _field.name)] = value
    return new_dict


def to_dict(obj: DataTransferObject) -> DtoPayload:
    return _convert_dict(obj.__class__, asdict(obj))


DTOTYPE = TypeVar("DTOTYPE", bound=DataTransferObject)


def _convert_payload(klass: Type[DTOTYPE], data: DtoPayload) -> DtoPayload:
    new_dict = {}
    for _field in fields(klass):
        value = data[_field.metadata.get(META_NAME, _field.name)]
        if is_dataclass(_field.type):
            value = _convert_payload(_field.type, value)
        elif isinstance(value, list) and _is_compatible_type(_field.type, 0):
            value = [
                _convert_payload(_field.type.__args__[0], item)
                for item in value
            ]
        elif isinstance(value, dict) and _is_compatible_type(_field.type, 1):
            value = {
                item_key: _convert_payload(_field.type.__args__[1], item_val)
                for item_key, item_val in value.items()
            }
        new_dict[_field.name] = value
    return new_dict


def from_dict(
    cls: Type[DTOTYPE], data: DtoPayload, strict: bool = False
) -> DTOTYPE:
    return dacite.from_dict(
        data_class=cls,
        data=_convert_payload(cls, data),
        # NOTE: all enum types has to be listed here in key cast
        # see: https://github.com/konradhalas/dacite#casting
        config=dacite.Config(
            cast=[
                types.CibRuleInEffectStatus,
                types.CibRuleExpressionType,
                types.CorosyncTransportType,
                types.DrRole,
                types.ResourceRelationType,
                async_tasks_types.TaskFinishType,
                async_tasks_types.TaskState,
                async_tasks_types.TaskKillOrigin,
            ],
            strict=strict,
        ),
    )


class ImplementsToDto:
    def to_dto(self) -> Any:
        raise NotImplementedError()


class ImplementsFromDto:
    @classmethod
    def from_dto(cls: Type[T], dto_obj: Any) -> T:
        raise NotImplementedError()
