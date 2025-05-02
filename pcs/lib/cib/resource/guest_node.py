from typing import (
    Mapping,
    cast,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports.item import (
    ReportItem,
    ReportItemList,
)
from pcs.common.types import StringCollection
from pcs.lib import validate
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.cib.nvpair import (
    arrange_first_meta_attributes,
    get_meta_attribute_value,
    has_meta_attribute,
)
from pcs.lib.cib.tools import does_id_exist

OPTION_REMOTE_NODE = "remote-node"
_OPTION_REMOTE_ADDR = "remote-addr"
_OPTION_REMOTE_PORT = "remote-port"
_OPTION_REMOTE_CONN_TIMEOUT = "remote-connect-timeout"


# TODO pcs currently does not care about multiple meta_attributes and here
# we don't care as well
GUEST_OPTIONS = [
    _OPTION_REMOTE_ADDR,
    _OPTION_REMOTE_PORT,
    _OPTION_REMOTE_CONN_TIMEOUT,
]


def validate_updating_guest_attributes(
    cib: _Element,
    existing_nodes_names: list[str],
    existing_nodes_addrs: list[str],
    new_meta_attrs: Mapping[str, str],
    existing_meta_attrs: Mapping[str, str],
    force_flags: reports.types.ForceFlags,
) -> ReportItemList:
    """
    Guest nodes have an implicit connection resource created by Pacemaker with
    attributes remote-node and remode-addr that defaults to remote-node.
    Updating these attributes doesn't make sense because Pacemaker Remote also
    needs authkey, so changing the address to another host will not work as
    expected. However it can still be forced (in case of a networking change)
    and additional check for IDs in CIB is performed.

    TODO: needs to be consolidated with checks in resource create during its
        overhaul

    existing_nodes_names -- list of existing guest and remote node names to
        check for name conflicts
    existing_nodes_addrs -- list of existing guest and remote node addresses to
        check for name conflicts, since address is used if name is not defined
    new_meta_attrs -- meta attributes that are being updated with their new
        values
    existing_meta_attrs -- currently defined meta attributes with their values
    force_flags -- force flags
    """

    validator_list = [
        validate.ValueTimeInterval(_OPTION_REMOTE_CONN_TIMEOUT),
        validate.ValuePortNumber(_OPTION_REMOTE_PORT),
    ]
    for validator in validator_list:
        validator.empty_string_valid = True
    report_list = validate.ValidatorAll(validator_list).validate(new_meta_attrs)

    # Validate remote-node collision with other CIB IDs
    report_list.extend(
        validate_conflicts(
            cib,
            existing_nodes_names,
            existing_nodes_addrs,
            new_meta_attrs.get(OPTION_REMOTE_NODE, ""),
            new_meta_attrs,
        )
    )

    # Validating previously undefined meta attributes
    new_meta_attrs_set = set(new_meta_attrs.keys())
    existing_meta_attrs_set = set(existing_meta_attrs.keys())

    # Only addition of remote-node constitutes creating of a guest node, just
    # adding remote-addr when remote-node is not defined is fine
    added_guest_conn_keys = set(new_meta_attrs_set - existing_meta_attrs_set)
    if OPTION_REMOTE_NODE in added_guest_conn_keys:
        # Suggesting remove is not needed, this is only triggered when the
        # attributes weren't defined previously
        report_list.append(
            ReportItem(
                severity=reports.item.get_severity_from_flags(
                    reports.codes.FORCE,
                    force_flags,
                ),
                message=reports.messages.UseCommandNodeAddGuest(),
            )
        )
        # Never return reports with contradictory guidance
        return report_list

    # Validating previously defined meta attributes
    updated_guest_conn_keys = existing_meta_attrs_set.intersection(
        new_meta_attrs_set
    ).intersection(
        # These keys are crucial for defining the connection to the guest node
        # and should only be changed by recreating the guest node in most cases
        {OPTION_REMOTE_NODE, _OPTION_REMOTE_ADDR}
    )
    if any(
        new_meta_attrs[key] != existing_meta_attrs[key]
        for key in updated_guest_conn_keys
    ):
        # If all new values are empty, this is a delete operation
        if not all(new_meta_attrs[key] for key in updated_guest_conn_keys):
            report_list.append(
                ReportItem(
                    severity=reports.item.get_severity_from_flags(
                        reports.codes.FORCE,
                        force_flags,
                    ),
                    message=reports.messages.UseCommandNodeRemoveGuest(),
                )
            )
        elif OPTION_REMOTE_NODE in existing_meta_attrs:
            # Otherwise, this is an update, suggest readding resource but only
            # if remote-node is defined - if it isn't, it's not a dangerous
            # operation
            report_list.append(
                ReportItem(
                    severity=reports.item.get_severity_from_flags(
                        reports.codes.FORCE,
                        force_flags,
                    ),
                    message=reports.messages.UseCommandRemoveAndAddGuestNode(),
                )
            )

    # Special case - when remote-node is set up without node-addr, it is used as
    # an address, so adding remote-addr counts as an address change too
    if (
        _OPTION_REMOTE_ADDR not in existing_meta_attrs
        and OPTION_REMOTE_NODE in existing_meta_attrs
        and existing_meta_attrs[OPTION_REMOTE_NODE]
        and _OPTION_REMOTE_ADDR in new_meta_attrs
        and new_meta_attrs[_OPTION_REMOTE_ADDR]
    ):
        report_list.append(
            ReportItem(
                severity=reports.item.get_severity_from_flags(
                    reports.codes.FORCE,
                    force_flags,
                ),
                message=reports.messages.UseCommandRemoveAndAddGuestNode(),
            )
        )

    return report_list


def validate_conflicts(
    tree: _Element,
    existing_nodes_names: StringCollection,
    existing_nodes_addrs: StringCollection,
    node_name: str,
    options: Mapping[str, str],
) -> reports.ReportItemList:
    report_list = []
    if (
        does_id_exist(tree, node_name)
        or node_name in existing_nodes_names
        or (
            _OPTION_REMOTE_ADDR not in options
            and node_name in existing_nodes_addrs
        )
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.GuestNodeNameAlreadyExists(node_name)
            )
        )

    if (
        _OPTION_REMOTE_ADDR in options
        and options[_OPTION_REMOTE_ADDR] in existing_nodes_addrs
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.NodeAddressesAlreadyExist(
                    [options[_OPTION_REMOTE_ADDR]]
                )
            )
        )
    return report_list


