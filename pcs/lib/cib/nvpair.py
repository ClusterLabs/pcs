from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.tools import (
    get_sub_element,
    create_subelement_id,
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
            etree.SubElement(
                nvset_element,
                "nvpair",
                id=create_subelement_id(nvset_element, name),
                name=name,
                value=value
            )
    else:
        if value:
            nvpair.set("value", value)
        else:
            nvset_element.remove(nvpair)

def arrange_first_nvset(tag_name, context_element, attribute_dict):
    """
    Arrange to context_element contains some nvset (with tag_name) with nvpairs
    corresponing to attribute_dict.

    WARNING: does not solve multiple nvset (with tag_name) under
    context_element! Consider carefully if this is your case. Probably not.
    There could be more than one nvset.
    This function is DEPRECATED. Try to use update_nvset etc.

    This method updates nvset specified by tag_name. If specified nvset
    doesn't exist it will be created. Returns updated nvset element or None if
    attribute_dict is empty.

    tag_name -- tag name of nvset element
    context_element -- parent element of nvset
    attribute_dict -- dictionary of nvpairs
    """
    if not attribute_dict:
        return

    nvset_element = get_sub_element(
        context_element,
        tag_name,
        create_subelement_id(context_element, tag_name),
        new_index=0
    )

    update_nvset(nvset_element, attribute_dict)

def update_nvset(nvset_element, attribute_dict):
    for name, value in sorted(attribute_dict.items()):
        set_nvpair_in_nvset(nvset_element, name, value)

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
