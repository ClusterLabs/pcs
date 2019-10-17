from typing import (
    Any,
    Mapping,
    Type,
    TypeVar,
)


class DataTransferObject:
    def to_dict(self) -> Mapping[str, Any]:
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DataTransferObject":
        raise NotImplementedError()


class ImplementsToDto:
    def to_dto(self) -> DataTransferObject:
        raise NotImplementedError()


T = TypeVar("T")

class ImplementsFromDto:
    @classmethod
    def from_dto(cls: Type[T], dto_obj: DataTransferObject) -> T:
        raise NotImplementedError()
