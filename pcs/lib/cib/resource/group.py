from typing import (
    List,
    cast,
)

from lxml.etree import (
    SubElement,
    _Element,
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
