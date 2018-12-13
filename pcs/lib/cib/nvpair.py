from functools import partial
from lxml import etree

from pcs.lib.cib.tools import create_subelement_id
from pcs.lib.xml_tools import (
    get_sub_element,
    append_when_useful
)

def _append_new_nvpair(nvset_element, name, value, id_provider):
    """
    Create nvpair with name and value as subelement of nvset_element.

    etree.Element nvset_element is context of new nvpair
    string name is name attribute of new nvpair
    string value is value attribute of new nvpair
    IdProvider id_provider -- elements' ids generator
    """
    etree.SubElement(
        nvset_element,
        "nvpair",
        id=create_subelement_id(nvset_element, name, id_provider),
        name=name,
        value=value
    )

def set_nvpair_in_nvset(nvset_element, name, value, id_provider):
    """
    Update nvpair, create new if it doesn't yet exist or remove existing
    nvpair if value is empty.

    nvset_element -- element in which nvpair should be added/updated/removed
    name -- name of nvpair
    value -- value of nvpair
    IdProvider id_provider -- elements' ids generator
    """
    nvpair = nvset_element.find("./nvpair[@name='{0}']".format(name))
    if nvpair is None:
        if value:
            _append_new_nvpair(nvset_element, name, value, id_provider)
    else:
        if value:
            nvpair.set("value", value)
        else:
            nvset_element.remove(nvpair)

def arrange_first_nvset(
    tag_name, context_element, nvpair_dict, id_provider, new_id=None
):
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
    IdProvider id_provider -- elements' ids generator
    """
    if not nvpair_dict:
        return

    nvset_element = get_sub_element(
        context_element,
        tag_name,
        new_id=(new_id if new_id else create_subelement_id(
            context_element, tag_name, id_provider
        )),
        append_if_missing=False
    )
    update_nvset(nvset_element, nvpair_dict, id_provider)
    append_when_useful(context_element, nvset_element, index=0)

def append_new_nvset(tag_name, context_element, nvpair_dict, id_provider):
    """
    Append new nvset_element comprising nvpairs children (corresponding
    nvpair_dict) to the context_element

    string tag_name should be "instance_attributes" or "meta_attributes"
    etree.Element context_element is element where new nvset will be appended
    dict nvpair_dict contains source for nvpair children
    IdProvider id_provider -- elements' ids generator
    """
    nvset_element = etree.Element(
        tag_name,
        {
            "id": create_subelement_id(context_element, tag_name, id_provider)
        }
    )
    for name, value in sorted(nvpair_dict.items()):
        _append_new_nvpair(nvset_element, name, value, id_provider)
    append_when_useful(context_element, nvset_element)

append_new_instance_attributes = partial(
    append_new_nvset,
    "instance_attributes"
)

append_new_meta_attributes = partial(
    append_new_nvset,
    "meta_attributes"
)

def update_nvset(nvset_element, nvpair_dict, id_provider):
    """
    Add, remove or update nvpairs according to nvpair_dict into nvset_element

    etree nvset_element -- a container where nvpairs are set
    dict nvpair_dict -- names and values for nvpairs
    IdProvider id_provider -- elements' ids generator
    """
    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    for name, value in sorted(nvpair_dict.items()):
        set_nvpair_in_nvset(nvset_element, name, value, id_provider)

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

def get_value(tag_name, context_element, name, default=None):
    """
    Return value from nvpair.

    WARNING: does not solve multiple nvsets (with the same tag_name) in the
    context_element nor multiple nvpair with the same name

    string tag_name should be "instance_attributes" or "meta_attributes"
    etree.Element context_element is searched element
    string name specify nvpair name
    """
    value_list = context_element.xpath("""
        ./{0}
        /nvpair[
            @name="{1}"
            and
            string-length(@value) > 0
        ]
        /@value
    """.format(tag_name, name))
    return value_list[0] if value_list else default

def get_nvset_as_dict(tag_name, context_element):
    """
    Returns nvset with specified tag_name in context_element as dictionary

    tag_name string -- tag of nvset element which values shold be returned
    context_element etree.Element -- element in which required nvset is
        specified
    """
    return {
        nvpair["name"]: nvpair["value"]
        for nvpair in get_nvset(
            get_sub_element(context_element, tag_name, append_if_missing=False)
        )
    }

def has_meta_attribute(resource_el, name):
    """
    Return if the element contains meta attribute 'name'

    etree.Element resource_el is researched element
    string name specifies attribute
    """
    return len(resource_el.xpath(
        './meta_attributes/nvpair[@name="{0}"]'.format(name)
    )) > 0

arrange_first_meta_attributes = partial(
    arrange_first_nvset,
    "meta_attributes"
)

arrange_first_instance_attributes = partial(
    arrange_first_nvset,
    "instance_attributes"
)

get_meta_attribute_value = partial(get_value, "meta_attributes")
