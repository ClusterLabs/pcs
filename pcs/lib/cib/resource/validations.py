from dataclasses import dataclass
from typing import (
    List,
    Optional,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.validate import validate_add_remove_items

from . import group
from .bundle import (
    get_parent_bundle,
    is_bundle,
)
from .clone import (
    get_parent_any_clone,
    is_any_clone,
    is_master,
    is_promotable_clone,
)
from .common import (
    get_inner_resources,
    get_parent_resource,
    is_resource,
    is_wrapper_resource,
)
from .stonith import is_stonith


def validate_move_resources_to_group(
    group_element: _Element,
    resource_element_list: List[_Element],
    adjacent_resource_element: Optional[_Element],
) -> reports.ReportItemList:
    """
    Validates that existing resources can be moved into a group,
    optionally beside an adjacent_resource_element

    group_element -- the group to put resources into
    resource_element_list -- resources that are being moved into the group
    adjacent_resource_element -- put resources beside this one
    """
    report_list: reports.ReportItemList = []

    # Validate types of resources and their parents
    for resource_element in resource_element_list:
        # Only primitive resources can be moved
        if not is_resource(resource_element):
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        str(resource_element.attrib["id"]),
                        ["primitive"],
                        resource_element.tag,
                    )
                )
            )
        elif is_wrapper_resource(resource_element):
            report_list.append(
                reports.ReportItem.error(
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
                    reports.ReportItem.error(
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
            reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
            reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
            str(group_element.attrib["id"]),
            str(adjacent_resource_element.attrib["id"])
            if adjacent_resource_element is not None
            else None,
            True,
        )
    else:
        report_list.append(
            reports.ReportItem.error(
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


def validate_move(
    resource_element: _Element, master: bool
) -> reports.ReportItemList:
    """
    Validate moving a resource to a node

    resource_element -- the resource to be moved
    master -- limit moving to the master role
    """
    report_list = []

    if is_stonith(resource_element):
        report_list.append(
            reports.ReportItem.deprecation(
                reports.messages.ResourceStonithCommandsMismatch(
                    "stonith device"
                )
            )
        )

    analysis = _validate_move_ban_clear_analyzer(resource_element)

    if analysis.is_in_bundle:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotMoveResourceBundleInner(
                    str(resource_element.get("id")),
                    bundle_id=str(analysis.bundle_id),
                )
            )
        )

    if analysis.is_bundle:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotMoveResourceBundle(
                    str(resource_element.get("id"))
                )
            )
        )
        return report_list

    if (analysis.is_clone or analysis.is_in_clone) and not (
        analysis.is_promotable_clone or analysis.is_in_promotable_clone
    ):
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotMoveResourceClone(
                    str(resource_element.get("id"))
                )
            )
        )
        return report_list

    # Allow moving both promoted and demoted instances of promotable clones
    # (analysis.is_promotable_clone). Do not allow to move promoted instances
    # of promotables' inner resources (analysis.is_in_promotable_clone) as that
    # would create a constraint for the promoted role of a group or a primitive
    # which would not make sense if the group or primitive is later moved out
    # of its promotable clone. To be consistent, we do not allow to move
    # demoted instances of promotables' inner resources either. See
    # rhbz#1875301 for details.
    if not master and analysis.is_in_promotable_clone:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotMoveResourcePromotableInner(
                    str(resource_element.get("id")),
                    str(analysis.promotable_clone_id),
                )
            )
        )
    elif master and not analysis.is_promotable_clone:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotMoveResourceMasterResourceNotPromotable(
                    str(resource_element.get("id")),
                    promotable_id=analysis.promotable_clone_id or "",
                )
            )
        )

    return report_list


def validate_ban(
    resource_element: _Element, master: bool
) -> reports.ReportItemList:
    """
    Validate banning a resource on a node

    resource_element -- the resource to be banned
    master -- limit banning to the master role
    """
    report_list = []

    if is_stonith(resource_element):
        report_list.append(
            reports.ReportItem.deprecation(
                reports.messages.ResourceStonithCommandsMismatch(
                    "stonith device"
                )
            )
        )

    analysis = _validate_move_ban_clear_analyzer(resource_element)

    if analysis.is_in_bundle:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotBanResourceBundleInner(
                    str(resource_element.get("id")),
                    bundle_id=str(analysis.bundle_id),
                )
            )
        )

    if master and not analysis.is_promotable_clone:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotBanResourceMasterResourceNotPromotable(
                    str(resource_element.get("id")),
                    promotable_id=analysis.promotable_clone_id or "",
                )
            )
        )

    return report_list


def validate_unmove_unban(
    resource_element: _Element, master: bool
) -> reports.ReportItemList:
    """
    Validate unmoving/unbanning a resource to/on nodes

    resource_element -- the resource to be unmoved/unbanned
    master -- limit unmoving/unbanning to the master role
    """
    report_list = []

    if is_stonith(resource_element):
        report_list.append(
            reports.ReportItem.deprecation(
                reports.messages.ResourceStonithCommandsMismatch(
                    "stonith device"
                )
            )
        )

    analysis = _validate_move_ban_clear_analyzer(resource_element)

    if master and not analysis.is_promotable_clone:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable(
                    str(resource_element.get("id")),
                    promotable_id=analysis.promotable_clone_id or "",
                )
            )
        )

    return report_list


@dataclass(frozen=True)
class _MoveBanClearAnalysis:
    # pylint: disable=too-many-instance-attributes
    is_bundle: bool
    is_in_bundle: bool
    is_clone: bool
    is_in_clone: bool
    is_promotable_clone: bool
    is_in_promotable_clone: bool
    promotable_clone_id: Optional[str]
    bundle_id: Optional[str]


def _validate_move_ban_clear_analyzer(
    resource_element: _Element,
) -> _MoveBanClearAnalysis:
    resource_is_bundle = False
    resource_is_in_bundle = False
    resource_is_clone = False
    resource_is_in_clone = False
    resource_is_promotable_clone = False
    resource_is_in_promotable_clone = False
    promotable_clone_element = None
    bundle_element = None

    parent_bundle = get_parent_bundle(resource_element)
    parent_clone = get_parent_any_clone(resource_element)

    if is_bundle(resource_element):
        resource_is_bundle = True
        bundle_element = resource_element
    elif is_any_clone(resource_element):
        resource_is_clone = True
        if is_master(resource_element) or is_promotable_clone(resource_element):
            resource_is_promotable_clone = True
            promotable_clone_element = resource_element
    elif parent_bundle is not None:
        resource_is_in_bundle = True
        bundle_element = parent_bundle
    elif parent_clone is not None:
        resource_is_in_clone = True
        if is_master(parent_clone) or is_promotable_clone(parent_clone):
            resource_is_in_promotable_clone = True
            promotable_clone_element = parent_clone
    return _MoveBanClearAnalysis(
        resource_is_bundle,
        resource_is_in_bundle,
        resource_is_clone,
        resource_is_in_clone,
        resource_is_promotable_clone,
        resource_is_in_promotable_clone,
        (
            promotable_clone_element.get("id")
            if promotable_clone_element is not None
            else None
        ),
        bundle_element.get("id") if bundle_element is not None else None,
    )
