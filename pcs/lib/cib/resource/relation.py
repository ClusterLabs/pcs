from pcs.lib import reports
from pcs.lib.cib.resource import (
    clone,
    group,
    primitive,
)

def validate_move_resources_to_group(
    group_element, primitives_to_place, adjacent_resource=None
):
    """
    Validate putting resources into a group or moving them within their group

    etree.Element group_element -- the group to put resources into
    iterable primitives_to_place -- resource elements to put into the group
    etree.Element adjacent_resource -- put resources beside this one if set
    """
    if not primitives_to_place:
        return [reports.cannot_group_resource_no_resources()]

    report_list = []

    resources_already_in_the_group = set()
    for resource in primitives_to_place:
        if not primitive.is_primitive(resource):
            report_list.append(
                reports.cannot_group_resource_wrong_type(
                    resource.attrib.get("id"),
                    resource.tag
                )
            )
            continue
        parent = resource.getparent()
        if parent is not None:
            if group.is_group(parent):
                if (
                    adjacent_resource is None
                    and
                    parent.attrib.get("id") == group_element.attrib.get("id")
                ):
                    resources_already_in_the_group.add(
                        resource.attrib.get("id")
                    )
            elif parent.tag != "resources":
                # if the primitive is not in a 'group' or 'resources' tag, it
                # is either in a clone, master, bundle or similar tag and
                # cannot be put into a group
                report_list.append(
                    reports.cannot_group_resource_wrong_type(
                        resource.attrib.get("id"),
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