def is_node_name_in_options(options):
    return OPTION_REMOTE_NODE in options


def get_guest_option_value(options, default=None):
    """
    Commandline options: no options
    """
    return options.get(OPTION_REMOTE_NODE, default)


def validate_set_as_guest(
    tree, existing_nodes_names, existing_nodes_addrs, node_name, options
):
    validator_list = [
        validate.NamesIn(GUEST_OPTIONS, option_type="guest"),
        validate.ValueTimeInterval(_OPTION_REMOTE_CONN_TIMEOUT),
        validate.ValuePortNumber(_OPTION_REMOTE_PORT),
    ]
    return (
        validate.ValidatorAll(validator_list).validate(options)
        + validate.ValueNotEmpty("node name", None).validate(
            {"node name": node_name.strip()}
        )
        + validate_conflicts(
            tree, existing_nodes_names, existing_nodes_addrs, node_name, options
        )
    )


def is_guest_node(resource_element):
    """
    Return True if resource_element is already set as guest node.

    etree.Element resource_element is a search element
    """
    return has_meta_attribute(resource_element, OPTION_REMOTE_NODE)


def validate_is_not_guest(resource_element):
    """
    etree.Element resource_element
    """
    if not is_guest_node(resource_element):
        return []

    return [
        ReportItem.error(
            reports.messages.ResourceIsGuestNodeAlready(
                resource_element.attrib["id"]
            )
        )
    ]


def set_as_guest(
    resource_element,
    id_provider,
    node,
    addr=None,
    port=None,
    connect_timeout=None,
):
    """
    Set resource as guest node.

    etree.Element resource_element

    """
    meta_options = {OPTION_REMOTE_NODE: str(node)}
    if addr:
        meta_options[_OPTION_REMOTE_ADDR] = str(addr)
    if port:
        meta_options[_OPTION_REMOTE_PORT] = str(port)
    if connect_timeout:
        meta_options[_OPTION_REMOTE_CONN_TIMEOUT] = str(connect_timeout)

    arrange_first_meta_attributes(resource_element, meta_options, id_provider)


def unset_guest(resource_element):
    """
    Unset resource as guest node.

    etree.Element resource_element
    """
    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    guest_nvpair_list = resource_element.xpath(
        "./meta_attributes/nvpair[{0}]".format(
            " or ".join(
                [
                    f'@name="{option}"'
                    for option in (GUEST_OPTIONS + [OPTION_REMOTE_NODE])
                ]
            )
        )
    )
    for nvpair in guest_nvpair_list:
        meta_attributes = nvpair.getparent()
        meta_attributes.remove(nvpair)


def get_node_name_from_options(meta_options, default=None):
    """
    Return node_name from meta options.
    dict meta_options
    """
    return meta_options.get(OPTION_REMOTE_NODE, default)


def get_node_name_from_resource(resource_element):
    """
    Return the node name from a remote node resource, None for other resources

    etree.Element resource_element
    """
    return get_meta_attribute_value(resource_element, OPTION_REMOTE_NODE)


def find_node_list(tree):
    """
    Return list of guest nodes from the specified element tree

    etree.Element tree -- an element to search guest nodes in
    """
    node_list = []
    for meta_attrs in tree.xpath(
        """
            .//primitive
                /meta_attributes[
                    nvpair[
                        @name="remote-node"
                        and
                        string-length(@value) > 0
                    ]
                ]
        """
    ):
        host = None
        name = None
        for nvpair in meta_attrs:
            if nvpair.attrib.get("name", "") == _OPTION_REMOTE_ADDR:
                host = nvpair.attrib["value"]
            if nvpair.attrib.get("name", "") == OPTION_REMOTE_NODE:
                name = nvpair.attrib["value"]
                if host is None:
                    host = name
        if name:
            # The name is never empty as we only loop through elements with
            # non-empty names. It's just we loop through nvpairs instead of
            # reading the name directly.
            node_list.append(PacemakerNode(name, host))
    return node_list


def find_node_resources(
    resources_section: _Element, node_identifier: str
) -> list[_Element]:
    """
    Return list of primitive elements that are guest nodes.

    resources_section -- searched element
    node_identifier -- could be id of resource, node name or node address
    """
    return cast(
        list[_Element],
        resources_section.xpath(
            """
            .//primitive[
                (
                    @id=$node_id
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
                        @name="remote-node"
                        and
                        string-length(@value) > 0
                    ]
                    and
                    nvpair[
                        (
                            @name="remote-addr"
                            or
                            @name="remote-node"
                        )
                        and
                        @value=$node_id
                    ]
                ]
            ]
            """,
            node_id=node_identifier,
        ),
    )
