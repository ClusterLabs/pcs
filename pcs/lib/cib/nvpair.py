from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree
from functools import partial

from pcs.lib.cib.tools import create_subelement_id
from pcs.lib.xml_tools import get_sub_element

def _append_new_nvpair(nvset_element, name, value):
    """
    Create nvpair with name and value as subelement of nvset_element.

    etree.Element nvset_element is context of new nvpair
    string name is name attribute of new nvpair
    string value is value attribute of new nvpair
    """
    etree.SubElement(
        nvset_element,
        "nvpair",
        id=create_subelement_id(nvset_element, name),
        name=name,
        value=value
    )

def set_nvpair_in_nvset(nvset_element, name, value):
    """
    Update nvpair, create new if it doesn't yet exist or remove existing
    nvpair if value is empty.

    nvset_element -- element in which nvpair should be added/updated/removed
    name -- name of nvpair
    value -- value of nvpair
    """
    nvpair = nvset_element.find("./nvpair[@name='{0}']".format(name))
    if nvpair is None:
        if value:
            _append_new_nvpair(nvset_element, name, value)
    else:
        if value:
            nvpair.set("value", value)
        else:
            nvset_element.remove(nvpair)

def arrange_first_nvset(tag_name, context_element, nvpair_dict):
    """
    Put nvpairs to the first tag_name nvset in the context_element.

    If the nvset does not exist, it will be created.

    WARNING: does not solve multiple nvsets (with the same tag_name) in the
    context_element! Consider carefully if this is your use case. Probably not.
    There could be more than one nvset.
    This function is DEPRECATED. Try to use update_nvset etc.

    string tag_name -- tag name of nvset element
    etree context_element -- parent element of nvset
    dict nvpair_dict -- dictionary of nvpairs
    """
    if not nvpair_dict:
        return

    nvset_element = get_sub_element(
        context_element,
        tag_name,
        create_subelement_id(context_element, tag_name),
        new_index=0
    )

    update_nvset(nvset_element, nvpair_dict)

def append_new_nvset(tag_name, context_element, nvpair_dict):
    """
    Append new nvset_element comprising nvpairs children (corresponding
    nvpair_dict) to the context_element

    string tag_name should be "instance_attributes" or "meta_attributes"
    etree.Element context_element is element where new nvset will be appended
    dict nvpair_dict contains source for nvpair children
    """
    nvset_element = etree.SubElement(context_element, tag_name, {
        "id": create_subelement_id(context_element, tag_name)
    })
    for name, value in sorted(nvpair_dict.items()):
        _append_new_nvpair(nvset_element, name, value)

append_new_instance_attributes = partial(
    append_new_nvset,
    "instance_attributes"
)

append_new_meta_attributes = partial(
    append_new_nvset,
    "meta_attributes"
)

def update_nvset(nvset_element, nvpair_dict):
    """
    Add, remove or update nvpairs according to nvpair_dict into nvset_element

    If the resulting nvset is empty, it will be removed.

    etree nvset_element -- container where nvpairs are set
    dict nvpair_dict -- contains source for nvpair children
    """
    for name, value in sorted(nvpair_dict.items()):
        set_nvpair_in_nvset(nvset_element, name, value)
    # remove an empty nvset
    if not list(nvset_element):
        nvset_element.getparent().remove(nvset_element)

def get_nvset(nvset):
    """
    Returns nvset element as list of nvpairs with format:
    [
        {
            "id": <id of nvpair>,
            "name": <name of nvpair>,
            "value": <value of nvpair>
        },
        ...
    ]

    nvset -- nvset element
    """
    nvpair_list = []
    for nvpair in nvset.findall("./nvpair"):
        nvpair_list.append({
            "id": nvpair.get("id"),
            "name": nvpair.get("name"),
            "value": nvpair.get("value", "")
        })
    return nvpair_list
