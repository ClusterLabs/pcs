from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports, validate
from pcs.lib.cib.tools import does_id_exist
from pcs.lib.cib.resource.common import(
    has_meta_attribute,
    arrange_first_meta_attributes,
    get_meta_attribute_value,
)
from pcs.lib.node import NodeAddresses
from pcs.lib.node import (
    node_addresses_contain_host,
    node_addresses_contain_name,
)


#TODO pcs currently does not care about multiple meta_attributes and here
#we don't care as well

GUEST_OPTIONS = [
    'remote-node',
    'remote-port',
    'remote-addr',
    'remote-connect-timeout',
]

def validate_host_conflicts(tree, nodes, options):
    host = options.get("remote-addr", options.get("remote-node", None))
    if(
        does_id_exist(tree, options.get("remote-node", None))
        or (
            host
            and
            node_addresses_contain_host(nodes, host)
        )
    ):
        return [reports.id_already_exists(host)]
    return []

def contains_guest_options(options):
    return "remote-node" in options

def get_guest_option_value(options, default=None):
    return options.get("remote-node", default)


def validate_parts(tree, nodes, node_name, options):
    report_list = validate.names_in(
        GUEST_OPTIONS,
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

    report_list.extend(validate_host_conflicts(tree, nodes, options))

    if node_addresses_contain_name(nodes, node_name):
        report_list.append(reports.id_already_exists(node_name))

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

def unset_guest(resource_element):
    """
    Unset resource as guest node.

    etree.Element resource_element
    """
    guest_nvpair_list = resource_element.xpath(
        "./meta_attributes/nvpair[{0}]".format(
            " or ".join([
                '@name="{0}"'.format(option)
                for option in GUEST_OPTIONS
            ])
        )
    )
    for nvpair in guest_nvpair_list:
        meta_attributes = nvpair.getparent()
        meta_attributes.remove(nvpair)
        if not len(meta_attributes):
            meta_attributes.getparent().remove(meta_attributes)

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
    """
    Return host from meta options. Return None as a default value.
    """
    return meta_options.get(
        "remote-addr",
        meta_options.get("remote-node", None)
    )

def get_host(resource_element):
    host = get_meta_attribute_value(resource_element, "remote-addr")
    if host:
        return host

    return get_meta_attribute_value(resource_element, "remote-node")

def find_node_list(resources_section):
    """
    Return list of nodes from resources_section

    etree.Element resources_section is a researched element
    """
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

def find_node_resources(resources_section, node_identifier):
    """
    Return list of etree.Eleent primitives that are guest nodes.

    etree.Element resources_section is a researched element
    string node_identifier could be id of resource, node name or node address
    """
    resources = resources_section.xpath("""
        .//primitive[
            (
                @id="{0}"
                and
                meta_attributes[
                    nvpair[
                        @name="remote-node"
                        and
                        string-length(@value) > 0
                    ]
                ]
            )
            or
            meta_attributes[
                nvpair[
                    (
                        @name="remote-addr"
                        or
                        @name="remote-node"
                    )
                    and
                    @value="{0}"
                ]
            ]
        ]
    """.format(node_identifier))
    return resources
