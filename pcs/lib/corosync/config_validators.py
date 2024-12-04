# pylint: disable=too-many-lines
from collections import (
    Counter,
    defaultdict,
)
from dataclasses import dataclass
from itertools import zip_longest
from typing import (
    Any,
    Callable,
    Collection,
    Iterable,
    Mapping,
    MutableSequence,
    MutableSet,
    Optional,
    Sequence,
)

from pcs.common import reports
from pcs.common.corosync_conf import CorosyncNodeAddressType
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportItemSeverity,
    get_severity,
)
from pcs.common.types import StringCollection
from pcs.lib import validate
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.corosync import constants
from pcs.lib.corosync.node import (
    CorosyncNode,
    get_address_type,
)

_QDEVICE_NET_REQUIRED_OPTIONS = (
    "algorithm",
    "host",
)
_QDEVICE_NET_OPTIONAL_OPTIONS = (
    "connect_timeout",
    "force_ip_version",
    "keep_active_partition_tie_breaker",
    "port",
    "tie_breaker",
    "tls",
)


@dataclass(frozen=True, order=True)
class _LinkAddrType:
    link: str
    addr_type: CorosyncNodeAddressType


class _ClusterNameGfs2Validator(validate.ValueValidator):
    def __init__(
        self,
        option_name: str,
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        option_name -- name of the option to check
        option_name_for_report -- optional option_name override
        severity -- severity of produced reports, defaults to error
        """
        super().__init__(
            option_name, option_name_for_report=option_name_for_report
        )
        self._severity = (
            ReportItemSeverity.error() if severity is None else severity
        )

    def _validate_value(self, value: validate.ValuePair) -> ReportItemList:
        if not isinstance(value.normalized, str):
            return []
        if not validate.matches_regexp(
            value.normalized, r"^[a-zA-Z0-9_-]{0,32}$"
        ):
            return [
                ReportItem(
                    self._severity,
                    reports.messages.CorosyncClusterNameInvalidForGfs2(
                        cluster_name=value.original,
                        max_length=32,
                        allowed_characters="a-z A-Z 0-9 _-",
                    ),
                )
            ]
        return []


def create(
    cluster_name: str,
    # TODO change to DTO, needs new validator
    node_list: Iterable[Mapping[str, Any]],
    transport: str,
    ip_version: str,
    force_unresolvable: bool = False,
    force_cluster_name: bool = False,
) -> ReportItemList:
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Validate creating a new minimalistic corosync.conf

    cluster_name -- the name of the new cluster
    node_list -- nodes of the new cluster; dict: name, addrs
    transport -- corosync transport used in the new cluster
    ip_version -- which IP family node addresses should be
    force_unresolvable -- if True, report unresolvable addresses as warnings
        instead of errors
    force_cluster_name -- if True, report forcible cluster name issues as
        warnings instead of errors
    """
    # cluster name and transport validation
    validators = [
        validate.ValueNotEmpty(
            "name", None, option_name_for_report="cluster name"
        ),
        _ClusterNameGfs2Validator(
            "name",
            option_name_for_report="cluster name",
            severity=reports.item.get_severity(
                reports.codes.FORCE, force_cluster_name
            ),
        ),
        validate.ValueCorosyncValue(
            "name", option_name_for_report="cluster name"
        ),
        validate.ValueIn("transport", constants.TRANSPORTS_ALL),
        validate.ValueCorosyncValue("transport"),
    ]
    report_items = validate.ValidatorAll(validators).validate(
        {"name": cluster_name, "transport": transport}
    )

    # nodelist validation
    get_addr_type = _addr_type_analyzer()
    all_names_usable = True  # can names be used to identifying nodes?
    all_names_count: dict[str, int] = defaultdict(int)
    all_addrs_count: dict[str, int] = defaultdict(int)
    addr_types_per_node: list[list[CorosyncNodeAddressType]] = []
    unresolvable_addresses: set[str] = set()
    nodes_with_empty_addr: set[str] = set()
    # First, validate each node on its own. Also extract some info which will
    # be needed when validating the nodelist and inter-node dependencies.
    for i, node in enumerate(node_list, 1):
        report_items.extend(
            validate.ValidatorAll(_get_node_name_validators(i)).validate(node)
        )
        if "name" in node and node["name"]:
            # Count occurrences of each node name. Do not bother counting
            # missing or empty names. They must be fixed anyway.
            all_names_count[node["name"]] += 1
        else:
            all_names_usable = False
        # Cannot use node.get("addrs", []) - if node["addrs"] == None then
        # the get returns None and len(None) raises an exception.
        addr_count = len(node.get("addrs") or [])
        if transport in constants.TRANSPORTS_KNET + constants.TRANSPORTS_UDP:
            if transport in constants.TRANSPORTS_KNET:
                min_addr_count = constants.LINKS_KNET_MIN
                max_addr_count = constants.LINKS_KNET_MAX
            else:
                min_addr_count = constants.LINKS_UDP_MIN
                max_addr_count = constants.LINKS_UDP_MAX
            if addr_count < min_addr_count or addr_count > max_addr_count:
                report_items.append(
                    ReportItem.error(
                        reports.messages.CorosyncBadNodeAddressesCount(
                            actual_count=addr_count,
                            min_count=min_addr_count,
                            max_count=max_addr_count,
                            node_name=node.get("name"),
                            node_index=i,
                        )
                    )
                )
        addr_types: list[CorosyncNodeAddressType] = []
        # Cannot use node.get("addrs", []) - if node["addrs"] == None then
        # the get returns None and len(None) raises an exception.
        for link_index, addr in enumerate(node.get("addrs") or []):
            if addr == "":
                if node.get("name"):
                    # No way to report name if none is set. Unnamed nodes cause
                    # errors anyway.
                    nodes_with_empty_addr.add(node["name"])
                continue
            all_addrs_count[addr] += 1
            _validate_addr_type(
                addr,
                str(link_index),
                ip_version,
                get_addr_type,
                # these will get populated in the function
                addr_types,
                unresolvable_addresses,
                report_items,
            )
        addr_types_per_node.append(addr_types)
    # Report all empty and unresolvable addresses at once instead on each own.
    if nodes_with_empty_addr:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesCannotBeEmpty(
                    sorted(nodes_with_empty_addr),
                )
            )
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )

    # Reporting single-node errors finished.
    # Now report nodelist and inter-node errors.
    if not node_list:
        report_items.append(
            ReportItem.error(reports.messages.CorosyncNodesMissing())
        )
    non_unique_names = {
        name for name, count in all_names_count.items() if count > 1
    }
    if non_unique_names:
        all_names_usable = False
        report_items.append(
            ReportItem.error(
                reports.messages.NodeNamesDuplication(sorted(non_unique_names))
            )
        )
    non_unique_addrs = {
        addr
        for addr, count in all_addrs_count.items()
        # empty strings are not valid addresses and they are reported
        # from a different piece of code in a different report
        if count > 1 and addr != ""
    }
    if non_unique_addrs:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesDuplication(
                    sorted(non_unique_addrs),
                )
            )
        )
    if all_names_usable:
        # Check for errors using node names in their reports. If node names are
        # ambiguous then such issues cannot be comprehensibly reported so the
        # checks are skipped.
        node_addr_count = {}
        for node in node_list:
            # Cannot use node.get("addrs", []) - if node["addrs"] == None then
            # the get returns None and len(None) raises an exception.
            node_addr_count[node["name"]] = len(node.get("addrs") or [])
        # Check if all nodes have the same number of addresses. No need to
        # check that if udp or udpu transport is used as they can only use one
        # address and that has already been checked above.
        if (
            transport not in constants.TRANSPORTS_UDP
            and len(Counter(node_addr_count.values()).keys()) > 1
        ):
            report_items.append(
                ReportItem.error(
                    reports.messages.CorosyncNodeAddressCountMismatch(
                        node_addr_count,
                    )
                )
            )
    # Check mixing IPv4 and IPv6 in one link, node names are not relevant
    links_ip_mismatch = []
    for link, link_addr_types in enumerate(zip_longest(*addr_types_per_node)):
        if _mixes_ipv4_ipv6(link_addr_types):
            links_ip_mismatch.append(str(link))
    if links_ip_mismatch:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncIpVersionMismatchInLinks(
                    links_ip_mismatch,
                )
            )
        )

    return report_items


