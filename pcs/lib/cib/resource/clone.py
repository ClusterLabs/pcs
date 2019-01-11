"""
Module for stuff related to clones.

Previously, promotable clones were implemented in pacemaker as 'master'
elements whereas regular clones were 'clone' elemets. Since pacemaker-2.0,
promotable clones are clones with meta attribute promotable=true. Master
elements are deprecated yet still supported in pacemaker. We provide read-only
support for them to be able to read, process and display CIBs containing them.
"""
from lxml import etree

from pcs.lib.cib.nvpair import append_new_meta_attributes


TAG_CLONE = "clone"
TAG_MASTER = "master"
ALL_TAGS = [TAG_CLONE, TAG_MASTER]

def is_clone(resource_el):
    return resource_el.tag == TAG_CLONE

def is_master(resource_el):
    return resource_el.tag == TAG_MASTER

def is_any_clone(resource_el):
    return resource_el.tag in ALL_TAGS

def append_new(resources_section, id_provider, primitive_element, options):
    """
    Append a new clone element (containing the primitive_element) to the
    resources_section.

    etree.Element resources_section is place where new clone will be appended.
    IdProvider id_provider -- elements' ids generator
    etree.Element primitive_element is resource which will be cloned.
    dict options is source for clone meta options
    """
    clone_element = etree.SubElement(
        resources_section,
        TAG_CLONE,
        id=id_provider.allocate_id(
            "{0}-{1}".format(primitive_element.get("id"), TAG_CLONE)
        )
    )
    clone_element.append(primitive_element)

    if options:
        append_new_meta_attributes(clone_element, options, id_provider)

    return clone_element

def get_inner_resource(clone_el):
    return clone_el.xpath("./primitive | ./group")[0]
