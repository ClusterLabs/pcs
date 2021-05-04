from collections import namedtuple
from typing import (
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports.item import ReportItem, ReportItemList
from pcs.lib.cib import nvpair
from pcs.lib.cib.resource.bundle import (
    TAG as TAG_BUNDLE,
    is_bundle,
    get_inner_resource as get_bundle_inner_resource,
)
from pcs.lib.cib.resource.clone import (
    ALL_TAGS as TAG_CLONE_ALL,
    get_inner_resource as get_clone_inner_resource,
    get_parent_any_clone,
    is_any_clone,
    is_master,
    is_promotable_clone,
)
from pcs.lib.cib.resource.group import (
    TAG as TAG_GROUP,
    is_group,
    get_inner_resources as get_group_inner_resources,
)
from pcs.lib.cib.resource.primitive import (
    TAG as TAG_PRIMITIVE,
    is_primitive,
)
from pcs.lib.cib.tools import ElementSearcher
from pcs.lib.xml_tools import find_parent


ALL_RESOURCE_XML_TAGS = sorted(
    TAG_CLONE_ALL + [TAG_GROUP, TAG_PRIMITIVE, TAG_BUNDLE]
)


def are_meta_disabled(meta_attributes):
    return meta_attributes.get("target-role", "Started").lower() == "stopped"


def _can_be_evaluated_as_positive_num(value):
    string_wo_leading_zeros = str(value).lstrip("0")
    return string_wo_leading_zeros and string_wo_leading_zeros[0].isdigit()


def is_clone_deactivated_by_meta(meta_attributes):
    return are_meta_disabled(meta_attributes) or any(
        not _can_be_evaluated_as_positive_num(meta_attributes.get(key, "1"))
        for key in ["clone-max", "clone-node-max"]
    )


def find_one_resource(
    context_element: _Element,
    resource_id: str,
    resource_tags: Optional[Iterable[str]] = None,
) -> Tuple[Optional[_Element], ReportItemList]:
    """
    Find a single resource or return None if not found

    context_element -- an element to be searched in
    resource_id -- id of an element to find
    resource_tags -- types of resources to look for, default all types
    """
    resource_el_list, report_list = find_resources(
        context_element,
        [resource_id],
        resource_tags=resource_tags,
    )
    resource = resource_el_list[0] if resource_el_list else None
    return resource, report_list


def find_resources(
    context_element: _Element,
    resource_ids: Iterable[str],
    resource_tags: Optional[Iterable[str]] = None,
) -> Tuple[List[_Element], ReportItemList]:
    """
    Find a list of resource

    context_element -- an element to be searched in
    resource_id -- id of an element to find
    resource_tags -- types of resources to look for, default all types
    """
    report_list: ReportItemList = []
    if resource_tags is None:
        resource_tags = ALL_RESOURCE_XML_TAGS
    resource_el_list = []
    for res_id in resource_ids:
        searcher = ElementSearcher(resource_tags, res_id, context_element)
        if searcher.element_found():
            resource_el_list.append(searcher.get_element())
        else:
            report_list.extend(searcher.get_errors())
    return resource_el_list, report_list


def find_primitives(resource_el: _Element) -> List[_Element]:
    """
    Get list of primitives contained in a given resource
    etree resource_el -- resource element
    """
    if is_bundle(resource_el):
        in_bundle = get_bundle_inner_resource(resource_el)
        return [in_bundle] if in_bundle is not None else []
    if is_any_clone(resource_el):
        resource_el = get_clone_inner_resource(resource_el)
    if is_group(resource_el):
        return get_group_inner_resources(resource_el)
    if is_primitive(resource_el):
        return [resource_el]
    return []


def get_all_inner_resources(resource_el: _Element) -> Set[_Element]:
    """
    Return all inner resources (both direct and indirect) of a resource
    Example: for a clone containing a group, this function will return both
    the group and the resources inside the group

    resource_el -- resource element to get its inner resources
    """
    all_inner: Set[_Element] = set()
    to_process = set([resource_el])
    while to_process:
        new_inner = get_inner_resources(to_process.pop())
        to_process.update(set(new_inner) - all_inner)
        all_inner.update(new_inner)
    return all_inner


def get_inner_resources(resource_el: _Element) -> List[_Element]:
    """
    Return list of inner resources (direct descendants) of a resource
    specified as resource_el.
    Example: for clone containing a group, this function will return only
    group and not resource inside the group

    resource_el -- resource element to get its inner resources
    """
    if is_bundle(resource_el):
        in_bundle = get_bundle_inner_resource(resource_el)
        return [in_bundle] if in_bundle is not None else []
    if is_any_clone(resource_el):
        return [get_clone_inner_resource(resource_el)]
    if is_group(resource_el):
        return get_group_inner_resources(resource_el)
    return []


def is_wrapper_resource(resource_el: _Element) -> bool:
    """
    Return True for resource_el of types that can contain other resource(s)
    (these are: group, bundle, clone) and False otherwise.

    resource_el -- resource element to check
    """
    return (
        is_group(resource_el)
        or is_bundle(resource_el)
        or is_any_clone(resource_el)
    )


def get_parent_resource(resource_el: _Element) -> Optional[_Element]:
    """
    Return a direct ancestor of a specified resource or None if the resource
    has no ancestor.
    Example: for a resource in group which is in clone, this function will
    return group element.

    resource_el -- resource element of which parent resource should be returned
    """
    parent_el = resource_el.getparent()
    if parent_el is not None and is_wrapper_resource(parent_el):
        return parent_el
    return None


def find_resources_to_enable(resource_el):
    """
    Get resources to enable in order to enable specified resource succesfully
    etree resource_el -- resource element
    """
    if is_bundle(resource_el):
        to_enable = [resource_el]
        in_bundle = get_bundle_inner_resource(resource_el)
        if in_bundle is not None:
            to_enable.append(in_bundle)
        return to_enable

    if is_any_clone(resource_el):
        return [resource_el, get_clone_inner_resource(resource_el)]

    to_enable = [resource_el]
    parent = resource_el.getparent()
    if is_any_clone(parent) or is_bundle(parent):
        to_enable.append(parent)
    return to_enable


def enable(resource_el, id_provider):
    """
    Enable specified resource
    etree resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {
            "target-role": "",
        },
        id_provider,
    )


def disable(resource_el, id_provider):
    """
    Disable specified resource
    etree resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {
            "target-role": "Stopped",
        },
        id_provider,
    )


