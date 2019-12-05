from typing import (
    Mapping,
    Sequence,
    Type,
    TypeVar,
    Union,
)
from dataclasses import asdict, is_dataclass
import dacite


PrimitiveType = Union[str, int, float, bool, None]
DtoPayload = Mapping[str, "SerializableType"] # type: ignore
SerializableType = Union[ # type: ignore
    PrimitiveType,
    DtoPayload, # type: ignore
    Sequence["SerializableType"], # type: ignore
]

T = TypeVar("T")


class DataTransferObject:
    pass


def to_dict(obj: DataTransferObject) -> DtoPayload:
    if not is_dataclass(obj):
        AssertionError()
    return asdict(obj)


DtoType = TypeVar("DtoType", bound=DataTransferObject)


def from_dict(cls: Type[DtoType], data: DtoPayload) -> DtoType:
    return dacite.from_dict(cls, data)


class ImplementsToDto:
    def to_dto(self) -> DataTransferObject:
        raise NotImplementedError()


class ImplementsFromDto:
    @classmethod
    def from_dto(cls: Type[T], dto_obj: DataTransferObject) -> T:
        raise NotImplementedError()
