"""
The intention is put there knowledge about cluster state structure.
Hide information about underlying xml is desired too.
"""

from collections import defaultdict
from typing import (
    Any,
    Dict,
)

from lxml import etree

from pcs.common import (
    const,
    reports,
)
from pcs.common.pacemaker.role import (
    get_value_primary as get_primary_role_value,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.pacemaker.values import (
    is_false,
    is_true,
)
from pcs.lib.xml_tools import find_parent


class ResourceNotFound(Exception):
    pass


_id_xpath_predicate = "(@id=$id or starts-with(@id, concat($id, ':')))"


class _Attrs:
    def __init__(self, owner_name, attrib, required_attrs):
        """
        attrib lxml.etree._Attrib - wrapped attribute collection
        required_attrs dict of required attribute names object_name:xml_attribute
        """
        self.owner_name = owner_name
        self.attrib = attrib
        self.required_attrs = required_attrs

    def __getattr__(self, name):
        if name in self.required_attrs:
            try:
                attr_specification = self.required_attrs[name]
                if isinstance(attr_specification, tuple):
                    attr_name, attr_transform = attr_specification
                    return attr_transform(self.attrib[attr_name])
                return self.attrib[attr_specification]
            except KeyError as e:
                raise AttributeError(
                    f"Missing attribute '{name}' ('{self.required_attrs[name]}' "
                    f"in source) in '{self.owner_name}'"
                ) from e

        raise AttributeError(
            f"'{self.owner_name}' does not declare attribute '{name}'"
        )


class _Children:
    def __init__(self, owner_name, dom_part, children, sections):
        self.owner_name = owner_name
        self.dom_part = dom_part
        self.children = children
        self.sections = sections

    def __getattr__(self, name):
        if name in self.children:
            element_name, wrapper = self.children[name]
            return [
                wrapper(element)
                for element in self.dom_part.xpath(
                    ".//*[local-name()=$tag_name]", tag_name=element_name
                )
            ]

        if name in self.sections:
            element_name, wrapper = self.sections[name]
            return wrapper(
                self.dom_part.xpath(
                    ".//*[local-name()=$tag_name]", tag_name=element_name
                )[0]
            )

        raise AttributeError(
            f"'{self.owner_name}' does not declare child or section '{name}'"
        )


class _Element:
    # Note: not properly typed
    required_attrs: Dict[Any, Any] = {}
    # Note: not properly typed
    children: Dict[Any, Any] = {}
    # Note: not properly typed
    sections: Dict[Any, Any] = {}

    def __init__(self, dom_part: etree._Element):
        self.dom_part = dom_part
        self.attrs = _Attrs(
            self.__class__.__name__, self.dom_part.attrib, self.required_attrs
        )
        self.children_access = _Children(
            self.__class__.__name__,
            self.dom_part,
            self.children,
            self.sections,
        )

    def __getattr__(self, name):
        return getattr(self.children_access, name)


class _SummaryNodes(_Element):
    required_attrs = {
        "count": ("number", int),
    }


class _SummaryResources(_Element):
    required_attrs = {
        "count": ("number", int),
    }


class _SummarySection(_Element):
    sections = {
        "nodes": ("nodes_configured", _SummaryNodes),
        "resources": ("resources_configured", _SummaryResources),
    }


class _Node(_Element):
    required_attrs = {
        "id": "id",
        "name": "name",
        "type": "type",
        "online": ("online", is_true),
        "standby": ("standby", is_true),
        "standby_onfail": ("standby_onfail", is_true),
        "maintenance": ("maintenance", is_true),
        "pending": ("pending", is_true),
        "unclean": ("unclean", is_true),
        "shutdown": ("shutdown", is_true),
        "expected_up": ("expected_up", is_true),
        "is_dc": ("is_dc", is_true),
        "resources_running": ("resources_running", int),
    }


class _NodeSection(_Element):
    children = {
        "nodes": ("node", _Node),
    }


class ClusterState(_Element):
    sections = {
        "summary": ("summary", _SummarySection),
        "node_section": ("nodes", _NodeSection),
    }


def _get_primitives_for_state_check(
    cluster_state, resource_id, expected_running
):
    primitives = cluster_state.xpath(
        """
        .//resource[{predicate_id}]
        |
        .//group[{predicate_id}]/resource[{predicate_position}]
        |
        .//clone[@id=$id]/resource
        |
        .//clone[@id=$id]/group/resource[{predicate_position}]
        |
        .//bundle[@id=$id]/replica/resource
    """.format(
            predicate_id=_id_xpath_predicate,
            predicate_position=("last()" if expected_running else "1"),
        ),
        id=resource_id,
    )
    return [
        element
        for element in primitives
        if not is_true(element.attrib.get("failed", ""))
    ]


def _get_primitive_roles_with_nodes(primitive_el_list):
    # Clone resources are represented by multiple primitive elements.
    roles_with_nodes = defaultdict(set)
    for resource_element in primitive_el_list:
        if (
            resource_element.attrib["role"]
            in const.PCMK_ROLES_RUNNING_WITH_LEGACY
        ):
            roles_with_nodes[
                get_primary_role_value(resource_element.attrib["role"])
            ].update(
                [
                    node.attrib["name"]
                    for node in resource_element.findall(".//node")
                ]
            )
    return {role: sorted(nodes) for role, nodes in roles_with_nodes.items()}


def get_resource_state(cluster_state, resource_id):
    return _get_primitive_roles_with_nodes(
        _get_primitives_for_state_check(
            cluster_state, resource_id, expected_running=True
        )
    )


def info_resource_state(cluster_state, resource_id):
    roles_with_nodes = get_resource_state(cluster_state, resource_id)
    if not roles_with_nodes:
        return ReportItem.info(reports.messages.ResourceDoesNotRun(resource_id))
    return ReportItem.info(
        reports.messages.ResourceRunningOnNodes(resource_id, roles_with_nodes)
    )


def ensure_resource_state(expected_running, cluster_state, resource_id):
    roles_with_nodes = _get_primitive_roles_with_nodes(
        _get_primitives_for_state_check(
            cluster_state, resource_id, expected_running
        )
    )
    if not roles_with_nodes:
        return ReportItem(
            reports.item.ReportItemSeverity(
                reports.ReportItemSeverity.INFO
                if not expected_running
                else reports.ReportItemSeverity.ERROR
            ),
            reports.messages.ResourceDoesNotRun(resource_id),
        )
    return ReportItem(
        reports.item.ReportItemSeverity(
            reports.ReportItemSeverity.INFO
            if expected_running
            else reports.ReportItemSeverity.ERROR
        ),
        reports.messages.ResourceRunningOnNodes(resource_id, roles_with_nodes),
    )


def ensure_resource_running(cluster_state, resource_id):
    return ensure_resource_state(
        expected_running=True,
        cluster_state=cluster_state,
        resource_id=resource_id,
    )


def is_resource_managed(cluster_state, resource_id):
    """
    Check if the resource is managed

    etree cluster_state -- status of the cluster
    string resource_id -- id of the resource
    """
    primitive_list = cluster_state.xpath(
        """
        .//resource[{predicate_id}]
        |
        .//group[{predicate_id}]/resource
        """.format(predicate_id=_id_xpath_predicate),
        id=resource_id,
    )
    if primitive_list:
        for primitive in primitive_list:
            if is_false(primitive.attrib.get("managed", "")):
                return False
            parent = find_parent(primitive, ["clone", "bundle"])
            if parent is not None and is_false(
                parent.attrib.get("managed", "")
            ):
                return False
        return True

    parent_list = cluster_state.xpath(
        """
        .//clone[@id=$resource_id]
        |
        .//bundle[@id=$resource_id]
        """,
        resource_id=resource_id,
    )
    for parent in parent_list:
        if is_false(parent.attrib.get("managed", "")):
            return False
        for primitive in parent.xpath(".//resource"):
            if is_false(primitive.attrib.get("managed", "")):
                return False
        return True

    raise ResourceNotFound(resource_id)
