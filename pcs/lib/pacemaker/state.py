'''
The intention is put there knowledge about cluster state structure.
Hide information about underlaying xml is desired too.
'''

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path
from collections import defaultdict

from lxml import etree

from pcs import settings
from pcs.common.tools import xml_fromstring
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity as severities
from pcs.lib.pacemaker.values import (
    is_false,
    is_true,
)
from pcs.lib.xml_tools import find_parent

class ResourceNotFound(Exception):
    pass

class _Attrs(object):
    def __init__(self, owner_name, attrib, required_attrs):
        '''
        attrib lxml.etree._Attrib - wrapped attribute collection
        required_attrs dict of required atribute names object_name:xml_attribute
        '''
        self.owner_name = owner_name
        self.attrib = attrib
        self.required_attrs = required_attrs

    def __getattr__(self, name):
        if name in self.required_attrs.keys():
            try:
                attr_specification = self.required_attrs[name]
                if isinstance(attr_specification, tuple):
                    attr_name, attr_transform = attr_specification
                    return attr_transform(self.attrib[attr_name])
                else:
                    return self.attrib[attr_specification]
            except KeyError:
                raise AttributeError(
                    "Missing attribute '{0}' ('{1}' in source) in '{2}'"
                    .format(name, self.required_attrs[name], self.owner_name)
                )

        raise AttributeError(
            "'{0}' does not declare attribute '{1}'"
            .format(self.owner_name, name)
        )

class _Children(object):
    def __init__(self, owner_name, dom_part, children, sections):
        self.owner_name = owner_name
        self.dom_part = dom_part
        self.children = children
        self.sections = sections

    def __getattr__(self, name):
        if name in self.children.keys():
            element_name, wrapper = self.children[name]
            return [
                wrapper(element)
                for element in self.dom_part.findall('.//' + element_name)
            ]

        if name in self.sections.keys():
            element_name, wrapper = self.sections[name]
            return wrapper(self.dom_part.findall('.//' + element_name)[0])

        raise AttributeError(
            "'{0}' does not declare child or section '{1}'"
            .format(self.owner_name, name)
        )

class _Element(object):
    required_attrs = {}
    children = {}
    sections = {}

    def __init__(self, dom_part):
        self.dom_part = dom_part
        self.attrs = _Attrs(
            self.__class__.__name__,
            self.dom_part.attrib,
            self.required_attrs
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
        'count': ('number', int),
    }

class _SummaryResources(_Element):
    required_attrs = {
        'count': ('number', int),
    }

class _SummarySection(_Element):
    sections = {
        'nodes': ('nodes_configured', _SummaryNodes),
        'resources': ('resources_configured', _SummaryResources),
    }

class _Node(_Element):
    required_attrs = {
        'id': 'id',
        'name': 'name',
        'type': 'type',
        'online': ('online', is_true),
        'standby': ('standby', is_true),
        'standby_onfail': ('standby_onfail', is_true),
        'maintenance': ('maintenance', is_true),
        'pending': ('pending', is_true),
        'unclean': ('unclean', is_true),
        'shutdown': ('shutdown', is_true),
        'expected_up': ('expected_up', is_true),
        'is_dc': ('is_dc', is_true),
        'resources_running': ('resources_running', int),
    }

class _NodeSection(_Element):
    children = {
        'nodes': ('node', _Node),
    }

def get_cluster_state_dom(xml):
    try:
        dom = xml_fromstring(xml)
        if os.path.isfile(settings.crm_mon_schema):
            etree.RelaxNG(file=settings.crm_mon_schema).assertValid(dom)
        return dom
    except (etree.XMLSyntaxError, etree.DocumentInvalid):
        raise LibraryError(reports.cluster_state_invalid_format())

class ClusterState(_Element):
    sections = {
        'summary': ('summary', _SummarySection),
        'node_section': ('nodes', _NodeSection),
    }

    def __init__(self, xml):
        self.dom = get_cluster_state_dom(xml)
        super(ClusterState, self).__init__(self.dom)

def _id_xpath_predicate(resource_id):
    return """(@id="{0}" or starts-with(@id, "{0}:"))""".format(resource_id)

def _get_primitives_for_state_check(
    cluster_state, resource_id, expected_running
):
    primitives = cluster_state.xpath("""
        .//resource[{predicate_id}]
        |
        .//group[{predicate_id}]/resource[{predicate_position}]
        |
        .//clone[@id="{id}"]/resource
        |
        .//clone[@id="{id}"]/group/resource[{predicate_position}]
        |
        .//bundle[@id="{id}"]/replica/resource
    """.format(
        id=resource_id,
        predicate_id=_id_xpath_predicate(resource_id),
        predicate_position=("last()" if expected_running else "1")
    ))
    return [
        element for element in primitives
            if not is_true(element.attrib.get("failed", ""))
    ]

def _get_primitive_roles_with_nodes(primitive_el_list):
    # Clone resources are represented by multiple primitive elements.
    roles_with_nodes = defaultdict(set)
    for resource_element in primitive_el_list:
        if resource_element.attrib["role"] in ["Started", "Master", "Slave"]:
            roles_with_nodes[resource_element.attrib["role"]].update([
                node.attrib["name"]
                for node in resource_element.findall(".//node")
            ])
    return dict([
        (role, sorted(nodes))
        for role, nodes in roles_with_nodes.items()
    ])

def ensure_resource_state(expected_running, cluster_state, resource_id):
    roles_with_nodes = _get_primitive_roles_with_nodes(
        _get_primitives_for_state_check(
            cluster_state,
            resource_id,
            expected_running
        )
    )
    if not roles_with_nodes:
        return reports.resource_does_not_run(
            resource_id,
            severities.INFO if not expected_running else severities.ERROR
        )
    return reports.resource_running_on_nodes(
        resource_id,
        roles_with_nodes,
        severities.INFO if expected_running else severities.ERROR
    )

def is_resource_managed(cluster_state, resource_id):
    """
    Check if the resource is managed

    etree cluster_state -- status of the cluster
    string resource_id -- id of the resource
    """
    primitive_list = cluster_state.xpath("""
        .//resource[{predicate_id}]
        |
        .//group[{predicate_id}]/resource
        """.format(predicate_id=_id_xpath_predicate(resource_id))
    )
    if primitive_list:
        for primitive in primitive_list:
            if is_false(primitive.attrib.get("managed", "")):
                return False
            clone = find_parent(primitive, ["clone"])
            if clone is not None and is_false(clone.attrib.get("managed", "")):
                return False
        return True

    clone_list = cluster_state.xpath(
        """.//clone[@id="{0}"]""".format(resource_id)
    )
    for clone in clone_list:
        if is_false(clone.attrib.get("managed", "")):
            return False
        for primitive in clone.xpath(".//resource"):
            if is_false(primitive.attrib.get("managed", "")):
                return False
        return True

    raise ResourceNotFound(resource_id)
