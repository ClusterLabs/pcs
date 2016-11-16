from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib.tools import get_root
from pcs.lib.errors import LibraryError


TAG = "group"

def provide_group(resources_section, group_id):
    """
    Provide group with id=group_id. Create new group if group with id=group_id
    does not exists.

    etree.Element resources_section is place where new group will be appended
    string group_id is id of group
    """
    group_element = find_group_by_id(get_root(resources_section), group_id)
    if group_element is None:
        group_element = etree.SubElement(
            resources_section,
            "group",
            id=group_id
        )
    return group_element

def find_group_by_id(context_to_scan, group_id):
    """
    Return group with id=group_id. If group does not exists raise LibraryError.

    etree.Element(Tree) context_to_scan is contex inside will be group searched.
    string group_id is id of group
    """
    element = context_to_scan.find('.//*[@id="{0}"]'.format(group_id))
    if element is not None and element.tag != TAG:
        #TODO
        #keep original buggy functionality for now => refuse only some tags
        #in the future - after correction make common function in
        #pcs.lib.cib.tools
        if element.tag in ["primitive", "clone", "master"]:
            raise LibraryError(reports.id_belongs_to_unexpected_type(
                group_id,
                expected_types=[TAG],
                current_type=element.tag
            ))
    return element

def get_resource(group_element, resource_id):
    """
    Return resource with resource_id that is inside group_element.

    etree.Element group_element is a search area
    string resource_id is id of resource
    """
    resource = group_element.find('.//primitive[@id="{0}"]'.format(resource_id))
    if resource is None:
        raise LibraryError(reports.resource_not_found_in_group(
            resource_id,
            group_element.attrib["id"]
        ))
    return resource

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

    adjacent_resource = get_resource(group_element, adjacent_resource_id)

    if put_after_adjacent and adjacent_resource.getnext() is None:
        return group_element.append(primitive_element)

    index = group_element.index(
        adjacent_resource.getnext() if put_after_adjacent
        else adjacent_resource
    )
    group_element.insert(index, primitive_element)