def _get_node_name_validators(
    node_index: int,
) -> list[validate.ValidatorInterface]:
    _type = f"node {node_index}"
    _name = f"node {node_index} name"
    return [
        validate.NamesIn(["addrs", "name"], option_type="node"),
        validate.IsRequiredAll(["name"], option_type=_type),
        validate.ValueNotEmpty("name", None, option_name_for_report=_name),
        validate.ValueCorosyncValue("name", option_name_for_report=_name),
    ]


def _addr_type_analyzer() -> Callable[[str], CorosyncNodeAddressType]:
    cache = {}

    def analyzer(addr: str) -> CorosyncNodeAddressType:
        if addr not in cache:
            cache[addr] = get_address_type(addr, resolve=True)
        return cache[addr]

    return analyzer


def _extract_existing_addrs_and_names(
    coro_existing_nodes: Iterable[CorosyncNode],
    pcmk_existing_nodes: Iterable[PacemakerNode],
    pcmk_names: bool = True,
) -> tuple[set[str], dict[str, CorosyncNodeAddressType], set[str]]:
    existing_names = set()
    existing_addrs = set()
    existing_addr_types_dict = {}
    for coro_node in coro_existing_nodes:
        if coro_node.name:
            existing_names.add(coro_node.name)
        existing_addrs.update(set(coro_node.addrs_plain()))
        for addr in coro_node.addrs:
            # If two nodes have FQDN and one has IPv4, we want to keep the IPv4
            if (
                addr.type
                not in (
                    CorosyncNodeAddressType.FQDN,
                    CorosyncNodeAddressType.UNRESOLVABLE,
                )
                or addr.link not in existing_addr_types_dict
            ):
                existing_addr_types_dict[addr.link] = addr.type
    for pcmk_node in pcmk_existing_nodes:
        if pcmk_names:
            existing_names.add(pcmk_node.name)
        existing_addrs.add(pcmk_node.addr)
    return existing_addrs, existing_addr_types_dict, existing_names


def _validate_addr_type(
    addr: str,
    link_index: Optional[str],
    ip_version: str,
    get_addr_type: Callable[[str], CorosyncNodeAddressType],
    # these will get populated in the function
    addr_types: MutableSequence[CorosyncNodeAddressType],
    unresolvable_addresses: MutableSet[str],
    report_items: ReportItemList,
) -> None:
    addr_types.append(get_addr_type(addr))
    if get_addr_type(addr) == CorosyncNodeAddressType.UNRESOLVABLE:
        unresolvable_addresses.add(addr)
    elif (
        get_addr_type(addr) == CorosyncNodeAddressType.IPV4
        and ip_version == constants.IP_VERSION_6
    ):
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncAddressIpVersionWrongForLink(
                    addr,
                    CorosyncNodeAddressType.IPV6.value,
                    link_number=link_index,
                )
            )
        )
    elif (
        get_addr_type(addr) == CorosyncNodeAddressType.IPV6
        and ip_version == constants.IP_VERSION_4
    ):
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncAddressIpVersionWrongForLink(
                    addr,
                    CorosyncNodeAddressType.IPV4.value,
                    link_number=link_index,
                )
            )
        )
    report_items += validate.ValueCorosyncValue(
        "addr", option_name_for_report="node address"
    ).validate({"addr": addr})


def _report_unresolvable_addresses_if_any(
    unresolvable_addresses: StringCollection, force_unresolvable: bool
) -> ReportItemList:
    if not unresolvable_addresses:
        return []
    return [
        ReportItem(
            severity=get_severity(
                reports.codes.FORCE,
                force_unresolvable,
            ),
            message=reports.messages.NodeAddressesUnresolvable(
                sorted(unresolvable_addresses),
            ),
        )
    ]


