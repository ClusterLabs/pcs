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

from lxml import etree

from pcs import settings
from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker_values import is_true

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

def _get_valid_cluster_state_dom(xml):
    try:
        dom = etree.fromstring(xml)
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
        self.dom = _get_valid_cluster_state_dom(xml)
        super(ClusterState, self).__init__(self.dom)
