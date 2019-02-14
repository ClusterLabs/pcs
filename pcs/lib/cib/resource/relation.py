from pcs.lib import reports
from pcs.lib.cib.resource import (
    clone,
    group,
    primitive,
)

def validate_move_resources_to_group(
    group_element, primitives_to_place, adjacent_resource=None,
    missing_adjacent_resource_specified=False
):
    """
    Validate putting resources into a group or moving them within their group

    etree.Element group_element -- the group to put resources into
    iterable primitives_to_place -- resource elements to put into the group
    etree.Element adjacent_resource -- put resources beside this one if set
    bool missing_adjacent_resource_specified -- an adjacent resource has been
        specified but it does not exist
    """
    # pylint: disable=too-many-branches
    report_list = []

    if not group.is_group(group_element):
        report_list.append(
            reports.id_belongs_to_unexpected_type(
                group_element.attrib.get("id"),
                expected_types=[group.TAG],
                current_type=group_element.tag
            )
        )

    if not primitives_to_place:
        report_list.append(reports.cannot_group_resource_no_resources())
        return report_list

    resources_already_in_the_group = set()
    resources_count = dict()
    for resource in primitives_to_place:
        resource_id = resource.attrib.get("id")
        if not primitive.is_primitive(resource):
            report_list.append(
                reports.cannot_group_resource_wrong_type(
                    resource_id,
                    resource.tag
                )
            )
            continue
        resources_count[resource_id] = resources_count.get(resource_id, 0) + 1
        parent = resource.getparent()
        if parent is not None:
            if group.is_group(parent):
                if (
                    adjacent_resource is None
                    and
                    not missing_adjacent_resource_specified
                    and
                    parent.attrib.get("id") == group_element.attrib.get("id")
                ):
                    resources_already_in_the_group.add(resource_id)
            elif parent.tag != "resources":
                # if the primitive is not in a 'group' or 'resources' tag, it
                # is either in a clone, master, bundle or similar tag and
                # cannot be put into a group
                report_list.append(
                    reports.cannot_group_resource_wrong_type(
                        resource_id,
                        parent.tag
                    )
                )
    if resources_already_in_the_group:
        report_list.append(
            reports.cannot_group_resource_already_in_the_group(
                resources_already_in_the_group,
                group_element.attrib.get("id")
            )
        )
    more_than_once_resources = [
        resource for resource, count in resources_count.items()
        if count > 1
    ]
    if more_than_once_resources:
        report_list.append(
            reports.cannot_group_resource_more_than_once(
                more_than_once_resources
            )
        )

    if adjacent_resource is not None:
        adjacent_parent = adjacent_resource.getparent()
        if not (
            adjacent_parent is not None
            and
            group.is_group(adjacent_parent)
            and
            adjacent_parent.attrib.get("id") == group_element.attrib.get("id")
        ):
            report_list.append(
                reports.cannot_group_resource_adjacent_resource_not_in_group(
                    adjacent_resource.attrib.get("id"),
                    group_element.attrib.get("id")
                )
            )
        for resource in primitives_to_place:
            if adjacent_resource.attrib.get("id") == resource.attrib.get("id"):
                report_list.append(
                    reports.cannot_group_resource_next_to_itself(
                        adjacent_resource.attrib.get("id"),
                        group_element.attrib.get("id"),
                    )
                )
                break

    return report_list

def move_resources_to_group(
    group_element, primitives_to_place, adjacent_resource=None,
    put_after_adjacent=True
):
    """
    Put resources into a group or move them within their group

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
            and
            adjacent_resource.getnext() is not None
            and
            put_after_adjacent
        ):
            adjacent_resource.getnext().addprevious(resource)
            adjacent_resource = resource
        elif (
            adjacent_resource is not None
            and
            not put_after_adjacent
        ):
            adjacent_resource.addprevious(resource)
        else:
            group_element.append(resource)
            adjacent_resource = resource

        # If the resource was the last resource in another group, that group is
        # now empty and must be deleted. If the group is in a clone element,
        # delete that as well.
        if (
            old_parent is not None
            and
            group.is_group(old_parent)
            and
            not group.get_inner_resources(old_parent)
            and
            old_parent.getparent() is not None
        ):
            old_grandparent = old_parent.getparent()
            if (
                clone.is_any_clone(old_grandparent)
                and
                old_grandparent.getparent() is not None
            ):
                old_grandparent.getparent().remove(old_grandparent)
            else:
                old_grandparent.remove(old_parent)
