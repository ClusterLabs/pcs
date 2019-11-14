from pcs.common.pacemaker.resource.relations import (
    RelationEntityDto,
    ResourceRelationDto,
    ResourceRelationType,
)
from pcs.lib.cib import tools
from pcs.lib.cib.resource import common

from pcs.lib.cib.resource.bundle import TAG as TAG_BUNDLE
from pcs.lib.cib.resource.clone import ALL_TAGS as TAG_CLONE_ALL
from pcs.lib.cib.resource.group import TAG as TAG_GROUP
from pcs.lib.cib.resource.primitive import TAG as TAG_PRIMITIVE


# character ':' ensures that there is no conflict with any id in CIB, as it
# would be an invalid id
INNER_RESOURCE_ID_TEMPLATE = "inner:{}"
OUTER_RESOURCE_ID_TEMPLATE = "outer:{}"


def _get_opposite_relation_id_template(relation_type):
    return {
        ResourceRelationType.INNER_RESOURCES: OUTER_RESOURCE_ID_TEMPLATE,
        ResourceRelationType.OUTER_RESOURCE: INNER_RESOURCE_ID_TEMPLATE,
    }.get(relation_type, "")


class ResourceRelationNode(object):
    def __init__(self, entity):
        self._obj = entity
        self._members = []
        self._is_leaf = False
        self._parent = None
        self._opposite_id = _get_opposite_relation_id_template(
            self._obj.type
        ).format(self._obj.metadata["id"])

    @property
    def obj(self):
        return self._obj

    @property
    def members(self):
        return self._members

    def to_dto(self):
        return ResourceRelationDto(
            self._obj,
            [member.to_dto() for member in self._members],
            self._is_leaf,
        )

    def stop(self):
        self._is_leaf = True

    def add_member(self, member):
        # pylint: disable=protected-access
        if member._parent is not None:
            raise AssertionError(
                "object {} already has a parent set: {}".format(
                    repr(member), repr(member._parent)
                )
            )
        # we don't want opposite relations (inner resource vs outer resource)
        # in a branch, so we are filtering them out
        parents = set(self._get_all_parents())
        if (
            self != member
            and
            member.obj.id not in parents
            and
            (
                member._opposite_id not in parents
                or
                len(member.obj.members) > 1
            )
        ):
            member._parent = self
            self._members.append(member)

    def _get_all_parents(self):
        # pylint: disable=protected-access
        if self._parent is None:
            return []
        return self._parent._get_all_parents() + [self._parent.obj.id]


class ResourceRelationTreeBuilder(object):
    def __init__(self, resource_entities, relation_entities):
        self._resources = resource_entities
        self._all = dict(resource_entities)
        self._all.update(relation_entities)
        self._init_structures()

    def _init_structures(self):
        self._processed_nodes = set()
        # queue
        self._nodes_to_process = []

    def get_tree(self, resource_id):
        self._init_structures()
        if resource_id not in self._resources:
            raise AssertionError(
                "Resource with id '{}' not found in resource "
                "relation structures".format(resource_id)
            )

        # self._all is a superset of self._resources, see __init__
        root = ResourceRelationNode(self._all[resource_id])
        self._nodes_to_process.append(root)

        while self._nodes_to_process:
            node = self._nodes_to_process.pop(0)
            if node.obj.id in self._processed_nodes:
                node.stop()
                continue
            self._processed_nodes.add(node.obj.id)
            for node_id in node.obj.members:
                node.add_member(
                    ResourceRelationNode(self._all[node_id])
                )
            self._nodes_to_process.extend(node.members)
        return root


