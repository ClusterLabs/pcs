from typing import (
    Iterable,
    List,
    Optional,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports.const import (
    ADD_REMOVE_CONTAINER_TYPE_GROUP,
    ADD_REMOVE_ITEM_TYPE_RESOURCE,
)
from pcs.common.reports.item import ReportItem, ReportItemList
from pcs.lib.cib.resource import (
    clone,
    group,
)
from pcs.lib.cib.resource.common import (
    get_parent_resource,
    get_inner_resources,
    is_resource,
    is_wrapper_resource,
)
from pcs.lib.validate import validate_add_remove_items


def validate_move_resources_to_group(
    group_element: _Element,
    resource_element_list: List[_Element],
    adjacent_resource_element: Optional[_Element],
) -> ReportItemList:
    """
    Validates that existing resources can be moved into a group,
    optionally beside an adjacent_resource_element

    group_element -- the group to put resources into
    resource_element_list -- resources that are being moved into the group
    adjacent_resource_element -- put resources beside this one
    """
    report_list: ReportItemList = []

    # Validate types of resources and their parents
    for resource_element in resource_element_list:
        # Only primitive resources can be moved
        if not is_resource(resource_element):
            report_list.append(
                ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        str(resource_element.attrib["id"]),
                        ["primitive"],
                        resource_element.tag,
                    )
                )
            )
        elif is_wrapper_resource(resource_element):
            report_list.append(
                ReportItem.error(
                    reports.messages.CannotGroupResourceWrongType(
                        str(resource_element.attrib["id"]),
                        resource_element.tag,
                        parent_id=None,
                        parent_type=None,
                    )
                )
            )
        else:
            parent = get_parent_resource(resource_element)
            if parent is not None and not group.is_group(parent):
                # At the moment, moving resources out of bundles and clones
                # (or masters) is not possible
                report_list.append(
                    ReportItem.error(
                        reports.messages.CannotGroupResourceWrongType(
                            str(resource_element.attrib["id"]),
                            resource_element.tag,
                            parent_id=str(parent.attrib["id"]),
                            parent_type=parent.tag,
                        )
                    )
                )

    # Validate that elements can be added
    # Check if the group element is a group
    if group.is_group(group_element):
        report_list += validate_add_remove_items(
            [str(resource.attrib["id"]) for resource in resource_element_list],
            [],
            [
                str(resource.attrib["id"])
                for resource in get_inner_resources(group_element)
            ],
            ADD_REMOVE_CONTAINER_TYPE_GROUP,
            ADD_REMOVE_ITEM_TYPE_RESOURCE,
            str(group_element.attrib["id"]),
            str(adjacent_resource_element.attrib["id"])
            if adjacent_resource_element is not None
            else None,
            True,
        )
    else:
        report_list.append(
            ReportItem.error(
                reports.messages.IdBelongsToUnexpectedType(
                    str(group_element.attrib["id"]),
                    expected_types=[group.TAG],
                    current_type=group_element.tag,
                )
            )
        )

    # Elements can always be removed from their old groups, except when the last
    # resource is removed but that is handled in resource.group_add for now, no
    # need to run the validation for removing elements
    return report_list


def move_resources_to_group(
    group_element: _Element,
    primitives_to_place: Iterable[_Element],
    adjacent_resource: Optional[_Element] = None,
    put_after_adjacent: bool = True,
) -> None:
    """
    Put resources into a group or move them within their group

    There is a corner case which is not covered in this function. If the CIB
    contains references to a group or clone which this function deletes,
    they are not deleted and an invalid CIB is generated. These references
    can be constraints, fencing levels etc. - anything that contains group id of
    the deleted group. It is on the caller to detect this corner case and handle
    it appropriately (see group_add in lib/commands/resource.py). For future
    rewrites of this function, it would be better to ask for --force before
    deleting anything that user didn't explicitly ask for - like deleting the
    clone and its associated constraints.

    etree.Element group_element -- the group to put resources into
    iterable primitives_to_place -- resource elements to put into the group
    etree.Element adjacent_resource -- put resources beside this one if set
    bool put_after_adjacent -- put resources after or before the adjacent one
    """
    for resource in primitives_to_place:
        old_parent = resource.getparent()

        # Move a resource to the group.
        if (
            adjacent_resource is not None
            and adjacent_resource.getnext() is not None
            and put_after_adjacent
        ):
            adjacent_resource.getnext().addprevious(resource)  # type: ignore
            adjacent_resource = resource
        elif adjacent_resource is not None and not put_after_adjacent:
            adjacent_resource.addprevious(resource)
        else:
            group_element.append(resource)
            adjacent_resource = resource

        # If the resource was the last resource in another group, that group is
        # now empty and must be deleted. If the group is in a clone element,
        # delete that as well.
        if (
            old_parent is not None
            and group.is_group(old_parent)  # do not delete resources element
            and not group.get_inner_resources(old_parent)
        ):
            old_grandparent = old_parent.getparent()
            if old_grandparent is not None:
                old_great_grandparent = old_grandparent.getparent()
                if (
                    clone.is_any_clone(old_grandparent)
                    and old_great_grandparent is not None
                ):
                    old_great_grandparent.remove(old_grandparent)
                else:
                    old_grandparent.remove(old_parent)
