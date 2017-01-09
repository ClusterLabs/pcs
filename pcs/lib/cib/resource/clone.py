"""
Module for stuff related to clones.
Multi-state resources are a specialization of clone resources. So this module
include stuffs related to master.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.nvpair import append_new_meta_attributes
from pcs.lib.cib.tools import find_unique_id


TAG_CLONE = "clone"
TAG_MASTER = "master"
ALL_TAGS = [TAG_CLONE, TAG_MASTER]

def create_id(clone_tag, primitive_element):
    """
    Create id for clone element based on contained primitive_element.

    string clone_tag is tag of clone element. Specialization of "clone" is
        "master" and this function is common for both - "clone" and "master".
    etree.Element primitive_element is resource which will be cloned.
        It must be connected into the cib to ensure that the resulting id is
        unique!
    """
    return find_unique_id(
        primitive_element,
        "{0}-{1}".format(primitive_element.get("id"), clone_tag)
    )

def append_new(clone_tag, resources_section, primitive_element, options):
    """
    Append a new clone element (containing the primitive_element) to the
    resources_section.

    string clone_tag is tag of clone element. Expected values are "clone" and
        "master".
    etree.Element resources_section is place where new clone will be appended.
    etree.Element primitive_element is resource which will be cloned.
    dict options is source for clone meta options
    """
    clone_element = etree.SubElement(
        resources_section,
        clone_tag,
        id=create_id(clone_tag, primitive_element),
    )
    clone_element.append(primitive_element)

    if options:
        append_new_meta_attributes(clone_element, options)

    return clone_element
