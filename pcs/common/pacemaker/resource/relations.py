from pcs.common.interface.dto import DataTransferObject


class ResourceRelationType(object):
    ORDER = "ORDER"
    ORDER_SET = "ORDER_SET"
    INNER_RESOURCES = "INNER_RESOURCES"
    OUTER_RESOURCE = "OUTER_RESOURCE"


class RelationEntityDto(DataTransferObject):
    def __init__(self, id_, type_, members, metadata):
        # pylint: disable=invalid-name
        self.id = id_
        self.type = type_
        self.members = members
        self.metadata = metadata

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and
            self.to_dict() == other.to_dict()
        )

    def to_dict(self):
        return dict(
            id=self.id,
            type=self.type,
            members=self.members,
            metadata=self.metadata,
        )

    @classmethod
    def from_dict(cls, payload):
        return cls(
            payload["id"],
            payload["type"],
            payload["members"],
            payload["metadata"],
        )


class ResourceRelationDto(DataTransferObject):
    def __init__(self, relation_entity, members, is_leaf):
        self.relation_entity = relation_entity
        self.members = members
        self.is_leaf = is_leaf

    def to_dict(self):
        return dict(
            relation_entity=self.relation_entity.to_dict(),
            members=[member.to_dict() for member in self.members],
            is_leaf=self.is_leaf,
        )

    @classmethod
    def from_dict(cls, payload):
        return cls(
            RelationEntityDto.from_dict(payload["relation_entity"]),
            [
                ResourceRelationDto.from_dict(member_data)
                for member_data in payload["members"]
            ],
            payload["is_leaf"],
        )