def find_resources_to_manage(resource_el):
    """
    Get resources to manage to manage the specified resource succesfully
    etree resource_el -- resource element
    """
    # If the resource_el is a primitive in a group, we set both the group and
    # the primitive to managed mode. Otherwise the resource_el, all its
    # children and parents need to be set to managed mode. We do it to make
    # sure to remove the unmanaged flag form the whole tree. The flag could be
    # put there manually. If we didn't do it, the resource may stay unmanaged,
    # as a managed primitive in an unmanaged clone / group is still unmanaged
    # and vice versa.
    res_id = resource_el.attrib["id"]
    return (
        [resource_el]  # the resource itself
        +
        # its parents
        find_parent(resource_el, "resources").xpath(
            # a master or a clone which contains a group, a primitve, or a
            # grouped primitive with the specified id
            # OR
            # a group (in a clone, master, etc. - hence //) which contains a
            # primitive with the specified id
            # OR
            # a bundle which contains a primitive with the specified id
            """
                (./master|./clone)[(group|group/primitive|primitive)[@id='{r}']]
                |
                //group[primitive[@id='{r}']]
                |
                ./bundle[primitive[@id='{r}']]
            """.format(
                r=res_id
            )
        )
        +
        # its children
        resource_el.xpath("(./group|./primitive|./group/primitive)")
    )


