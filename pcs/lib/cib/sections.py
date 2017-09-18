"""
This module defines madatory and optional cib sections. It provides function for
getting existing section from the cib (lxml) tree.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import get_sub_element


CONFIGURATION = "configuration"
CONSTRAINTS = "configuration/constraints"
NODES = "configuration/nodes"
RESOURCES = "configuration/resources"

ACLS = "acls"
ALERTS = "alerts"
FENCING_TOPOLOGY = "fencing-topology"
OP_DEFAULTS = "op_defaults"
RSC_DEFAULTS = "rsc_defaults"

__MANDATORY_SECTIONS = [
    CONFIGURATION,
    CONSTRAINTS,
    NODES,
    RESOURCES,
]

__OPTIONAL_SECTIONS = [
    ACLS,
    ALERTS,
    FENCING_TOPOLOGY,
    OP_DEFAULTS,
    RSC_DEFAULTS,
]

def get(tree, section_name):
    """
    Return the element which represents section 'section_name' in the tree.

    If the section is mandatory and is not found in the tree this function
    raises.
    If the section is optional and is not found in the tree this function
    creates new section.

    lxml.etree.Element tree -- is tree in which the section is looked up
    string section_name -- name of desired section; it is strongly recommended
        to use constants defined in this module
    """
    if section_name in __MANDATORY_SECTIONS:
        section = tree.find(".//{0}".format(section_name))
        if section is not None:
            return section
        raise LibraryError(reports.cib_missing_mandatory_section(section_name))

    if section_name in __OPTIONAL_SECTIONS:
        return get_sub_element(get(tree, CONFIGURATION), section_name)

    raise AssertionError("Unknown cib section '{0}'".format(section_name))
