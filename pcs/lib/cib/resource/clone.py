"""
Module for stuff related to clones.

Previously, promotable clones were implemented in pacemaker as 'master'
elements whereas regular clones were 'clone' elemets. Since pacemaker-2.0,
promotable clones are clones with meta attribute promotable=true. Master
elements are deprecated yet still supported in pacemaker. We provide read-only
support for them to be able to read, process and display CIBs containing them.
"""
from typing import (
    Mapping,
    Optional,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common.reports import ReportItemList
from pcs.lib.cib import nvpair
from pcs.lib.cib.const import TAG_RESOURCE_CLONE as TAG_CLONE
from pcs.lib.cib.const import TAG_RESOURCE_MASTER as TAG_MASTER
from pcs.lib.cib.tools import IdProvider
from pcs.lib.pacemaker.values import (
    is_true,
    validate_id,
)

ALL_TAGS = [TAG_CLONE, TAG_MASTER]


def is_clone(resource_el):
    return resource_el.tag == TAG_CLONE


def is_master(resource_el):
    return resource_el.tag == TAG_MASTER


def is_any_clone(resource_el):
    return resource_el.tag in ALL_TAGS


def is_promotable_clone(resource_el):
    """
    Return True if resource_el is a promotable clone, False on clone and master
    """
    return is_clone(resource_el) and is_true(
        nvpair.get_value(
            nvpair.META_ATTRIBUTES_TAG,
            resource_el,
            "promotable",
            default="false",
        )
    )


def get_parent_any_clone(resource_el):
    """
    Get any parent clone of a primitive (may be in a group) or group

    etree.Element resource_el -- the primitive or group to get its parent clone
    """
    element = resource_el
    for _ in range(2):
        parent_el = element.getparent()
        if parent_el is None:
            return None
        if is_any_clone(parent_el):
            return parent_el
        element = parent_el
    return None


def append_new(
    resources_section: _Element,
    id_provider: IdProvider,
    primitive_element: _Element,
    options: Mapping[str, str],
    clone_id: Optional[str] = None,
):
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
            "{0}-{1}".format(str(primitive_element.get("id")), TAG_CLONE)
        )
        if clone_id is None
        else clone_id,
    )
    clone_element.append(primitive_element)

    if options:
        nvpair.append_new_meta_attributes(clone_element, options, id_provider)

    return clone_element


def get_inner_resource(clone_el):
    return clone_el.xpath("./primitive | ./group")[0]


def validate_clone_id(clone_id: str, id_provider: IdProvider) -> ReportItemList:
    """
    Validate that clone_id is an valid xml id an it is uniqe in the cib.

    clone_id -- identifier of clone element
    id_provider -- elements' ids generator
    """
    report_list: ReportItemList = []
    validate_id(clone_id, reporter=report_list)
    report_list.extend(id_provider.book_ids(clone_id))
    return report_list