def find_resources_to_unmanage(resource_el):
    """
    Get resources to unmanage to unmanage the specified resource succesfully
    etree resource_el -- resource element
    """
    # resource hierarchy - specified resource - what to return
    # a primitive - the primitive - the primitive
    #
    # a cloned primitive - the primitive - the primitive
    # a cloned primitive - the clone - the primitive
    #   The resource will run on all nodes after unclone. However that doesn't
    #   seem to be bad behavior. Moreover, if monitor operations were disabled,
    #   they wouldn't enable on unclone, but the resource would become managed,
    #   which is definitely bad.
    #
    # a primitive in a group - the primitive - the primitive
    #   Otherwise all primitives in the group would become unmanaged.
    # a primitive in a group - the group - all primitives in the group
    #   If only the group was set to unmanaged, setting any primitive in the
    #   group to managed would set all the primitives in the group to managed.
    #   If the group as well as all its primitives were set to unmanaged, any
    #   primitive added to the group would become unmanaged. This new primitive
    #   would become managed if any original group primitive becomes managed.
    #   Therefore changing one primitive influences another one, which we do
    #   not want to happen.
    #
    # a primitive in a cloned group - the primitive - the primitive
    # a primitive in a cloned group - the group - all primitives in the group
    #   See group notes above
    # a primitive in a cloned group - the clone - all primitives in the group
    #   See clone notes above
    #
    # a bundled primitive - the primitive - the primitive
    # a bundled primitive - the bundle - the bundle and the primitive
    #  We need to unmanage implicit resources create by pacemaker and there is
    #  no other way to do it than unmanage the bundle itself.
    #  Since it is not possible to unbundle a resource, the concers described
    #  at unclone don't apply here. However to prevent future bugs, in case
    #  unbundling becomes possible, we unmanage the primitive as well.
    # an empty bundle - the bundle - the bundle
    #  There is nothing else to unmanage.
    if is_bundle(resource_el):
        in_bundle = get_bundle_inner_resource(resource_el)
        return (
            [resource_el, in_bundle] if in_bundle is not None else [resource_el]
        )
    if is_any_clone(resource_el):
        resource_el = get_clone_inner_resource(resource_el)
    if is_group(resource_el):
        return get_group_inner_resources(resource_el)
    if is_primitive(resource_el):
        return [resource_el]
    return []


def manage(resource_el, id_provider):
    """
    Set the resource to be managed by the cluster
    etree resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {
            "is-managed": "",
        },
        id_provider,
    )


def unmanage(resource_el, id_provider):
    """
    Set the resource not to be managed by the cluster
    etree resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {
            "is-managed": "false",
        },
        id_provider,
    )


def find_resources_to_delete(resource_el: _Element) -> List[_Element]:
    """
    Get resources to delete, children and parents of the given resource if
    necessary.

    If element is a primitive which is in a clone and you specify one of them,
    you will get elements for both of them. If you specify group element which
    is in a clone then will you get clone, group, and all primitive elements in
    a group and etc.

    resource_el - resource element (bundle, clone, group, primitive)
    """
    result = [resource_el]
    # childrens of bundle, clone, group, clone-with-group
    inner_resource_list = get_inner_resources(resource_el)
    if inner_resource_list:
        result.extend(inner_resource_list)
        inner_resource = inner_resource_list[0]
        if is_group(inner_resource):
            result.extend(get_inner_resources(inner_resource))
    # parents of primitive if needed (group, clone)
    parent_el = get_parent_resource(resource_el)
    if parent_el is None or is_bundle(parent_el):
        return result
    if is_any_clone(parent_el):
        result.insert(0, parent_el)
    if is_group(parent_el):
        group_inner_resources = get_group_inner_resources(parent_el)
        if len(group_inner_resources) <= 1:
            result = [parent_el] + group_inner_resources
            clone_el = get_parent_resource(parent_el)
            if clone_el is not None:
                result.insert(0, clone_el)
    return result


