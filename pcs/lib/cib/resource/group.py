from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib.tools import find_element_by_tag_and_id
from pcs.lib.errors import LibraryError


TAG = "group"

def is_group(resource_el):
    return resource_el.tag == TAG

def provide_group(resources_section, group_id):
    """
    Provide group with id=group_id. Create new group if group with id=group_id
    does not exists.

    etree.Element resources_section is place where new group will be appended
    string group_id is id of group
    """
    group_element = find_element_by_tag_and_id(
        "group",
        resources_section,
        group_id,
        none_if_id_unused=True
    )
    if group_element is None:
        group_element = etree.SubElement(
            resources_section,
            "group",
            id=group_id
        )
    return group_element

def place_resource(
    group_element, primitive_element,
    adjacent_resource_id=None, put_after_adjacent=False
):
    """
    Add resource into group. This function is also applicable for a modification
    of the resource position because the primitive element is replanted from
    anywhere (including group itself) to concrete place inside group.

    etree.Element group_element is element where to put primitive_element
    etree.Element primitive_element is element for placement
    string adjacent_resource_id is id of the existing resource in group.
        primitive_element will be put beside adjacent_resource_id if specified.
    bool put_after_adjacent is flag where put primitive_element:
        before adjacent_resource_id if put_after_adjacent=False
        after adjacent_resource_id if put_after_adjacent=True
        Note that it make sense only if adjacent_resource_id is specified
    """
    if primitive_element.attrib["id"] == adjacent_resource_id:
        raise LibraryError(reports.resource_cannot_be_next_to_itself_in_group(
            adjacent_resource_id,
            group_element.attrib["id"],
        ))

    if not adjacent_resource_id:
        return group_element.append(primitive_element)

    adjacent_resource = find_element_by_tag_and_id(
        "primitive",
        group_element,
        adjacent_resource_id,
        id_description="resource",
    )

    if put_after_adjacent and adjacent_resource.getnext() is None:
        return group_element.append(primitive_element)

    index = group_element.index(
        adjacent_resource.getnext() if put_after_adjacent
        else adjacent_resource
    )
    group_element.insert(index, primitive_element)

def get_inner_resources(group_el):
    return group_el.xpath("./primitive")