class ResourceRelationsFetcher(object):
    def __init__(self, cib):
        self._cib = cib
        self._resources_section = tools.get_resources(self._cib)
        self._constraints_section = tools.get_constraints(self._cib)

    def get_relations(self, resource_id):
        resources_to_process = {resource_id}
        relations = {}
        resources = {}
        while resources_to_process:
            res_id = resources_to_process.pop()
            if res_id in resources:
                # already processed
                continue
            res_el = self._get_resource_el(res_id)
            res_relations = {
                rel.id: rel for rel in self._get_resource_relations(res_el)
            }
            resources[res_id] = RelationEntityDto(
                res_id,
                res_el.tag,
                list(res_relations.keys()),
                dict(res_el.attrib),
            )
            relations.update(res_relations)
            resources_to_process.update(
                self._get_all_members(res_relations.values())
            )
        return resources, relations

    def _get_resource_el(self, res_id):
        # client of this class should ensure that res_id really exists in CIB,
        # so here we don't need to handle possible reports
        for tag in TAG_CLONE_ALL + [TAG_GROUP, TAG_PRIMITIVE, TAG_BUNDLE]:
            element_list = self._resources_section.xpath(
                './/{}[@id="{}"]'.format(tag, res_id)
            )
            if element_list:
                return element_list[0]

    @staticmethod
    def _get_all_members(relation_list):
        result = set()
        for relation in relation_list:
            result.update(relation.members)
        return result

    def _get_resource_relations(self, resource_el):
        resource_id = resource_el.attrib["id"]
        relations = [
            _get_ordering_constraint_relation(item)
            for item in self._get_ordering_coinstraints(resource_id)
        ] + [
            _get_ordering_set_constraint_relation(item)
            for item in self._get_ordering_set_constraints(resource_id)
        ]

        # special type of relation, group (note that a group can be a resource
        # and a relation)
        if common.is_wrapper_resource(resource_el):
            relations.append(_get_inner_resources_relation(resource_el))

        # handle resources in a wrapper resource (group/bundle/clone relation)
        parent_el = common.get_parent_resource(resource_el)
        if parent_el is not None:
            relations.append(_get_outer_resource_relation(parent_el))
        return relations

    def _get_ordering_coinstraints(self, resource_id):
        return self._constraints_section.xpath("""
            .//rsc_order[
                not (descendant::resource_set)
                and
                (@first='{0}' or @then='{0}')
            ]
        """.format(resource_id))

    def _get_ordering_set_constraints(self, resource_id):
        return self._constraints_section.xpath(
            ".//rsc_order[./resource_set/resource_ref[@id='{}']]".format(
                resource_id
            )
        )


# relation obj to RelationEntityDto obj
def _get_inner_resources_relation(parent_resource_el):
    attrs = parent_resource_el.attrib
    return RelationEntityDto(
        INNER_RESOURCE_ID_TEMPLATE.format(attrs["id"]),
        ResourceRelationType.INNER_RESOURCES,
        [
            res.attrib["id"]
            for res in common.get_inner_resources(parent_resource_el)
        ],
        dict(attrs),
    )


def _get_outer_resource_relation(parent_resource_el):
    attrs = parent_resource_el.attrib
    return RelationEntityDto(
        OUTER_RESOURCE_ID_TEMPLATE.format(attrs["id"]),
        ResourceRelationType.OUTER_RESOURCE,
        [attrs["id"]],
        dict(attrs),
    )


def _get_ordering_constraint_relation(ord_const_el):
    attrs = ord_const_el.attrib
    return RelationEntityDto(
        attrs["id"],
        ResourceRelationType.ORDER,
        [attrs["first"], attrs["then"]],
        dict(attrs),
    )


def _get_ordering_set_constraint_relation(ord_set_const_el):
    attrs = ord_set_const_el.attrib
    members = set()
    metadata = dict(attrs)
    metadata["sets"] = []
    for rsc_set_el in ord_set_const_el.findall("resource_set"):
        rsc_set = dict(
            id=rsc_set_el.get("id"),
            metadata=dict(rsc_set_el.attrib),
            members=[],
        )
        metadata["sets"].append(rsc_set)
        for rsc_ref in rsc_set_el.findall("resource_ref"):
            rsc_id = rsc_ref.attrib["id"]
            members.add(rsc_id)
            rsc_set["members"].append(rsc_id)

    return RelationEntityDto(
        attrs["id"], ResourceRelationType.ORDER_SET, sorted(members), metadata
    )