def validate_move(resource_element, master):
    """
    Validate moving a resource to a node

    etree resource_element -- the resource to be moved
    bool master -- limit moving to the master role
    """
    report_list = []
    analysis = _validate_move_ban_clear_analyzer(resource_element)

    if analysis.is_bundle:
        report_list.append(
            ReportItem.error(
                reports.messages.CannotMoveResourceBundle(
                    resource_element.get("id")
                )
            )
        )
        return report_list

    if (analysis.is_clone or analysis.is_in_clone) and not (
        analysis.is_promotable_clone or analysis.is_in_promotable_clone
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.CannotMoveResourceClone(
                    resource_element.get("id")
                )
            )
        )
        return report_list

    # Allow moving both promoted and demoted instances of promotable clones
    # (analysis.is_promotable_clone). Do not allow to move promoted instances
    # of promotables' inner resources (analysis.is_in_promotable_clone) as that
    # would create a constraint for the promoted role of a group or a primitve
    # which would not make sense if the group or primitive is later moved out
    # of its promotable clone. To be consistent, we do not allow to move
    # demoted instances of promotables' inner resources either. See
    # rhbz#1875301 for details.
    if not master and analysis.is_in_promotable_clone:
        report_list.append(
            ReportItem.error(
                reports.messages.CannotMoveResourcePromotableInner(
                    resource_element.get("id"),
                    analysis.promotable_clone_id,
                )
            )
        )
    elif master and not analysis.is_promotable_clone:
        report_list.append(
            ReportItem.error(
                reports.messages.CannotMoveResourceMasterResourceNotPromotable(
                    resource_element.get("id"),
                    promotable_id=analysis.promotable_clone_id,
                )
            )
        )

    return report_list


def validate_ban(resource_element, master):
    """
    Validate banning a resource on a node

    etree resource_element -- the resource to be banned
    bool master -- limit banning to the master role
    """
    report_list = []
    analysis = _validate_move_ban_clear_analyzer(resource_element)

    if master and not analysis.is_promotable_clone:
        report_list.append(
            ReportItem.error(
                reports.messages.CannotBanResourceMasterResourceNotPromotable(
                    resource_element.get("id"),
                    promotable_id=analysis.promotable_clone_id,
                )
            )
        )

    return report_list


def validate_unmove_unban(resource_element, master):
    """
    Validate unmoving/unbanning a resource to/on nodes

    etree resource_element -- the resource to be unmoved/unbanned
    bool master -- limit unmoving/unbanning to the master role
    """
    report_list = []
    analysis = _validate_move_ban_clear_analyzer(resource_element)

    if master and not analysis.is_promotable_clone:
        # pylint: disable=line-too-long
        report_list.append(
            ReportItem.error(
                reports.messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable(
                    resource_element.get("id"),
                    promotable_id=analysis.promotable_clone_id,
                )
            )
        )

    return report_list


class _MoveBanClearAnalysis(
    namedtuple(
        "_MoveBanClearAnalysis",
        [
            "is_bundle",
            "is_clone",
            "is_in_clone",
            "is_promotable_clone",
            "is_in_promotable_clone",
            "promotable_clone_id",
        ],
    )
):
    pass


def _validate_move_ban_clear_analyzer(resource_element):
    resource_is_bundle = False
    resource_is_clone = False
    resource_is_in_clone = False
    resource_is_promotable_clone = False
    resource_is_in_promotable_clone = False
    promotable_clone_element = None

    if is_bundle(resource_element):
        resource_is_bundle = True
    elif is_any_clone(resource_element):
        resource_is_clone = True
        if is_master(resource_element) or is_promotable_clone(resource_element):
            resource_is_promotable_clone = True
            promotable_clone_element = resource_element
    elif get_parent_any_clone(resource_element) is not None:
        parent_clone = get_parent_any_clone(resource_element)
        resource_is_in_clone = True
        if is_master(parent_clone) or is_promotable_clone(parent_clone):
            resource_is_in_promotable_clone = True
            promotable_clone_element = parent_clone
    return _MoveBanClearAnalysis(
        resource_is_bundle,
        resource_is_clone,
        resource_is_in_clone,
        resource_is_promotable_clone,
        resource_is_in_promotable_clone,
        (
            promotable_clone_element.get("id")
            if promotable_clone_element is not None
            else None
        ),
    )
