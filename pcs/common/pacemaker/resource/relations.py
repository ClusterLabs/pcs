from enum import auto
from typing import (
    cast,
    Any,
    Mapping,
    Sequence,
    Union,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.tools import AutoNameEnum


class ResourceRelationType(AutoNameEnum):
    ORDER = auto()
    ORDER_SET = auto()
    INNER_RESOURCES = auto()
    OUTER_RESOURCE = auto()


class RelationEntityDto(DataTransferObject):
    # Note: mypy doesn't understand recursive NamedTuple types, therefore this
    # class cannot inherit NamedTuple
    def __init__(
        self,
        id_: str,
        type_: Union[ResourceRelationType, str],
        members: Sequence[str],
        metadata: Mapping[str, Any],
    ):
        # pylint: disable=invalid-name
        self.id = id_
        self.type = type_
        self.members = members
        self.metadata = metadata

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, self.__class__)
            and
            self.to_dict() == cast(RelationEntityDto, other).to_dict()
        )

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            id=self.id,
            type=self.type,
            members=self.members,
            metadata=self.metadata,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RelationEntityDto":
        obj_type = payload["type"]
        try:
            obj_type = ResourceRelationType(obj_type)
        except ValueError:
            # if obj_type is not valid ResourceRelationType, it is resource
            # type as string such as 'primitive', 'clone', ...
            pass
        return cls(
            payload["id"],
            obj_type,
            payload["members"],
            payload["metadata"],
        )


class ResourceRelationDto(DataTransferObject):
    # Note: mypy doesn't understand recursive NamedTuple types, therefore this
    # class cannot inherit NamedTuple
    def __init__(
        self,
        relation_entity: RelationEntityDto,
        members: Sequence["ResourceRelationDto"],
        is_leaf: bool,
    ):
        self.relation_entity = relation_entity
        self.members = members
        self.is_leaf = is_leaf

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            relation_entity=self.relation_entity.to_dict(),
            members=[member.to_dict() for member in self.members],
            is_leaf=self.is_leaf,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResourceRelationDto":
        return cls(
            RelationEntityDto.from_dict(payload["relation_entity"]),
            [
                ResourceRelationDto.from_dict(member_data)
                for member_data in payload["members"]
            ],
            payload["is_leaf"],
        )