def add_nodes(
    # TODO change to DTO, needs new validator
    node_list: Iterable[Mapping[str, Any]],
    coro_existing_nodes: Iterable[CorosyncNode],
    pcmk_existing_nodes: Iterable[PacemakerNode],
    force_unresolvable: bool = False,
) -> ReportItemList:
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Validate adding nodes to a config with a nonempty nodelist

    node_list -- new nodes data; list of dict: name, addrs
    coro_existing_nodes -- existing corosync nodes
    pcmk_existing_nodes -- existing pacemaker nodes
    force_unresolvable -- if True, report unresolvable addresses as warnings
        instead of errors
    """
    # extract info from existing nodes
    (
        existing_addrs,
        existing_addr_types_dict,
        existing_names,
    ) = _extract_existing_addrs_and_names(
        coro_existing_nodes, pcmk_existing_nodes
    )
    existing_addr_types = sorted(
        [
            _LinkAddrType(link_number, addr_type)
            for link_number, addr_type in existing_addr_types_dict.items()
        ]
    )
    number_of_existing_links = len(existing_addr_types)

    # validation
    get_addr_type = _addr_type_analyzer()
    report_items = []
    new_names_count: dict[str, int] = defaultdict(int)
    new_addrs_count: dict[str, int] = defaultdict(int)
    new_addr_types_per_node: list[list[CorosyncNodeAddressType]] = []
    links_ip_mismatch_reported = set()
    unresolvable_addresses: set[str] = set()
    nodes_with_empty_addr: set[str] = set()

    # First, validate each node on its own. Also extract some info which will
    # be needed when validating the nodelist and inter-node dependencies.
    for i, node in enumerate(node_list, 1):
        report_items.extend(
            validate.ValidatorAll(_get_node_name_validators(i)).validate(node)
        )
        if "name" in node and node["name"]:
            # Count occurrences of each node name. Do not bother counting
            # missing or empty names. They must be fixed anyway.
            new_names_count[node["name"]] += 1
        # Cannot use node.get("addrs", []) - if node["addrs"] == None then
        # the get returns None and len(None) raises an exception.
        addr_count = len(node.get("addrs") or [])
        if addr_count != number_of_existing_links:
            report_items.append(
                ReportItem.error(
                    reports.messages.CorosyncBadNodeAddressesCount(
                        actual_count=addr_count,
                        min_count=number_of_existing_links,
                        max_count=number_of_existing_links,
                        node_name=node.get("name"),
                        node_index=i,
                    )
                )
            )
        addr_types: list[CorosyncNodeAddressType] = []
        # Cannot use node.get("addrs", []) - if node["addrs"] == None then
        # the get returns None and len(None) raises an exception.
        for link_index, addr in enumerate(node.get("addrs") or []):
            if addr == "":
                if node.get("name"):
                    # No way to report name if none is set. Unnamed nodes cause
                    # errors anyway.
                    nodes_with_empty_addr.add(node["name"])
                continue
            new_addrs_count[addr] += 1
            addr_types.append(get_addr_type(addr))
            if get_addr_type(addr) == CorosyncNodeAddressType.UNRESOLVABLE:
                unresolvable_addresses.add(addr)
            # Check matching IPv4 / IPv6 in existing links. FQDN matches with
            # both IPv4 and IPv6 as it can resolve to both. Unresolvable is a
            # special case of FQDN so we don't need to check it.
            if (
                link_index < number_of_existing_links
                and (
                    get_addr_type(addr)
                    not in (
                        CorosyncNodeAddressType.FQDN,
                        CorosyncNodeAddressType.UNRESOLVABLE,
                    )
                )
                and (
                    existing_addr_types[link_index].addr_type
                    != CorosyncNodeAddressType.FQDN
                )
                and (
                    get_addr_type(addr)
                    != existing_addr_types[link_index].addr_type
                )
            ):
                links_ip_mismatch_reported.add(
                    existing_addr_types[link_index].link
                )
                report_items.append(
                    ReportItem.error(
                        reports.messages.CorosyncAddressIpVersionWrongForLink(
                            addr,
                            existing_addr_types[link_index].addr_type.value,
                            existing_addr_types[link_index].link,
                        )
                    )
                )
            report_items += validate.ValueCorosyncValue(
                "addr", option_name_for_report="node address"
            ).validate({"addr": addr})

        new_addr_types_per_node.append(addr_types)
    # Report all empty and unresolvable addresses at once instead on each own.
    if nodes_with_empty_addr:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesCannotBeEmpty(
                    sorted(nodes_with_empty_addr),
                )
            )
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )

    # Reporting single-node errors finished.
    # Now report nodelist and inter-node errors.
    if not node_list:
        report_items.append(
            ReportItem.error(reports.messages.CorosyncNodesMissing())
        )
    # Check nodes' names and address are unique
    already_existing_names = existing_names.intersection(new_names_count.keys())
    if already_existing_names:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeNamesAlreadyExist(
                    sorted(already_existing_names),
                )
            )
        )
    already_existing_addrs = existing_addrs.intersection(new_addrs_count.keys())
    if already_existing_addrs:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesAlreadyExist(
                    sorted(already_existing_addrs),
                )
            )
        )
    non_unique_names = {
        name for name, count in new_names_count.items() if count > 1
    }
    if non_unique_names:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeNamesDuplication(sorted(non_unique_names))
            )
        )
    non_unique_addrs = {
        addr for addr, count in new_addrs_count.items() if count > 1
    }
    if non_unique_addrs:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesDuplication(
                    sorted(non_unique_addrs),
                )
            )
        )
    # Check mixing IPv4 and IPv6 in one link, node names are not relevant,
    # skip links already reported due to new nodes have wrong IP version
    existing_links = [x.link for x in existing_addr_types]
    links_ip_mismatch = []
    for link_index, link_addr_types in enumerate(
        zip_longest(*new_addr_types_per_node)
    ):
        if (
            _mixes_ipv4_ipv6(link_addr_types)
            and existing_links[link_index] not in links_ip_mismatch_reported
        ):
            links_ip_mismatch.append(existing_links[link_index])
    if links_ip_mismatch:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncIpVersionMismatchInLinks(
                    links_ip_mismatch,
                )
            )
        )
    return report_items


def remove_nodes(
    nodes_names_to_remove: StringCollection,
    existing_nodes: Iterable[CorosyncNode],
    quorum_device_model: Optional[str],
    quorum_device_settings: tuple[
        Mapping[str, str], Mapping[str, str], Mapping[str, str]
    ],
) -> ReportItemList:
    """
    Validate removing nodes

    nodes_names_to_remove -- list of names of nodes to remove
    existing_nodes -- list of all existing nodes
    quorum_device_model -- quorum device model, if quorum device used in cluster
    quorum_device_settings -- model, generic and heuristic qdevice options
    """
    existing_node_names = [node.name for node in existing_nodes]
    report_items = []
    for not_found_node in set(nodes_names_to_remove) - set(existing_node_names):
        report_items.append(
            ReportItem.error(reports.messages.NodeNotFound(not_found_node))
        )

    if not set(existing_node_names) - set(nodes_names_to_remove):
        report_items.append(
            ReportItem.error(reports.messages.CannotRemoveAllClusterNodes())
        )

    if quorum_device_model == "net":
        qdevice_model_options, _, _ = quorum_device_settings
        tie_breaker_nodeid = qdevice_model_options.get("tie_breaker")
        if tie_breaker_nodeid not in [None, "lowest", "highest"]:
            for node in existing_nodes:
                if (
                    node.name in nodes_names_to_remove
                    and
                    # "4" != 4, convert ids to string to detect a match for sure
                    str(node.nodeid) == str(tie_breaker_nodeid)
                ):
                    report_items.append(
                        ReportItem.error(
                            reports.messages.NodeUsedAsTieBreaker(
                                node.name, node.nodeid
                            )
                        )
                    )

    return report_items


def _check_link_options_count(
    link_count: int, max_allowed_link_count: int
) -> ReportItemList:
    report_items = []
    # make sure we don't report negative counts
    link_count = max(link_count, 0)
    max_allowed_link_count = max(max_allowed_link_count, 0)
    if link_count > max_allowed_link_count:
        # link_count < max_allowed_link_count is a valid scenario - for some
        # links no options have been specified
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncTooManyLinksOptions(
                    link_count,
                    max_allowed_link_count,
                )
            )
        )
    return report_items


def _get_link_options_validators_udp(
    options: Mapping[str, str], allow_empty_values: bool = False
) -> list[validate.ValidatorInterface]:
    # This only returns validators checking single values. Add checks for
    # intervalues relationships as needed.
    validators = [
        validate.ValueIpAddress("bindnetaddr"),
        validate.ValueIn("broadcast", ("0", "1")),
        validate.ValueIpAddress("mcastaddr"),
        validate.ValuePortNumber("mcastport"),
        validate.ValueIntegerInRange("ttl", 0, 255),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [validate.NamesIn(constants.LINK_OPTIONS_UDP, option_type="link")]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="link"
        )
        + list(validators)
    )


def _update_link_options_udp(
    new_options: Mapping[str, str], current_options: Mapping[str, str]
) -> ReportItemList:
    report_items = validate.ValidatorAll(
        _get_link_options_validators_udp(new_options, allow_empty_values=True)
    ).validate(new_options)

    # default values taken from `man corosync.conf`
    target_broadcast = _get_option_after_update(
        new_options, current_options, "broadcast", "0"
    )
    target_mcastaddr = _get_option_after_update(
        new_options, current_options, "mcastaddr", None
    )
    if target_broadcast == "1" and target_mcastaddr is not None:
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionMustBeDisabled(
                    "mcastaddr",
                    "broadcast",
                    option_type="link",
                    prerequisite_type="link",
                )
            )
        )

    return report_items


def create_link_list_udp(
    link_list: Sequence[Mapping[str, str]], max_allowed_link_count: int
) -> ReportItemList:
    """
    Validate creating udp/udpu link (interface) list options

    link_list -- list of link options
    max_allowed_link_count -- how many links is defined by addresses
    """
    if not link_list:
        # It is not mandatory to set link options. If an empty link list is
        # provided, everything is fine and we have nothing to validate.
        return []

    options = link_list[0]
    report_items = validate.ValidatorAll(
        _get_link_options_validators_udp(options, allow_empty_values=False)
    ).validate(options)
    # default values taken from `man corosync.conf`
    if options.get("broadcast", "0") == "1" and "mcastaddr" in options:
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionMustBeDisabled(
                    "mcastaddr",
                    "broadcast",
                    option_type="link",
                    prerequisite_type="link",
                )
            )
        )
    report_items.extend(
        _check_link_options_count(len(link_list), max_allowed_link_count)
    )
    return report_items


def create_link_list_knet(
    link_list: Sequence[Mapping[str, str]], max_allowed_link_count: int
) -> ReportItemList:
    """
    Validate creating knet link (interface) list options

    link_list -- list of link options
    max_allowed_link_count -- how many links is defined by addresses
    """
    if not link_list:
        # It is not mandatory to set link options. If an empty link list is
        # provided, everything is fine and we have nothing to validate. It is
        # also possible to set link options for only some of the links.
        return []

    report_items = []
    used_link_number: dict[str, int] = defaultdict(int)
    for options in link_list:
        if "linknumber" in options:
            used_link_number[options["linknumber"]] += 1
            if validate.is_integer(
                options["linknumber"], 0, constants.LINKS_KNET_MAX - 1
            ):
                if int(options["linknumber"]) >= max_allowed_link_count:
                    # first link is link0, hence >=
                    report_items.append(
                        # Links are defined by node addresses. Therefore we
                        # update link options here, we do not create links.
                        ReportItem.error(
                            reports.messages.CorosyncLinkDoesNotExistCannotUpdate(
                                options["linknumber"],
                                [str(x) for x in range(max_allowed_link_count)],
                            )
                        )
                    )
        report_items += _add_link_options_knet(options)
    non_unique_linknumbers = [
        number for number, count in used_link_number.items() if count > 1
    ]
    if non_unique_linknumbers:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncLinkNumberDuplication(
                    non_unique_linknumbers,
                )
            )
        )
    report_items.extend(
        _check_link_options_count(len(link_list), max_allowed_link_count)
    )
    return report_items


def _get_link_options_validators_knet(
    options: Mapping[str, str],
    allow_empty_values: bool = False,
    including_linknumber: bool = True,
) -> list[validate.ValidatorInterface]:
    # This only returns validators checking single values. Add checks for
    # intervalues relationships as needed.
    validators = [
        validate.ValueIntegerInRange("link_priority", 0, 255),
        validate.ValuePortNumber("mcastport"),
        validate.ValueNonnegativeInteger("ping_interval"),
        validate.ValueNonnegativeInteger("ping_precision"),
        validate.ValueNonnegativeInteger("ping_timeout"),
        validate.ValueNonnegativeInteger("pong_count"),
        validate.ValueIn("transport", ("sctp", "udp")),
    ]

    if including_linknumber:
        validators.append(
            validate.ValueIntegerInRange(
                "linknumber", 0, constants.LINKS_KNET_MAX - 1
            )
        )
        allowed_options = constants.LINK_OPTIONS_KNET_USER
    else:
        allowed_options = tuple(
            option
            for option in constants.LINK_OPTIONS_KNET_USER
            if option != "linknumber"
        )

    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [validate.NamesIn(allowed_options, option_type="link")]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="link"
        )
        + list(validators)
    )


def _get_link_options_validators_knet_relations() -> (
    list[validate.ValidatorInterface]
):
    return [
        validate.DependsOnOption(
            ["ping_interval"],
            "ping_timeout",
            option_type="link",
            prerequisite_type="link",
        ),
        validate.DependsOnOption(
            ["ping_timeout"],
            "ping_interval",
            option_type="link",
            prerequisite_type="link",
        ),
    ]


def _add_link_options_knet(options: Mapping[str, str]) -> ReportItemList:
    return validate.ValidatorAll(
        _get_link_options_validators_knet(
            options, allow_empty_values=False, including_linknumber=True
        )
        + _get_link_options_validators_knet_relations()
    ).validate(options)


def _update_link_options_knet(
    new_options: Mapping[str, str], current_options: Mapping[str, str]
) -> ReportItemList:
    # Changing linknumber is not allowed in update. It would effectively
    # delete one link and add a new one. Link update is meant for the cases
    # when there is only one link which cannot be removed and another one
    # cannot be added.

    # check dependencies in resulting options
    after_update = {}
    for option_name in ("ping_interval", "ping_timeout"):
        option_value = _get_option_after_update(
            new_options, current_options, option_name, None
        )
        if option_value is not None:
            after_update[option_name] = option_value

    return validate.ValidatorAll(
        _get_link_options_validators_knet(
            new_options, allow_empty_values=True, including_linknumber=False
        )
    ).validate(new_options) + validate.ValidatorAll(
        _get_link_options_validators_knet_relations()
    ).validate(
        after_update
    )


def add_link(
    node_addr_map: Mapping[str, str],
    link_options: Mapping[str, str],
    coro_existing_nodes: Iterable[CorosyncNode],
    pcmk_existing_nodes: Iterable[PacemakerNode],
    linknumbers_existing: StringCollection,
    transport: str,
    ip_version: str,
    force_unresolvable: bool = False,
) -> ReportItemList:
    # pylint: disable=too-many-locals
    """
    Validate adding a link

    node_addr_map -- key: node name, value: node address for the new link
    link_options -- link options
    coro_existing_nodes -- existing corosync nodes
    pcmk_existing_nodes -- existing pacemaker nodes
    linknumbers_existing -- all currently existing links (linknumbers)
    transport -- corosync transport used in the cluster
    ip_version -- ip family defined to be used in the cluster
    force_unresolvable -- if True, report unresolvable addresses as warnings
        instead of errors
    """
    report_items = []
    # We only support adding one link (that's the "1"), this may change later.
    number_of_links_to_add = 1

    # Check the transport supports adding links
    if transport not in constants.TRANSPORTS_KNET:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncCannotAddRemoveLinksBadTransport(
                    transport,
                    list(constants.TRANSPORTS_KNET),
                    add_or_not_remove=True,
                )
            )
        )
        return report_items

    # Check the allowed number of links is not exceeded
    if (
        len(linknumbers_existing) + number_of_links_to_add
        > constants.LINKS_KNET_MAX
    ):
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncCannotAddRemoveLinksTooManyFewLinks(
                    number_of_links_to_add,
                    len(linknumbers_existing) + number_of_links_to_add,
                    constants.LINKS_KNET_MAX,
                    add_or_not_remove=True,
                )
            )
        )
        # Since only one link can be added there is no point in validating the
        # link if it cannot be added. If it was possible to add more links at
        # once, it would make sense to continue walidating them (e.g. adding 4
        # links to a cluster with 5 links where max number of links is 8).
        return report_items

    # Check all nodes have their addresses specified
    (
        existing_addrs,
        dummy_existing_addr_types_dict,
        existing_names,
    ) = _extract_existing_addrs_and_names(
        coro_existing_nodes, pcmk_existing_nodes, pcmk_names=False
    )
    report_items += [
        ReportItem.error(
            reports.messages.CorosyncBadNodeAddressesCount(
                actual_count=0,
                min_count=number_of_links_to_add,
                max_count=number_of_links_to_add,
                node_name=node,
            )
        )
        for node in sorted(existing_names - set(node_addr_map.keys()))
    ]
    report_items += [
        ReportItem.error(reports.messages.NodeNotFound(node))
        for node in sorted(set(node_addr_map.keys()) - existing_names)
    ]

    get_addr_type = _addr_type_analyzer()
    unresolvable_addresses: set[str] = set()
    nodes_with_empty_addr: set[str] = set()
    addr_types: list[CorosyncNodeAddressType] = []
    for node_name, node_addr in node_addr_map.items():
        if node_addr == "":
            nodes_with_empty_addr.add(node_name)
        else:
            _validate_addr_type(
                node_addr,
                None,
                ip_version,
                get_addr_type,
                # these will get appended in the function
                addr_types,
                unresolvable_addresses,
                report_items,
            )
    if nodes_with_empty_addr:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesCannotBeEmpty(
                    sorted(nodes_with_empty_addr),
                )
            )
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )

    # Check mixing IPv4 and IPv6 in the link
    if _mixes_ipv4_ipv6(addr_types):
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncIpVersionMismatchInLinks(),
            )
        )

    # Check addresses are unique
    report_items += _report_non_unique_addresses(
        existing_addrs, list(node_addr_map.values())
    )

    # Check link options
    report_items += _add_link_options_knet(link_options)
    if "linknumber" in link_options:
        if link_options["linknumber"] in linknumbers_existing:
            report_items.append(
                ReportItem.error(
                    reports.messages.CorosyncLinkAlreadyExistsCannotAdd(
                        link_options["linknumber"],
                    )
                )
            )

    return report_items


def remove_links(
    linknumbers_to_remove: StringCollection,
    linknumbers_existing: StringCollection,
    transport: str,
) -> ReportItemList:
    """
    Validate removing links

    linknumbers_to_remove -- links to be removed (linknumbers strings)
    linknumbers_existing -- all existing linknumbers (strings)
    transport -- corosync transport used in the cluster
    """
    report_items = []

    if transport not in constants.TRANSPORTS_KNET:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncCannotAddRemoveLinksBadTransport(
                    transport,
                    list(constants.TRANSPORTS_KNET),
                    add_or_not_remove=False,
                )
            )
        )
        return report_items

    to_remove_duplicates = {
        link
        for link, count in Counter(linknumbers_to_remove).items()
        if count > 1
    }
    if to_remove_duplicates:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncLinkNumberDuplication(
                    sorted(to_remove_duplicates),
                )
            )
        )

    to_remove = frozenset(linknumbers_to_remove)
    existing = frozenset(linknumbers_existing)
    left = existing - to_remove
    nonexistent = to_remove - existing

    if not to_remove:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncCannotAddRemoveLinksNoLinksSpecified(
                    add_or_not_remove=False,
                )
            )
        )
    if len(left) < constants.LINKS_KNET_MIN:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncCannotAddRemoveLinksTooManyFewLinks(
                    # only existing links can be removed, do not count
                    # nonexistent ones
                    len(to_remove & existing),
                    len(left),
                    constants.LINKS_KNET_MIN,
                    add_or_not_remove=False,
                )
            )
        )
    if nonexistent:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncLinkDoesNotExistCannotRemove(
                    sorted(nonexistent),
                    sorted(existing),
                )
            )
        )

    return report_items


def update_link(
    linknumber: str,
    node_addr_map: Mapping[str, str],
    link_options: Mapping[str, str],
    current_link_options: Mapping[str, str],
    coro_existing_nodes: Iterable[CorosyncNode],
    pcmk_existing_nodes: Iterable[PacemakerNode],
    linknumbers_existing: StringCollection,
    transport: str,
    ip_version: str,
    force_unresolvable: bool = False,
) -> ReportItemList:
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-positional-arguments
    """
    Validate changing an existing link

    linknumber -- the link to be changed
    node_addr_map -- key: node name, value: node address for the new link
    link_options -- link options
    current_link_options -- current options of the link to be changed
    coro_existing_nodes -- existing corosync nodes; list of CorosyncNode
    pcmk_existing_nodes -- existing pacemaker nodes; list of PacemakerNode
    linknumbers_existing -- all currently existing links (linknumbers)
    transport -- corosync transport used in the cluster
    ip_version -- ip family defined to be used in the cluster
    force_unresolvable -- if True, report unresolvable addresses as warnings
        instead of errors
    """
    report_items = []
    # check the link exists
    if linknumber not in linknumbers_existing:
        # All other validations work with what is set for the existing link. If
        # the linknumber is wrong, there is no point in returning possibly
        # misleading errors.
        return [
            ReportItem.error(
                reports.messages.CorosyncLinkDoesNotExistCannotUpdate(
                    linknumber,
                    sorted(linknumbers_existing),
                )
            )
        ]
    # validate link options based on transport
    if link_options:
        if transport in constants.TRANSPORTS_UDP:
            report_items.extend(
                _update_link_options_udp(link_options, current_link_options)
            )
        elif transport in constants.TRANSPORTS_KNET:
            report_items.extend(
                _update_link_options_knet(link_options, current_link_options)
            )
    # validate addresses
    get_addr_type = _addr_type_analyzer()
    existing_names = set()
    unchanged_addrs = set()
    link_addr_types = []
    name_missing_in_corosync = False
    for coro_node in coro_existing_nodes:
        if coro_node.name:
            existing_names.add(coro_node.name)
        else:
            name_missing_in_corosync = True
        if coro_node.name and coro_node.name in node_addr_map:
            link_addr_types.append(get_addr_type(node_addr_map[coro_node.name]))
            unchanged_addrs |= set(
                coro_node.addrs_plain(except_link=linknumber)
            )
        else:
            addr = coro_node.addr_plain_for_link(linknumber)
            if addr:
                link_addr_types.append(get_addr_type(addr))
            unchanged_addrs |= set(coro_node.addrs_plain())
    for pcmk_node in pcmk_existing_nodes:
        unchanged_addrs.add(pcmk_node.addr)
    # report missing node names
    if name_missing_in_corosync:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncConfigMissingNamesOfNodes(fatal=True)
            )
        )
    # report unknown nodes
    report_items += [
        ReportItem.error(reports.messages.NodeNotFound(node))
        for node in sorted(set(node_addr_map.keys()) - existing_names)
    ]
    # validate new addresses
    unresolvable_addresses: set[str] = set()
    nodes_with_empty_addr: set[str] = set()
    dummy_addr_types: list[CorosyncNodeAddressType] = []
    for node_name, node_addr in node_addr_map.items():
        if node_addr == "":
            nodes_with_empty_addr.add(node_name)
        else:
            _validate_addr_type(
                node_addr,
                linknumber,
                ip_version,
                get_addr_type,
                # these will get appended in the function
                dummy_addr_types,
                unresolvable_addresses,
                report_items,
            )
    if nodes_with_empty_addr:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesCannotBeEmpty(
                    sorted(nodes_with_empty_addr),
                )
            )
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )
    # Check mixing IPv4 and IPv6 in the link - get addresses after update
    if _mixes_ipv4_ipv6(link_addr_types):
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncIpVersionMismatchInLinks(),
            )
        )
    # Check address are unique. If new addresses are unique and no new address
    # already exists in the set of addresses not changed by the update, then
    # the new addresses are unique.
    report_items += _report_non_unique_addresses(
        unchanged_addrs, list(node_addr_map.values())
    )

    return report_items


def _report_non_unique_addresses(
    existing_addrs: set[str], new_addrs: StringCollection
) -> ReportItemList:
    report_items = []

    already_existing_addrs = existing_addrs.intersection(new_addrs)
    if already_existing_addrs:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesAlreadyExist(
                    sorted(already_existing_addrs),
                )
            )
        )

    non_unique_addrs = {
        addr
        for addr, count in Counter(new_addrs).items()
        # empty strings are not valid addresses and they should be reported
        # from a different piece of code in a different report
        if count > 1 and addr != ""
    }
    if non_unique_addrs:
        report_items.append(
            ReportItem.error(
                reports.messages.NodeAddressesDuplication(
                    sorted(non_unique_addrs),
                )
            )
        )

    return report_items


def _get_transport_udp_generic_validators(
    options: Mapping[str, str],
    allow_empty_values: bool,
) -> list[validate.ValidatorInterface]:
    # No need to support force:
    # * values are either an enum or numbers with no range set - nothing to
    #   force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    validators = [
        validate.ValueIn("ip_version", constants.IP_VERSION_VALUES),
        validate.ValuePositiveInteger("netmtu"),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [
            validate.NamesIn(
                constants.TRANSPORT_UDP_GENERIC_OPTIONS,
                option_type="udp/udpu transport",
            )
        ]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="udp/udpu transport"
        )
        + list(validators)
    )


def _validate_transport_udp(
    generic_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    allow_empty_values: bool,
) -> ReportItemList:
    report_items = validate.ValidatorAll(
        _get_transport_udp_generic_validators(
            generic_options, allow_empty_values=allow_empty_values
        )
    ).validate(generic_options)

    if compression_options:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncTransportUnsupportedOptions(
                    "compression",
                    "udp/udpu",
                    ["knet"],
                )
            )
        )
    if crypto_options:
        report_items.append(
            ReportItem.error(
                reports.messages.CorosyncTransportUnsupportedOptions(
                    "crypto",
                    "udp/udpu",
                    ["knet"],
                )
            )
        )
    return report_items


def create_transport_udp(
    generic_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
) -> ReportItemList:
    """
    Validate creating udp/udpu transport options

    dict generic_options -- generic transport options
    dict compression_options -- compression options
    dict crypto_options -- crypto options
    """
    return _validate_transport_udp(
        generic_options,
        compression_options,
        crypto_options,
        allow_empty_values=False,
    )


def update_transport_udp(
    generic_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
) -> ReportItemList:
    """
    Validate updating udp/udpu transport options

    generic_options -- generic transport options
    compression_options -- compression options
    crypto_options -- crypto options
    """
    return _validate_transport_udp(
        generic_options,
        compression_options,
        crypto_options,
        allow_empty_values=True,
    )


def _get_transport_knet_generic_validators(
    options: Mapping[str, str],
    allow_empty_values: bool,
) -> list[validate.ValidatorInterface]:
    validators = [
        validate.ValueIn("ip_version", constants.IP_VERSION_VALUES),
        validate.ValueNonnegativeInteger("knet_pmtud_interval"),
        validate.ValueIn("link_mode", ("active", "passive", "rr")),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [
            validate.NamesIn(
                constants.TRANSPORT_KNET_GENERIC_OPTIONS,
                option_type="knet transport",
            )
        ]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="knet transport"
        )
        + list(validators)
    )


def _get_transport_knet_compression_validators(
    options: Mapping[str, str],
    allow_empty_values: bool,
) -> list[validate.ValidatorInterface]:
    validators = [
        validate.ValueNonnegativeInteger("level"),
        validate.ValueNotEmpty(
            "model", "a compression model e.g. zlib, lz4 or bzip2"
        ),
        validate.ValueNonnegativeInteger("threshold"),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [
            validate.NamesIn(
                constants.TRANSPORT_KNET_COMPRESSION_OPTIONS,
                option_type="compression",
            )
        ]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="compression"
        )
        + list(validators)
    )


def _get_transport_knet_crypto_validators(
    options: Mapping[str, str],
    allow_empty_values: bool,
) -> list[validate.ValidatorInterface]:
    validators = [
        validate.ValueIn("cipher", ("none", "aes256", "aes192", "aes128")),
        validate.ValueIn(
            "hash", ("none", "md5", "sha1", "sha256", "sha384", "sha512")
        ),
        validate.ValueIn("model", ("nss", "openssl")),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [
            validate.NamesIn(
                constants.TRANSPORT_KNET_CRYPTO_OPTIONS, option_type="crypto"
            )
        ]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="crypto"
        )
        + list(validators)
    )


def _validate_transport_knet(
    generic_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    allow_empty_values: bool,
) -> ReportItemList:
    # No need to support force:
    # * values are either an enum or numbers with no range set - nothing to
    #   force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare

    generic_validators = _get_transport_knet_generic_validators(
        generic_options,
        allow_empty_values=allow_empty_values,
    )
    crypto_validators = _get_transport_knet_crypto_validators(
        crypto_options,
        allow_empty_values=allow_empty_values,
    )
    compression_validators = _get_transport_knet_compression_validators(
        compression_options,
        allow_empty_values=allow_empty_values,
    )

    return (
        validate.ValidatorAll(generic_validators).validate(generic_options)
        + validate.ValidatorAll(compression_validators).validate(
            compression_options
        )
        + validate.ValidatorAll(crypto_validators).validate(crypto_options)
    )


def create_transport_knet(
    generic_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
) -> ReportItemList:
    """
    Validate creating knet transport options

    generic_options -- generic transport options
    compression_options -- compression options
    crypto_options -- crypto options
    """
    report_items = _validate_transport_knet(
        generic_options,
        compression_options,
        crypto_options,
        allow_empty_values=False,
    )

    if (
        # default values taken from `man corosync.conf`
        crypto_options.get("cipher", "none") != "none"
        and crypto_options.get("hash", "none") == "none"
    ):
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionMustBeEnabledAsWell(
                    "cipher",
                    "hash",
                    option_type="crypto",
                    prerequisite_type="crypto",
                )
            )
        )

    return report_items


def update_transport_knet(
    generic_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    current_crypto_options: Mapping[str, str],
) -> ReportItemList:
    """
    Validate updating knet transport options

    generic_options -- generic transport options
    compression_options -- compression options
    crypto_options -- crypto options
    current_crypto_options -- crypto options currently configured
    """
    report_items = _validate_transport_knet(
        generic_options,
        compression_options,
        crypto_options,
        allow_empty_values=True,
    )

    # there are 2 possibilities how to disable crypto options:
    #   1. set it to "none"
    #   2. set it to default, which is "none" according to `man corosync.conf`,
    #      by using value of empty string
    crypto_cipher_enabled = crypto_options.get(
        "cipher",
        current_crypto_options.get("cipher", "none"),
    ) not in ["none", ""]

    crypto_hash_disabled = crypto_options.get(
        "hash",
        current_crypto_options.get("hash", "none"),
    ) in ["none", ""]

    if crypto_cipher_enabled and crypto_hash_disabled:
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionMustBeEnabledAsWell(
                    "cipher",
                    "hash",
                    option_type="crypto",
                    prerequisite_type="crypto",
                )
            )
        )

    return report_items


def _get_totem_options_validators(
    options: Mapping[str, str], allow_empty_values: bool = False
) -> list[validate.ValidatorInterface]:
    # No need to support force:
    # * values are either bool or numbers with no range set - nothing to force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    validators = [
        validate.ValueIn("block_unlisted_ips", ["yes", "no"]),
        validate.ValueNonnegativeInteger("consensus"),
        validate.ValueNonnegativeInteger("downcheck"),
        validate.ValueNonnegativeInteger("fail_recv_const"),
        validate.ValueNonnegativeInteger("heartbeat_failures_allowed"),
        validate.ValueNonnegativeInteger("hold"),
        validate.ValueNonnegativeInteger("join"),
        validate.ValueNonnegativeInteger("max_messages"),
        validate.ValueNonnegativeInteger("max_network_delay"),
        validate.ValueNonnegativeInteger("merge"),
        validate.ValueNonnegativeInteger("miss_count_const"),
        validate.ValueNonnegativeInteger("send_join"),
        validate.ValueNonnegativeInteger("seqno_unchanged_const"),
        validate.ValueNonnegativeInteger("token"),
        validate.ValueNonnegativeInteger("token_coefficient"),
        validate.ValueNonnegativeInteger("token_retransmit"),
        validate.ValueNonnegativeInteger("token_retransmits_before_loss_const"),
        validate.ValueNonnegativeInteger("window_size"),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [validate.NamesIn(constants.TOTEM_OPTIONS, option_type="totem")]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="totem"
        )
        + list(validators)
    )


def _validate_totem_options(
    options: Mapping[str, str], allow_empty_values: bool
) -> ReportItemList:
    return validate.ValidatorAll(
        _get_totem_options_validators(
            options, allow_empty_values=allow_empty_values
        )
    ).validate(options)


def create_totem(options: Mapping[str, str]) -> ReportItemList:
    """
    Validate creating the "totem" section

    options -- totem options
    """
    return _validate_totem_options(options, allow_empty_values=False)


def update_totem(options: Mapping[str, str]) -> ReportItemList:
    """
    Validate updating the "totem" section

    options -- totem options
    """
    return _validate_totem_options(options, allow_empty_values=True)


def create_quorum_options(
    options: Mapping[str, str], has_qdevice: bool
) -> ReportItemList:
    """
    Validate creating quorum options

    options -- quorum options to set
    has_qdevice -- is a qdevice set in corosync.conf?
    """
    # No need to support force:
    # * values are either bool or numbers with no range set - nothing to force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    report_items = _validate_quorum_options(
        options, has_qdevice, allow_empty_values=False
    )
    if (
        # Default value in corosync is 10 ms. However, that would always fail
        # the validation, so we use the default value of 0.
        options.get("last_man_standing_window", "0") != "0"
        and
        # default value taken from `man corosync.conf`
        options.get("last_man_standing", "0") == "0"
    ):
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionMustBeEnabledAsWell(
                    "last_man_standing_window",
                    "last_man_standing",
                    option_type="quorum",
                    prerequisite_type="quorum",
                )
            )
        )
    return report_items


def update_quorum_options(
    options: Mapping[str, str],
    has_qdevice: bool,
    current_options: Mapping[str, str],
) -> ReportItemList:
    """
    Validate modifying quorum options

    options -- quorum options to set
    has_qdevice -- is a qdevice set in corosync.conf?
    current_options -- currently set quorum options
    """
    # No need to support force:
    # * values are either bool or numbers with no range set - nothing to force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    report_items = _validate_quorum_options(
        options, has_qdevice, allow_empty_values=True
    )
    effective_lms = options.get(
        "last_man_standing",
        # default value taken from `man corosync.conf`
        current_options.get("last_man_standing", "0"),
    )
    if (
        # Default value in corosync is 10 ms. However, that would always fail
        # the validation, so we use the default value of 0.
        options.get("last_man_standing_window", "0") != "0"
        and effective_lms == "0"
    ):
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionMustBeEnabledAsWell(
                    "last_man_standing_window",
                    "last_man_standing",
                    option_type="quorum",
                    prerequisite_type="quorum",
                )
            )
        )
    return report_items


def _validate_quorum_options(
    options: Mapping[str, str], has_qdevice: bool, allow_empty_values: bool
) -> ReportItemList:
    report_items = validate.ValidatorAll(
        _get_quorum_options_validators(
            options, allow_empty_values=allow_empty_values
        )
    ).validate(options)

    if has_qdevice:
        qdevice_incompatible_options = [
            name
            for name in options
            if name in constants.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
        ]
        if qdevice_incompatible_options:
            report_items.append(
                ReportItem.error(
                    reports.messages.CorosyncOptionsIncompatibleWithQdevice(
                        qdevice_incompatible_options,
                    )
                )
            )

    return report_items


def _get_quorum_options_validators(
    options: Mapping[str, str], allow_empty_values: bool = False
) -> list[validate.ValidatorInterface]:
    allowed_bool = ("0", "1")
    validators = [
        validate.ValueIn("auto_tie_breaker", allowed_bool),
        validate.ValueIn("last_man_standing", allowed_bool),
        validate.ValuePositiveInteger("last_man_standing_window"),
        validate.ValueIn("wait_for_all", allowed_bool),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return (
        [validate.NamesIn(constants.QUORUM_OPTIONS, option_type="quorum")]
        + _get_unsuitable_keys_and_values_validators(
            options, option_type="quorum"
        )
        + list(validators)
    )


def add_quorum_device(
    model: str,
    model_options: Mapping[str, str],
    generic_options: Mapping[str, str],
    heuristics_options: Mapping[str, str],
    node_ids: StringCollection,
    force_model: bool = False,
    force_options: bool = False,
) -> ReportItemList:
    """
    Validate adding a quorum device

    model -- quorum device model
    model_options -- model specific options
    generic_options -- generic quorum device options
    heuristics_options -- heuristics options
    node_ids -- list of existing node ids
    force_model -- continue even if the model is not valid
    force_options -- turn forceable errors into warnings
    """
    if model == "net":
        model_report_items = _qdevice_add_model_net_options(
            model_options, node_ids, force_options=force_options
        )
    else:
        model_report_items = validate.ValidatorAll(
            [
                validate.ValueIn(
                    "model",
                    ["net"],
                    severity=reports.item.get_severity(
                        reports.codes.FORCE, force_model
                    ),
                ),
                validate.ValueCorosyncValue("model"),
            ]
        ).validate({"model": model})

    return (
        model_report_items
        + validate.ValidatorAll(
            _get_unsuitable_keys_and_values_validators(
                model_options, "quorum device model"
            )
        ).validate(model_options)
        + validate.ValidatorAll(
            _get_qdevice_generic_options_validators(
                generic_options, force_options=force_options
            )
        ).validate(generic_options)
        + _qdevice_add_heuristics_options(heuristics_options, force_options)
    )


def update_quorum_device(
    model: str,
    model_options: Mapping[str, str],
    generic_options: Mapping[str, str],
    heuristics_options: Mapping[str, str],
    node_ids: StringCollection,
    force_options: bool = False,
) -> ReportItemList:
    """
    Validate updating a quorum device

    model -- quorum device model
    model_options -- model specific options
    generic_options -- generic quorum device options
    heuristics_options -- heuristics options
    node_ids -- list of existing node ids
    force_options -- turn forceable errors into warnings
    """
    if model == "net":
        model_report_items = _qdevice_update_model_net_options(
            model_options, node_ids, force_options
        )
    else:
        model_report_items = []

    return (
        model_report_items
        + validate.ValidatorAll(
            _get_unsuitable_keys_and_values_validators(
                model_options, "quorum device model"
            )
        ).validate(model_options)
        + validate.ValidatorAll(
            _get_qdevice_generic_options_validators(
                generic_options,
                allow_empty_values=True,
                force_options=force_options,
            )
        ).validate(generic_options)
        + _qdevice_update_heuristics_options(heuristics_options, force_options)
    )


def _qdevice_add_heuristics_options(
    options: Mapping[str, str], force_options: bool = False
) -> ReportItemList:
    """
    Validate quorum device heuristics options when adding a quorum device

    options -- heuristics options
    force_options -- turn forceable errors into warnings
    """
    options_nonexec, options_exec = _split_heuristics_exec_options(options)
    validators_nonexec = _get_qdevice_heuristics_nonexec_options_validators(
        force_options=force_options
    )
    validators_exec = [
        validate.ValueNotEmpty(option, "a command to be run")
        for option in options_exec
    ]
    return (
        validate.ValidatorAll(
            _get_unsuitable_keys_and_values_validators(options, "heuristics")
        ).validate(options)
        + validate.ValidatorAll(validators_nonexec).validate(options_nonexec)
        + validate.ValidatorAll(validators_exec).validate(options_exec)
    )


def _qdevice_update_heuristics_options(
    options: Mapping[str, str], force_options: bool = False
) -> ReportItemList:
    """
    Validate quorum device heuristics options when updating a quorum device

    options -- heuristics options
    force_options -- turn forceable errors into warnings
    """
    options_nonexec, dummy_options_exec = _split_heuristics_exec_options(
        options
    )
    validators_nonexec = _get_qdevice_heuristics_nonexec_options_validators(
        allow_empty_values=True, force_options=force_options
    )
    # No validation necessary for values of exec options - they are either
    # empty (meaning they will be removed) or nonempty strings.
    return validate.ValidatorAll(
        _get_unsuitable_keys_and_values_validators(options, "heuristics")
    ).validate(options) + validate.ValidatorAll(validators_nonexec).validate(
        options_nonexec
    )


def _qdevice_add_model_net_options(
    options: Mapping[str, str],
    node_ids: StringCollection,
    force_options: bool = False,
) -> ReportItemList:
    """
    Validate quorum device model options when adding a quorum device

    options -- model options
    node_ids -- list of existing node ids
    force_options -- turn forceable errors into warnings
    """
    return validate.ValidatorAll(
        [
            validate.IsRequiredAll(
                _QDEVICE_NET_REQUIRED_OPTIONS, option_type="quorum device model"
            )
        ]
        + _get_qdevice_model_net_options_validators(
            node_ids, force_options=force_options
        )
    ).validate(options)


def _qdevice_update_model_net_options(
    options: Mapping[str, str],
    node_ids: StringCollection,
    force_options: bool = False,
) -> ReportItemList:
    """
    Validate quorum device model options when updating a quorum device

    options -- model options
    node_ids -- list of existing node ids
    force_options -- turn forceable errors into warnings
    """
    return validate.ValidatorAll(
        _get_qdevice_model_net_options_validators(
            node_ids, allow_empty_values=True, force_options=force_options
        )
    ).validate(options)


def _get_qdevice_generic_options_validators(
    options: Mapping[str, str],
    allow_empty_values: bool = False,
    force_options: bool = False,
) -> list[validate.ValidatorInterface]:
    severity = reports.item.get_severity(reports.codes.FORCE, force_options)

    validators = [
        validate.ValuePositiveInteger("sync_timeout", severity=severity),
        validate.ValuePositiveInteger("timeout", severity=severity),
    ]
    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True

    return (
        [
            validate.NamesIn(
                ["sync_timeout", "timeout"],
                option_type="quorum device",
                banned_name_list=["model"],
                severity=severity,
            )
        ]
        + _get_unsuitable_keys_and_values_validators(options, "quorum device")
        + list(validators)
    )


def _split_heuristics_exec_options(
    options: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    options_exec = {}
    options_nonexec = {}
    for name, value in options.items():
        if name.startswith("exec_"):
            options_exec[name] = value
        else:
            options_nonexec[name] = value
    return options_nonexec, options_exec


def _get_qdevice_heuristics_nonexec_options_validators(
    allow_empty_values: bool = False, force_options: bool = False
) -> list[validate.ValidatorInterface]:
    severity = reports.item.get_severity(reports.codes.FORCE, force_options)

    allowed_options = [
        "interval",
        "mode",
        "sync_timeout",
        "timeout",
    ]
    validators = [
        validate.ValueIn("mode", ("off", "on", "sync"), severity=severity),
        validate.ValuePositiveInteger("interval", severity=severity),
        validate.ValuePositiveInteger("sync_timeout", severity=severity),
        validate.ValuePositiveInteger("timeout", severity=severity),
    ]

    if allow_empty_values:
        for val in validators:
            val.empty_string_valid = True
    return [
        validate.NamesIn(
            allowed_options,
            allowed_option_patterns=["exec_NAME"],
            option_type="heuristics",
            severity=severity,
        )
    ] + list(validators)


def _get_qdevice_model_net_options_validators(
    node_ids: StringCollection,
    allow_empty_values: bool = False,
    force_options: bool = False,
) -> list[validate.ValidatorInterface]:
    severity = reports.item.get_severity(reports.codes.FORCE, force_options)
    allowed_algorithms = ("ffsplit", "lms")

    validators_required_options = [
        validate.ValidatorFirstError(
            [
                validate.ValueNotEmpty("algorithm", allowed_algorithms),
                validate.ValueIn(
                    "algorithm", allowed_algorithms, severity=severity
                ),
            ]
        ),
        validate.ValueNotEmpty("host", "a qdevice host address"),
    ]
    validators_optional_options = [
        validate.ValueIntegerInRange(
            "connect_timeout", 1000, 2 * 60 * 1000, severity=severity
        ),
        validate.ValueIn(
            "force_ip_version", ("0", "4", "6"), severity=severity
        ),
        validate.ValuePortNumber("port", severity=severity),
        validate.ValueIn(
            "tie_breaker",
            ["lowest", "highest"] + sorted(node_ids),
            severity=severity,
        ),
        validate.ValueIn("tls", ("on", "off", "required"), severity=severity),
        validate.ValueIn(
            "keep_active_partition_tie_breaker",
            ("on", "off"),
            severity=severity,
        ),
    ]

    if allow_empty_values:
        for val in validators_optional_options:
            val.empty_string_valid = True
    return (
        [
            validate.NamesIn(
                _QDEVICE_NET_REQUIRED_OPTIONS + _QDEVICE_NET_OPTIONAL_OPTIONS,
                option_type="quorum device model",
                severity=severity,
            )
        ]
        + validators_required_options
        + list(validators_optional_options)
    )


def _get_option_after_update(
    new_options: Mapping[str, str],
    current_options: Mapping[str, str],
    option_name: str,
    default_value: Optional[str],
) -> Optional[str]:
    if option_name in new_options:
        if new_options[option_name] == "":
            return default_value
        return new_options[option_name]
    return current_options.get(option_name, default_value)


def _get_unsuitable_keys_and_values_validators(
    option_dict: Mapping[str, str], option_type: Optional[str] = None
) -> list[validate.ValidatorInterface]:
    return [validate.CorosyncOption(option_type=option_type)] + [
        validate.ValueCorosyncValue(name) for name in option_dict
    ]


def _mixes_ipv4_ipv6(addr_types: Collection[CorosyncNodeAddressType]) -> bool:
    return {CorosyncNodeAddressType.IPV4, CorosyncNodeAddressType.IPV6} <= set(
        addr_types
    )
