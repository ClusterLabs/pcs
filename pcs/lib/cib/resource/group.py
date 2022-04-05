from typing import (
    List,
    Optional,
    cast,
)

from lxml.etree import (
    SubElement,
    _Element,
)

from pcs.common.pacemaker.resource.group import CibResourceGroupDto
from pcs.lib.cib import (
    nvpair_multi,
    rule,
)
from pcs.lib.cib.const import TAG_RESOURCE_GROUP as TAG


def is_group(resource_el: _Element) -> bool:
    return resource_el.tag == TAG


def append_new(resources_section: _Element, group_id: str) -> _Element:
    return SubElement(resources_section, TAG, id=group_id)


def get_inner_resources(
    group_el: _Element,
) -> List[_Element]:
    return cast(List[_Element], group_el.xpath("./primitive"))


def group_element_to_dto(
    group_element: _Element,
    rule_eval: Optional[rule.RuleInEffectEval] = None,
) -> CibResourceGroupDto:
    if rule_eval is None:
        rule_eval = rule.RuleInEffectEvalDummy()
    return CibResourceGroupDto(
        id=str(group_element.attrib["id"]),
        description=group_element.get("description"),
        member_ids=[
            str(primitive_el.attrib["id"])
            for primitive_el in get_inner_resources(group_element)
        ],
        meta_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                group_element, nvpair_multi.NVSET_META
            )
        ],
        instance_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                group_element, nvpair_multi.NVSET_INSTANCE
            )
        ],
    )
