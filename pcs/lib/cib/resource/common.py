from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


from pcs.lib.cib import nvpair
from pcs.lib.cib.resource.bundle import (
    is_bundle,
    get_inner_resource as get_bundle_inner_resource,
)
from pcs.lib.cib.resource.clone import (
    is_any_clone,
    get_inner_resource as get_clone_inner_resource,
)
from pcs.lib.cib.resource.group import (
    is_group,
    get_inner_resources as get_group_inner_resources,
)
from pcs.lib.cib.resource.primitive import is_primitive
from pcs.lib.xml_tools import find_parent


def are_meta_disabled(meta_attributes):
    return meta_attributes.get("target-role", "Started").lower() == "stopped"

def _can_be_evaluated_as_positive_num(value):
    string_wo_leading_zeros = str(value).lstrip("0")
    return string_wo_leading_zeros and string_wo_leading_zeros[0].isdigit()

def is_clone_deactivated_by_meta(meta_attributes):
    return are_meta_disabled(meta_attributes) or any([
        not _can_be_evaluated_as_positive_num(meta_attributes.get(key, "1"))
        for key in ["clone-max", "clone-node-max"]
    ])

def find_primitives(resource_el):
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

def enable(resource_el):
    """
    Enable specified resource
    etree resource_el -- resource element
    """
    nvpair.arrange_first_nvset(
        "meta_attributes",
        resource_el,
        {
            "target-role": "",
        }
    )

def disable(resource_el):
    """
    Disable specified resource
    etree resource_el -- resource element
    """
    nvpair.arrange_first_nvset(
        "meta_attributes",
        resource_el,
        {
            "target-role": "Stopped",
        }
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
    # Bundle resources cannot be set as unmanaged - pcmk currently doesn't
    # support that. Resources in a bundle are supposed to be treated separately.
    if is_bundle(resource_el):
        return []
    res_id = resource_el.attrib["id"]
    return (
        [resource_el] # the resource itself
        +
        # its parents
        find_parent(resource_el, "resources").xpath(
            """
                (./master|./clone)[(group|group/primitive|primitive)[@id='{r}']]
                |
                //group[primitive[@id='{r}']]
            """
            .format(r=res_id)
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
    # a bundled primitive - the bundle - nothing
    #  bundles currently cannot be set as unmanaged - pcmk does not support that
    # an empty bundle - the bundle - nothing
    #  bundles currently cannot be set as unmanaged - pcmk does not support that
    if is_any_clone(resource_el):
        resource_el = get_clone_inner_resource(resource_el)
    if is_group(resource_el):
        return get_group_inner_resources(resource_el)
    if is_primitive(resource_el):
        return [resource_el]
    return []

def manage(resource_el):
    """
    Set the resource to be managed by the cluster
    etree resource_el -- resource element
    """
    nvpair.arrange_first_nvset(
        "meta_attributes",
        resource_el,
        {
            "is-managed": "",
        }
    )

def unmanage(resource_el):
    """
    Set the resource not to be managed by the cluster
    etree resource_el -- resource element
    """
    nvpair.arrange_first_nvset(
        "meta_attributes",
        resource_el,
        {
            "is-managed": "false",
        }
    )
