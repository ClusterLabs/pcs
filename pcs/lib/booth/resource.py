from typing import (
    Iterable,
    cast,
)

from lxml.etree import _Element

from pcs.lib.cib.tools import find_unique_id


def create_resource_id(resources_section, name, suffix):
    return find_unique_id(
        resources_section.getroottree(), f"booth-{name}-{suffix}"
    )


def is_ip_resource(resource_element):
    return resource_element.attrib.get("type", "") == "IPaddr2"


def find_grouped_ip_element_to_remove(booth_element):
    group = booth_element.getparent()

    if group.tag != "group":
        return None

    primitives = group.xpath("./primitive")
    if len(primitives) != 2:
        # Don't remove the IP resource if some other resources are in the group.
        # It is most likely manually configured by the user so we cannot delete
        # it automatically.
        return None
    for element in primitives:
        if is_ip_resource(element):
            return element
    return None


def find_elements_to_remove(
    booth_element_list: Iterable[_Element],
) -> list[_Element]:
    elements_to_remove = []
    for element in booth_element_list:
        ip_resource_to_remove = find_grouped_ip_element_to_remove(element)
        if ip_resource_to_remove is not None:
            elements_to_remove.append(ip_resource_to_remove)
        elements_to_remove.append(element)

    return elements_to_remove


def find_for_config(
    resources_section: _Element, booth_config_file_path: str
) -> list[_Element]:
    return cast(
        list[_Element],
        resources_section.xpath(
            """
            .//primitive[
                @type="booth-site"
                and
                instance_attributes[
                    nvpair[@name="config" and @value=$booth_name]
                ]
            ]
            """,
            booth_name=booth_config_file_path,
        ),
    )


def find_bound_ip(
    resources_section: _Element, booth_config_file_path: str
) -> list[str]:
    return cast(
        list[str],
        resources_section.xpath(
            """
            .//group[
                primitive[
                    @type="booth-site"
                    and
                    instance_attributes[
                        nvpair[@name="config" and @value=$booth_name]
                    ]
                ]
            ]
            /primitive[@type="IPaddr2"]
            /instance_attributes
            /nvpair[@name="ip"]
            /@value
            """,
            booth_name=booth_config_file_path,
        ),
    )
