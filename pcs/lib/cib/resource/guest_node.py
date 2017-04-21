from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports, validate
from pcs.lib.cib.resource.common import(
    has_meta_attribute,
    arrange_first_meta_attributes,
)
from pcs.lib.node import NodeAddresses

def validate_options(options):
    report_list = validate.names_in(
        [
            'remote-node',
            'remote-port',
            'remote-addr',
            'remote-connect-timeout',
        ],
        options.keys(),
        "guest options",
    )

    validator_list = [
        validate.is_required("remote-node"),
        validate.is_time_interval("remote-connect-timeout")
    ]

    report_list.extend(validate.run_collection_of_option_validators(
        options,
        validator_list
    ))

    return report_list

def is_guest_node(resource_element):
    """
    Return True if resource_element is already set as guest node.

    etree.Element resource_element is a researched element
    """
    return has_meta_attribute(resource_element, "remote-node")

def validate_is_not_guest(resource_element):
    """
    etree.Element resource_element
    """
    if not is_guest_node(resource_element):
        return []

    return [
        reports.resource_is_guest_node_already(
            resource_element.attrib["id"]
        )
    ]

def set_as_guest(resource_element, meta_options):
    """
    Set resource as guest node.

    etree.Element resource_element
    dict meta_options
    """
    arrange_first_meta_attributes(resource_element, meta_options)

def get_node(meta_attributes):
    """
    Return NodeAddresses with corresponding to guest node in meta_attributes.
    Return None if meta_attributes does not mean guest node

    etree.Element meta_attributes is a researched element
    """
    host = None
    name = None
    for nvpair in meta_attributes:
        if nvpair.attrib.get("name", "") == "remote-addr":
            host = nvpair.attrib["value"]
        if nvpair.attrib.get("name", "") == "remote-node":
            name = nvpair.attrib["value"]
            if host is None:
                host = name
    return NodeAddresses(host, name=name) if name else None

def get_host_from_options(meta_options):
    return meta_options.get(
        "remote-addr",
        meta_options.get("remote-node", None)
    )

def find_node_list(resources_section):
    """
    Return list of nodes from resources_section

    etree.Element resources_section is a researched element
    """
    #TODO pcs currently does not care about multiple meta_attributes and here
    #we don't care as well
    return [
        get_node(meta_attrs) for meta_attrs in resources_section.xpath("""
            .//primitive
                /meta_attributes[
                    nvpair[
                        @name="remote-node"
                        and
                        string-length(@value) > 0
                    ]
                ]
        """)
    ]
