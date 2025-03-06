from functools import partial
from typing import (
    List,
    Optional,
    cast,
    overload,
)

from lxml import etree
from lxml.etree import _Element

from pcs.lib.cib.tools import create_subelement_id
from pcs.lib.xml_tools import (
    append_when_useful,
    get_sub_element,
)

META_ATTRIBUTES_TAG = "meta_attributes"
INSTANCE_ATTRIBUTES_TAG = "instance_attributes"


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
        value=value,
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
    nvpair_list = nvset_element.xpath("./nvpair[@name=$name]", name=name)
    if not nvpair_list:
        if value:
            _append_new_nvpair(nvset_element, name, value, id_provider)
    else:
        nvpair = nvpair_list[0]
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
        new_id=(
            new_id
            if new_id
            else create_subelement_id(context_element, tag_name, id_provider)
        ),
        append_if_missing=False,
    )
    update_nvset(nvset_element, nvpair_dict, id_provider)
    append_when_useful(context_element, nvset_element, index=0)


def append_new_nvset(
    tag_name, context_element, nvpair_dict, id_provider, enforce_append=False
):
    """
    Append new nvset_element comprising nvpairs children (corresponding
    nvpair_dict) to the context_element

    string tag_name should be "instance_attributes" or "meta_attributes"
    etree.Element context_element is element where new nvset will be appended
    dict nvpair_dict contains source for nvpair children
    IdProvider id_provider -- elements' ids generator
    bool enforce_append -- append element wo usefulness check if flag is True
    """
    nvset_element = etree.Element(
        tag_name,
        {"id": create_subelement_id(context_element, tag_name, id_provider)},
    )
    for name, value in sorted(nvpair_dict.items()):
        _append_new_nvpair(nvset_element, name, value, id_provider)
    if enforce_append:
        context_element.append(nvset_element)
    else:
        append_when_useful(context_element, nvset_element)


append_new_instance_attributes = partial(
    append_new_nvset,
    INSTANCE_ATTRIBUTES_TAG,
)

append_new_meta_attributes = partial(
    append_new_nvset,
    META_ATTRIBUTES_TAG,
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


def get_nvset(nvset: _Element) -> list[dict[str, Optional[str]]]:
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
    return [
        {
            "id": nvpair.get("id"),
            "name": nvpair.get("name"),
            "value": nvpair.get("value"),
        }
        for nvpair in nvset.findall("./nvpair")
    ]


@overload
def get_value(
    tag_name: str,
    context_element: _Element,
    name: str,
    default: None = None,
) -> Optional[str]:
    pass


@overload
def get_value(
    tag_name: str,
    context_element: _Element,
    name: str,
    default: str,
) -> str:
    pass


def get_value(
    tag_name: str,
    context_element: _Element,
    name: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Return a value from an nvpair

    WARNING: does not solve multiple nvsets (with the same tag_name) in the
    context_element nor multiple nvpair with the same name

    tag_name -- "instance_attributes" or "meta_attributes"
    context_element -- searched element
    name -- nvpair name
    default -- default return value
    """
    value_list = context_element.xpath(
        """
            ./*[local-name()=$tag_name]
            /nvpair[
                @name=$name and string-length(@value) > 0
            ]
            /@value
        """,
        tag_name=tag_name,
        name=name,
    )
    return cast(List[str], value_list)[0] if value_list else default


def get_nvset_as_dict(tag_name, context_element):
    """
    Returns nvset with specified tag_name in context_element as dictionary

    tag_name string -- tag of nvset element which values should be returned
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
    return (
        len(
            resource_el.xpath(
                """
                    ./*[local-name()=$tag_name]
                    /nvpair[
                        @name=$name and string-length(@value) > 0
                    ]
                    /@value
                """,
                tag_name=META_ATTRIBUTES_TAG,
                name=name,
            )
        )
        > 0
    )


arrange_first_meta_attributes = partial(
    arrange_first_nvset,
    META_ATTRIBUTES_TAG,
)

arrange_first_instance_attributes = partial(
    arrange_first_nvset,
    INSTANCE_ATTRIBUTES_TAG,
)

get_meta_attribute_value = partial(get_value, META_ATTRIBUTES_TAG)
