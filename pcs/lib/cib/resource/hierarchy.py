from typing import (
    Iterable,
    Optional,
)

from lxml.etree import _Element

from . import (
    clone,
    group,
)


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
