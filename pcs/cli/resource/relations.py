from __future__ import print_function

from pcs.common.pacemaker.resource.relations import (
    ResourceRelationDto,
    ResourceRelationType,
)
from pcs.cli.common.console_report import format_optional
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.printable_tree import (
    tree_to_lines,
    PrintableTreeNode,
)


def show_resource_relations_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --full - show constraint ids and resource types
    """
    if len(argv) != 1:
        raise CmdLineInputError()
    tree = ResourcePrintableNode.from_dto(
        ResourceRelationDto.from_dict(
            lib.resource.get_resource_relations_tree(argv[0])
        )
    )
    for line in tree_to_lines(tree, verbose=modifiers["full"]):
        print(line)


class ResourceRelationBase(PrintableTreeNode):
    def __init__( self, relation_entity, members, is_leaf):
        self._relation_entity = relation_entity
        self._members = members
        self._is_leaf = is_leaf

    @property
    def is_leaf(self):
        return self._is_leaf

    @property
    def relation_entity(self):
        return self._relation_entity

    @property
    def members(self):
        return self._members

    @property
    def detail(self):
        raise NotImplementedError()

    def get_title(self, verbose):
        raise NotImplementedError()


class ResourcePrintableNode(ResourceRelationBase):
    @classmethod
    def from_dto(cls, resource_dto):
        def _relation_comparator(item):
            type_priorities = (
                ResourceRelationType.INNER_RESOURCES,
                ResourceRelationType.OUTER_RESOURCE,
                ResourceRelationType.ORDER,
                ResourceRelationType.ORDER_SET,
            )
            priority_map = {
                _type: value for value, _type in enumerate(type_priorities)
            }
            return "{_type}_{_id}".format(
                _type=priority_map.get(
                    # Hardcoded number 9 is intentional. If there is more than
                    # 10 items, it would be required to also prepend zeros for
                    # lower numbers. E.g: if there is 100 options, it should
                    # starts as 000, 001, ...
                    item.relation_entity.type, 9 # type: ignore
                ),
                _id=item.relation_entity.id
            )

        return cls(
            resource_dto.relation_entity,
            sorted(
                [
                    RelationPrintableNode.from_dto(member_dto)
                    for member_dto in resource_dto.members
                ],
                key=_relation_comparator,
            ),
            resource_dto.is_leaf
        )

    def get_title(self, verbose):
        rsc_type = self._relation_entity.type
        metadata = self._relation_entity.metadata
        if rsc_type == "primitive":
            rsc_type = "{_class}{_provider}{_type}".format(
                _class=format_optional(metadata.get("class"), "{}:"),
                _provider=format_optional(metadata.get("provider"), "{}:"),
                _type=metadata.get("type"),
            )
        detail = " (resource: {})".format(rsc_type) if verbose else ""
        return "{}{}".format(self._relation_entity.id, detail)

    @property
    def detail(self):
        return []


class RelationPrintableNode(ResourceRelationBase):
    @classmethod
    def from_dto(cls, relation_dto):
        return cls(
            relation_dto.relation_entity,
            sorted(
                [
                    ResourcePrintableNode.from_dto(member_dto)
                    for member_dto in relation_dto.members
                ],
                key=lambda item: item.relation_entity.id,
            ),
            relation_dto.is_leaf
        )

    def get_title(self, verbose):
        rel_type_map = {
            ResourceRelationType.ORDER: "order",
            ResourceRelationType.ORDER_SET: "order set",
            ResourceRelationType.INNER_RESOURCES: "inner resource(s)",
            ResourceRelationType.OUTER_RESOURCE: "outer resource",
        }
        detail = (
            " ({})".format(self._relation_entity.metadata.get("id"))
            if verbose
            else ""
        )
        return "{type}{detail}".format(
            type=rel_type_map.get(self._relation_entity.type, "<unknown>"),
            detail=detail,
        )

    @property
    def detail(self):
        ent = self._relation_entity
        if ent.type == ResourceRelationType.ORDER:
            return _order_metadata_to_str(ent.metadata)
        if ent.type == ResourceRelationType.ORDER_SET:
            return _order_set_metadata_to_str(ent.metadata)
        if (
            ent.type == ResourceRelationType.INNER_RESOURCES
            and
            len(ent.members) > 1
        ):
            return ["members: {}".format(" ".join(ent.members))]
        return []


def _order_metadata_to_str(metadata):
    return [
        "{action1} {resource1} then {action2} {resource2}".format(
            action1=metadata["first-action"],
            resource1=metadata["first"],
            action2=metadata["then-action"],
            resource2=metadata["then"],
        )
    ] + _order_common_metadata_to_str(metadata)


def _order_set_metadata_to_str(metadata):
    result = []
    for res_set in metadata["sets"]:
        result.append("   set {resources}{options}".format(
            resources=" ".join(res_set["members"]),
            options=_resource_set_options_to_str(res_set["metadata"]),
        ))
    return _order_common_metadata_to_str(metadata) + result


def _resource_set_options_to_str(metadata):
    supported_keys = (
        "sequential", "require-all", "ordering", "action", "role", "kind",
        "score",
    )
    result = _filter_supported_keys(metadata, supported_keys)
    return " ({})".format(result) if result else ""


def _filter_supported_keys(data, supported_keys):
    return " ".join([
        "{}={}".format(key, value)
        for key, value in sorted(data.items())
        if key in supported_keys
    ])


def _order_common_metadata_to_str(metadata):
    result = _filter_supported_keys(
        metadata, ("symmetrical", "kind", "require-all", "score")
    )
    return [result] if result else []

