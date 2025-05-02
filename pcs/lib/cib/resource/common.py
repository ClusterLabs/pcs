from typing import (
    List,
    Optional,
    Set,
    Tuple,
    cast,
)

from lxml.etree import _Element

from pcs.common.reports.item import ReportItemList
from pcs.common.types import StringCollection
from pcs.lib.cib import nvpair
from pcs.lib.cib.const import TAG_LIST_RESOURCE
from pcs.lib.cib.tools import (
    ElementSearcher,
    IdProvider,
)
from pcs.lib.xml_tools import find_parent

from .bundle import get_inner_resource as get_bundle_inner_resource
from .bundle import is_bundle
from .clone import (
    get_inner_primitives as get_clone_inner_primitive_resources,
)
from .clone import get_inner_resource as get_clone_inner_resource
from .clone import is_any_clone
from .group import get_inner_resources as get_group_inner_resources
from .group import is_group
from .primitive import is_primitive


# DEPRECATED, use get_element_by_id
def find_one_resource(
    context_element: _Element,
    resource_id: str,
    resource_tags: Optional[StringCollection] = None,
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


# DEPRECATED, use get_elements_by_ids
# Issue: produces report with CIB tags when wrong element type was found
def find_resources(
    context_element: _Element,
    resource_ids: StringCollection,
    resource_tags: Optional[StringCollection] = None,
) -> Tuple[List[_Element], ReportItemList]:
    """
    Find a list of resources

    context_element -- an element to be searched in
    resource_id -- id of an element to find
    resource_tags -- types of resources to look for, default all types
    """
    report_list: ReportItemList = []
    if resource_tags is None:
        resource_tags = TAG_LIST_RESOURCE
    resource_el_list = []
    for res_id in resource_ids:
        searcher = ElementSearcher(resource_tags, res_id, context_element)
        found_element = searcher.get_element()
        if found_element is not None:
            resource_el_list.append(found_element)
        else:
            report_list.extend(searcher.get_errors())
    return resource_el_list, report_list


def find_primitives(resource_el: _Element) -> List[_Element]:
    """
    Get list of primitives contained in a given resource

    resource_el -- resource element
    """
    if is_bundle(resource_el):
        in_bundle = get_bundle_inner_resource(resource_el)
        return [in_bundle] if in_bundle is not None else []
    if is_any_clone(resource_el):
        return get_clone_inner_primitive_resources(resource_el)
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
    to_process = {resource_el}
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


def is_resource(element: _Element) -> bool:
    """
    Return True for any resource, False otherwise, like meta_attributes element.

    element -- element to check
    """
    return element.tag in TAG_LIST_RESOURCE


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


def find_resources_to_enable(resource_el: _Element) -> List[_Element]:
    """
    Get resources to enable in order to enable specified resource successfully

    resource_el -- resource element
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
    if parent is not None and (is_any_clone(parent) or is_bundle(parent)):
        to_enable.append(parent)
    return to_enable


def enable(resource_el: _Element, id_provider: IdProvider) -> None:
    """
    Enable specified resource

    resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {"target-role": ""},
        id_provider,
    )


def disable(resource_el: _Element, id_provider: IdProvider) -> None:
    """
    Disable specified resource

    resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {"target-role": "Stopped"},
        id_provider,
    )


def is_disabled(resource_el: _Element) -> bool:
    """
    Is the resource disabled by its own meta? (Doesn't check parent resources.)
    """
    return (
        nvpair.get_value(
            nvpair.META_ATTRIBUTES_TAG, resource_el, "target-role", default=""
        ).lower()
        == "stopped"
    )


def find_resources_to_manage(resource_el: _Element) -> List[_Element]:
    """
    Get resources to set to managed for the specified resource to become managed

    resource_el -- resource element
    """
    # If the resource_el is a primitive in a group, we set both the group and
    # the primitive to managed mode. Otherwise the resource_el, all its
    # children and parents need to be set to managed mode. We do it to make
    # sure to remove the unmanaged flag form the whole tree. The flag could be
    # put there manually. If we didn't do it, the resource may stay unmanaged,
    # as a managed primitive in an unmanaged clone / group is still unmanaged
    # and vice versa.
    res_id = resource_el.attrib["id"]
    parent_el = []
    top_element = find_parent(resource_el, {"resources"})
    if top_element is not None:
        parent_el = cast(
            List[_Element],
            top_element.xpath(
                # a master or a clone which contains a group, a primitive, or a
                # grouped primitive with the specified id
                # OR
                # a group (in a clone, master, etc. - hence //) which contains a
                # primitive with the specified id
                # OR
                # a bundle which contains a primitive with the specified id
                """
                (./master|./clone)[(group|group/primitive|primitive)[@id=$r]]
                |
                //group[primitive[@id=$r]]
                |
                ./bundle[primitive[@id=$r]]
                """,
                r=res_id,
            ),
        )
    children_el = cast(
        List[_Element],
        resource_el.xpath("(./group|./primitive|./group/primitive)"),
    )
    return [resource_el] + parent_el + children_el


def find_resources_to_unmanage(resource_el: _Element) -> List[_Element]:
    """
    Get resources to unmanage to unmanage the specified resource successfully

    resource_el -- resource element
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


def manage(resource_el: _Element, id_provider: IdProvider) -> None:
    """
    Set the resource to be managed by the cluster

    resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {"is-managed": ""},
        id_provider,
    )


def unmanage(resource_el: _Element, id_provider: IdProvider) -> None:
    """
    Set the resource not to be managed by the cluster

    resource_el -- resource element
    """
    nvpair.arrange_first_meta_attributes(
        resource_el,
        {"is-managed": "false"},
        id_provider,
    )
