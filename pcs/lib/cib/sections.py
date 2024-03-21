"""
This module defines mandatory and optional cib sections. It provides functions
for getting existing sections from the cib (lxml) tree.
"""

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import get_sub_element

CONFIGURATION = "configuration"
CONSTRAINTS = "configuration/constraints"
CRM_CONFIG = "configuration/crm_config"
NODES = "configuration/nodes"
RESOURCES = "configuration/resources"

ACLS = "acls"
ALERTS = "alerts"
FENCING_TOPOLOGY = "fencing-topology"
OP_DEFAULTS = "op_defaults"
RSC_DEFAULTS = "rsc_defaults"
TAGS = "tags"

__MANDATORY_SECTIONS = [
    CONFIGURATION,
    CONSTRAINTS,
    CRM_CONFIG,
    NODES,
    RESOURCES,
]

__OPTIONAL_SECTIONS = [
    ACLS,
    ALERTS,
    FENCING_TOPOLOGY,
    OP_DEFAULTS,
    RSC_DEFAULTS,
    TAGS,
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
        section = tree.find(f".//{section_name}")
        if section is not None:
            return section
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibCannotFindMandatorySection(section_name)
            )
        )

    if section_name in __OPTIONAL_SECTIONS:
        return get_sub_element(get(tree, CONFIGURATION), section_name)

    raise AssertionError(f"Unknown cib section '{section_name}'")


def exists(tree, section_name):
    if section_name not in __MANDATORY_SECTIONS + __OPTIONAL_SECTIONS:
        raise AssertionError(f"Unknown cib section '{section_name}'")
    return tree.find(f".//{section_name}") is not None
