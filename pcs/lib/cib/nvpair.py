from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.tools import (
    get_sub_element,
    find_unique_id,
)


def update_nvpair(element, name, value):
    """
    Update nvpair, create new if it doesn't yet exist or remove existing
    nvpair if value is empty. Returns created/updated/removed nvpair element.

    element -- element in which nvpair should be added/updated/removed
    name -- name of nvpair
    value -- value of nvpair
    """
    nvpair = element.find("./nvpair[@name='{0}']".format(name))
    if nvpair is None:
        if not value:
            return None
        nvpair_id = find_unique_id(
            element, "{0}-{1}".format(element.get("id"), name)
        )
        nvpair = etree.SubElement(
            element, "nvpair", id=nvpair_id, name=name, value=value
        )
    else:
        if value:
            nvpair.set("value", value)
        else:
            # remove nvpair if value is empty
            element.remove(nvpair)
    return nvpair


def update_nvset(tag_name, element, attribute_dict):
    """
    This method updates nvset specified by tag_name. If specified nvset
    doesn't exist it will be created. Returns updated nvset element or None if
    attribute_dict is empty.

    tag_name -- tag name of nvset element
    element -- parent element of nvset
    attribute_dict -- dictionary of nvpairs
    """
    if not attribute_dict:
        return None

    attributes = get_sub_element(element, tag_name, find_unique_id(
        element, "{0}-{1}".format(element.get("id"), tag_name)
    ), 0)

    for name, value in sorted(attribute_dict.items()):
        update_nvpair(attributes, name, value)

    return attributes


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
