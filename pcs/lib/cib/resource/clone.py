"""
Module for stuff related to clones.

Previously, promotable clones were implemented in pacemaker as 'master'
elements whereas regular clones were 'clone' elements. Since pacemaker-2.0,
promotable clones are clones with meta attribute promotable=true. Master
elements are deprecated yet still supported in pacemaker. We provide read-only
support for them to be able to read, process and display CIBs containing them.
"""

import dataclasses
from typing import (
    List,
    Mapping,
    Optional,
    cast,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common.pacemaker import nvset
from pcs.common.pacemaker.resource.clone import CibResourceCloneDto
from pcs.common.reports import ReportItemList
from pcs.lib.cib import (
    nvpair,
    nvpair_multi,
    rule,
)
from pcs.lib.cib.const import TAG_RESOURCE_CLONE as TAG_CLONE
from pcs.lib.cib.const import TAG_RESOURCE_MASTER as TAG_MASTER
from pcs.lib.cib.tools import IdProvider
from pcs.lib.pacemaker.values import (
    is_true,
    validate_id,
)

ALL_TAGS = [TAG_CLONE, TAG_MASTER]


def is_clone(resource_el: _Element) -> bool:
    return resource_el.tag == TAG_CLONE


def is_master(resource_el: _Element) -> bool:
    return resource_el.tag == TAG_MASTER


def is_any_clone(resource_el: _Element) -> bool:
    return resource_el.tag in ALL_TAGS


def is_promotable_clone(resource_el: _Element) -> bool:
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


def clone_element_to_dto(
    clone_element: _Element,
    rule_eval: Optional[rule.RuleInEffectEval] = None,
) -> CibResourceCloneDto:
    if rule_eval is None:
        rule_eval = rule.RuleInEffectEvalDummy()
    return CibResourceCloneDto(
        id=str(clone_element.attrib["id"]),
        description=clone_element.get("description"),
        member_id=str(get_inner_resource(clone_element).attrib["id"]),
        meta_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                clone_element, nvpair_multi.NVSET_META
            )
        ],
        instance_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                clone_element, nvpair_multi.NVSET_INSTANCE
            )
        ],
    )


def master_element_to_dto(
    master_element: _Element,
    rule_eval: Optional[rule.RuleInEffectEval] = None,
) -> CibResourceCloneDto:
    clone_dto = clone_element_to_dto(master_element, rule_eval)
    promotable_nvpair = nvset.CibNvpairDto(
        id="", name="promotable", value="true"
    )
    if clone_dto.meta_attributes:
        first_meta_attributes = clone_dto.meta_attributes[0]
        clone_dto = dataclasses.replace(
            clone_dto,
            meta_attributes=[
                dataclasses.replace(
                    first_meta_attributes,
                    nvpairs=(
                        list(first_meta_attributes.nvpairs)
                        + [promotable_nvpair]
                    ),
                )
            ]
            + list(clone_dto.meta_attributes[1:]),
        )
    else:
        clone_dto = dataclasses.replace(
            clone_dto,
            meta_attributes=[
                nvset.CibNvsetDto(
                    id="", options={}, rule=None, nvpairs=[promotable_nvpair]
                )
            ],
        )

    return clone_dto


def get_parent_any_clone(resource_el: _Element) -> Optional[_Element]:
    """
    Get any parent clone of a primitive (may be in a group) or group

    resource_el -- the primitive or group to get its parent clone
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
) -> _Element:
    """
    Append a new clone element (containing the primitive_element) to the
    resources_section.

    resources_section -- place where the new clone will be appended
    id_provider -- elements' ids generator
    primitive_element -- resource which will be cloned
    options -- source for clone meta options
    clone_id -- optional custom clone id
    """
    clone_element = etree.SubElement(
        resources_section,
        TAG_CLONE,
        id=(
            id_provider.allocate_id(
                "{0}-{1}".format(str(primitive_element.get("id")), TAG_CLONE)
            )
            if clone_id is None
            else clone_id
        ),
    )
    clone_element.append(primitive_element)

    if options:
        nvpair.append_new_meta_attributes(clone_element, options, id_provider)

    return clone_element


def get_inner_resource(clone_el: _Element) -> _Element:
    return cast(List[_Element], clone_el.xpath("./primitive | ./group"))[0]


def validate_clone_id(clone_id: str, id_provider: IdProvider) -> ReportItemList:
    """
    Validate that clone_id is a valid xml id and it is unique in the cib.

    clone_id -- identifier of clone element
    id_provider -- elements' ids generator
    """
    report_list: ReportItemList = []
    validate_id(clone_id, reporter=report_list)
    report_list.extend(id_provider.book_ids(clone_id))
    return report_list
