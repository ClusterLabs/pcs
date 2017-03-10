from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.cib import nvpair
from pcs.lib.cib.resource.clone import (
    is_any_clone,
    get_inner_resource,
)


def disable_meta(meta_attributes):
    """
    Return new dict with meta attributes containing values to disable resource.

    dict meta_attributes are current meta attributes
    """
    disabled_meta_attributes = meta_attributes.copy()
    disabled_meta_attributes["target-role"] = "Stopped"
    return disabled_meta_attributes

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

def find_resources_to_enable(resource_el):
    """
    Get resources to enable in order to enable specified resource succesfully
    etree resource_el -- resource element
    """
    if is_any_clone(resource_el):
        return [resource_el, get_inner_resource(resource_el)]

    to_enable = [resource_el]
    parent = resource_el.getparent()
    if is_any_clone(parent):
        to_enable.append(parent)
    return to_enable

def enable(resource_el):
    """
    Enable specified resource
    etree resource_el -- resource element
    """
    meta_attributes_el_list = resource_el.xpath("./meta_attributes")
    if not meta_attributes_el_list:
        # If there are no meta_attributes, the resource is not disabled. We do
        # not want to create an empty meta_attributes element, so we return
        # early.
        return
    meta_attributes_el = meta_attributes_el_list[0]
    nvpair.update_nvset(
        meta_attributes_el,
        {
            "target-role": "",
        }
    )
    # remove empty meta_attributes
    if not list(meta_attributes_el):
        resource_el.remove(meta_attributes_el)

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
