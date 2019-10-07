from typing import (
    Any,
    Mapping,
    Type,
    TypeVar,
)
from typing_extensions import Protocol


class DataTransferObject(Protocol):
    def to_dict(self) -> Mapping[str, Any]:
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DataTransferObject":
        raise NotImplementedError()


class ImplementsToDto(Protocol):
    def to_dto(self) -> DataTransferObject:
        raise NotImplementedError()


T = TypeVar("T")

class ImplementsFromDto(Protocol):
    @classmethod
    def from_dto(cls: Type[T], dto_obj: DataTransferObject) -> T:
        raise NotImplementedError()
