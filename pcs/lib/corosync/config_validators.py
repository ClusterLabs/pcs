from collections import Counter, defaultdict, namedtuple
from itertools import zip_longest

from pcs.common import report_codes
from pcs.lib import reports, validate
from pcs.lib.corosync import constants
from pcs.lib.corosync.node import(
    ADDR_IPV4,
    ADDR_IPV6,
    ADDR_FQDN,
    ADDR_UNRESOLVABLE,
    get_address_type
)
from pcs.lib.errors import ReportItemSeverity

_QDEVICE_NET_REQUIRED_OPTIONS = (
    "algorithm",
    "host",
)
_QDEVICE_NET_OPTIONAL_OPTIONS = (
    "connect_timeout",
    "force_ip_version",
    "port",
    "tie_breaker",
)

class _LinkAddrType(
    namedtuple("_LinkAddrType", "link addr_type")
):
    pass


def create(cluster_name, node_list, transport, force_unresolvable=False):
    """
    Validate creating a new minimalistic corosync.conf

    string cluster_name -- the name of the new cluster
    list node_list -- nodes of the new cluster; dict: name, addrs
    string transport -- corosync transport used in the new cluster
    bool force_unresolvable -- if True, report unresolvable addresses as
        warnings instead of errors
    """
    # cluster name and transport validation
    validators = [
        validate.value_not_empty("name", "a non-empty string", "cluster name"),
        validate.value_in("transport", constants.TRANSPORTS_ALL)
    ]
    report_items = validate.run_collection_of_option_validators(
        {
            "name": cluster_name,
            "transport": transport
        },
        validators
    )

    # nodelist validation
    get_addr_type = _addr_type_analyzer()
    all_names_usable = True # can names be used to identifying nodes?
    all_names_count = defaultdict(int)
    all_addrs_count = defaultdict(int)
    addr_types_per_node = []
    unresolvable_addresses = set()
    # First, validate each node on its own. Also extract some info which will
    # be needed when validating the nodelist and inter-node dependencies.
    for i, node in enumerate(node_list, 1):
        report_items.extend(
            validate.run_collection_of_option_validators(
                node,
                _get_node_name_validators(i)
            )
            +
            validate.names_in(["addrs", "name"], node.keys(), "node")
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
        if transport in (constants.TRANSPORTS_KNET + constants.TRANSPORTS_UDP):
            if transport in constants.TRANSPORTS_KNET:
                min_addr_count = constants.LINKS_KNET_MIN
                max_addr_count = constants.LINKS_KNET_MAX
            else:
                min_addr_count = constants.LINKS_UDP_MIN
                max_addr_count = constants.LINKS_UDP_MAX
            if (
                addr_count < min_addr_count
                or
                addr_count > max_addr_count
            ):
                report_items.append(
                    reports.corosync_bad_node_addresses_count(
                        addr_count,
                        min_addr_count,
                        max_addr_count,
                        node_name=node.get("name"),
                        node_index=i
                    )
                )
        addr_types = []
        # Cannot use node.get("addrs", []) - if node["addrs"] == None then
        # the get returns None and len(None) raises an exception.
        for addr in (node.get("addrs") or []):
            all_addrs_count[addr] += 1
            addr_types.append(get_addr_type(addr))
            if get_addr_type(addr) == ADDR_UNRESOLVABLE:
                unresolvable_addresses.add(addr)
        addr_types_per_node.append(addr_types)
    # Report all unresolvable addresses at once instead on each own.
    if unresolvable_addresses:
        severity = ReportItemSeverity.ERROR
        forceable = report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE
        if force_unresolvable:
            severity = ReportItemSeverity.WARNING
            forceable = None
        report_items.append(
            reports.node_addresses_unresolvable(
                unresolvable_addresses,
                severity,
                forceable
            )
        )

    # Reporting single-node errors finished.
    # Now report nodelist and inter-node errors.
    if len(node_list) < 1:
        report_items.append(reports.corosync_nodes_missing())
    non_unique_names = set([
        name for name, count in all_names_count.items() if count > 1
    ])
    if non_unique_names:
        all_names_usable = False
        report_items.append(
            reports.node_names_duplication(non_unique_names)
        )
    non_unique_addrs = set([
        addr for addr, count in all_addrs_count.items() if count > 1
    ])
    if non_unique_addrs:
        report_items.append(
            reports.node_addresses_duplication(non_unique_addrs)
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
            and
            len(Counter(node_addr_count.values()).keys()) > 1
        ):
            report_items.append(
                reports.corosync_node_address_count_mismatch(node_addr_count)
            )
    # Check mixing IPv4 and IPv6 in one link, node names are not relevant
    links_ip_mismatch = []
    for link, addr_types in enumerate(zip_longest(*addr_types_per_node)):
        if ADDR_IPV4 in addr_types and ADDR_IPV6 in addr_types:
            links_ip_mismatch.append(link)
    if links_ip_mismatch:
        report_items.append(
            reports.corosync_ip_version_mismatch_in_links(links_ip_mismatch)
        )

    return report_items

def _get_node_name_validators(node_index):
    return [
        validate.is_required("name", f"node {node_index}"),
        validate.value_not_empty(
            "name",
            "a non-empty string",
            option_name_for_report=f"node {node_index} name"
        )
    ]

def _addr_type_analyzer():
    cache = dict()
    def analyzer(addr):
        if addr not in cache:
            cache[addr] = get_address_type(addr, resolve=True)
        return cache[addr]
    return analyzer

def add_nodes(
    node_list, coro_existing_nodes, pcmk_existing_nodes,
    force_unresolvable=False
):
    """
    Validate adding nodes to a config with a nonempty nodelist

    list node_list -- new nodes data; list of dict: name, addrs
    list coro_existing_nodes -- existing corosync nodes; list of CorosyncNode
    list pcmk_existing_nodes -- existing pacemaker nodes; list of PacemakerNode
    bool force_unresolvable -- if True, report unresolvable addresses as
        warnings instead of errors
    """
    # extract info from existing nodes
    existing_names = set()
    existing_addrs = set()
    existing_addr_types_dict = dict()
    for node in coro_existing_nodes:
        existing_names.add(node.name)
        existing_addrs.update(set(node.addrs_plain))
        for addr in node.addrs:
            # If two nodes have FQDN and one has IPv4, we want to keep the IPv4
            if (
                addr.type not in (ADDR_FQDN, ADDR_UNRESOLVABLE)
                or
                addr.link not in existing_addr_types_dict
            ):
                existing_addr_types_dict[addr.link] = addr.type
    for node in pcmk_existing_nodes:
        existing_names.add(node.name)
        existing_addrs.add(node.addr)
    existing_addr_types = sorted([
        _LinkAddrType(link_number, addr_type)
        for link_number, addr_type in existing_addr_types_dict.items()
    ])
    number_of_existing_links = len(existing_addr_types)

    # validation
    get_addr_type = _addr_type_analyzer()
    report_items = []
    new_names_count = defaultdict(int)
    new_addrs_count = defaultdict(int)
    new_addr_types_per_node = []
    links_ip_mismatch_reported = set()
    unresolvable_addresses = set()

    # First, validate each node on its own. Also extract some info which will
    # be needed when validating the nodelist and inter-node dependencies.
    for i, node in enumerate(node_list, 1):
        report_items.extend(
            validate.run_collection_of_option_validators(
                node,
                _get_node_name_validators(i)
            )
            +
            validate.names_in(["addrs", "name"], node.keys(), "node")
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
                reports.corosync_bad_node_addresses_count(
                    addr_count,
                    number_of_existing_links,
                    number_of_existing_links,
                    node_name=node.get("name"),
                    node_index=i
                )
            )
        addr_types = []
        # Cannot use node.get("addrs", []) - if node["addrs"] == None then
        # the get returns None and len(None) raises an exception.
        for link_index, addr in enumerate(node.get("addrs") or []):
            new_addrs_count[addr] += 1
            addr_types.append(get_addr_type(addr))
            if get_addr_type(addr) == ADDR_UNRESOLVABLE:
                unresolvable_addresses.add(addr)
            # Check matching IPv4 / IPv6 in existing links. FQDN matches with
            # both IPv4 and IPv6 as it can resolve to both. Unresolvable is a
            # special case of FQDN so we don't need to check it.
            if (
                link_index < number_of_existing_links
                and
                get_addr_type(addr) not in (ADDR_FQDN, ADDR_UNRESOLVABLE)
                and
                existing_addr_types[link_index].addr_type != ADDR_FQDN
                and
                get_addr_type(addr) != existing_addr_types[link_index].addr_type
            ):
                links_ip_mismatch_reported.add(
                    existing_addr_types[link_index].link
                )
                report_items.append(
                    reports.corosync_address_ip_version_wrong_for_link(
                        addr,
                        existing_addr_types[link_index].addr_type,
                        existing_addr_types[link_index].link,
                    )
                )

        new_addr_types_per_node.append(addr_types)
    # Report all unresolvable addresses at once instead on each own.
    if unresolvable_addresses:
        severity = ReportItemSeverity.ERROR
        forceable = report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE
        if force_unresolvable:
            severity = ReportItemSeverity.WARNING
            forceable = None
        report_items.append(
            reports.node_addresses_unresolvable(
                unresolvable_addresses,
                severity,
                forceable
            )
        )

    # Reporting single-node errors finished.
    # Now report nodelist and inter-node errors.
    if len(node_list) < 1:
        report_items.append(reports.corosync_nodes_missing())
    # Check nodes' names and address are unique
    already_existing_names = existing_names.intersection(new_names_count.keys())
    if already_existing_names:
        report_items.append(
            reports.node_names_already_exist(already_existing_names)
        )
    already_existing_addrs = existing_addrs.intersection(new_addrs_count.keys())
    if already_existing_addrs:
        report_items.append(
            reports.node_addresses_already_exist(already_existing_addrs)
        )
    non_unique_names = set([
        name for name, count in new_names_count.items() if count > 1
    ])
    if non_unique_names:
        report_items.append(
            reports.node_names_duplication(non_unique_names)
        )
    non_unique_addrs = set([
        addr for addr, count in new_addrs_count.items() if count > 1
    ])
    if non_unique_addrs:
        report_items.append(
            reports.node_addresses_duplication(non_unique_addrs)
        )
    # Check mixing IPv4 and IPv6 in one link, node names are not relevant,
    # skip links already reported due to new nodes have wrong IP version
    existing_links = [x.link for x in existing_addr_types]
    links_ip_mismatch = []
    for link_index, addr_types in enumerate(
            zip_longest(*new_addr_types_per_node)
    ):
        if (
            ADDR_IPV4 in addr_types and ADDR_IPV6 in addr_types
            and
            existing_links[link_index] not in links_ip_mismatch_reported
        ):
            links_ip_mismatch.append(existing_links[link_index])
    if links_ip_mismatch:
        report_items.append(
            reports.corosync_ip_version_mismatch_in_links(links_ip_mismatch)
        )
    return report_items

def remove_nodes(nodes_names_to_remove, existing_nodes, quorum_device_settings):
    """
    Validate removing nodes

    iterable nodes_names_to_remove -- list of names of nodes to remove
    iterable existing_nodes -- list of all existing nodes
    tuple quorum_device_settings -- output of get_quorum_device_settings
    """
    existing_node_names = [node.name for node in existing_nodes]
    report_items = []
    for node in set(nodes_names_to_remove) - set(existing_node_names):
        report_items.append(reports.node_not_found(node))

    if len(set(existing_node_names) - set(nodes_names_to_remove)) == 0:
        report_items.append(reports.cannot_remove_all_cluster_nodes())

    qdevice_model, qdevice_model_options, _, _ = quorum_device_settings
    if qdevice_model == "net":
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
                        reports.node_used_as_tie_breaker(node.name, node.nodeid)
                    )

    return report_items

def create_link_list_udp(link_list):
    """
    Validate creating udp/udpu link (interface) list options

    iterable link_list -- list of link options
    """
    if not link_list:
        # It is not mandatory to set link options. If an empty link list is
        # provided, everything is fine and we have nothing to validate.
        return []

    allowed_options = [
        "bindnetaddr",
        "broadcast",
        "mcastaddr",
        "mcastport",
        "ttl",
    ]
    validators = [
        validate.value_ip_address("bindnetaddr"),
        validate.value_in("broadcast", ("0", "1")),
        validate.value_ip_address("mcastaddr"),
        validate.value_port_number("mcastport"),
        validate.value_integer_in_range("ttl", 0, 255),
    ]
    options = link_list[0]
    report_items = (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(allowed_options, options.keys(), "link")
    )
    # default values taken from `man corosync.conf`
    if options.get("broadcast", "0") == "1" and "mcastaddr" in options:
        report_items.append(
            reports.prerequisite_option_must_be_disabled(
                "mcastaddr",
                "broadcast",
                option_type="link",
                prerequisite_type="link"
            )
        )
    link_count = len(link_list)
    if link_count > constants.LINKS_UDP_MAX:
        report_items.append(
            reports.corosync_too_many_links(
                link_count,
                constants.LINKS_UDP_MAX,
                "udp/udpu"
            )
        )
    return report_items

def create_link_list_knet(link_list, max_link_number):
    """
    Validate creating knet link (interface) list options

    iterable link_list -- list of link options
    integer max_link_number -- highest allowed linknumber
    """
    if not link_list:
        # It is not mandatory to set link options. If an empty link list is
        # provided, everything is fine and we have nothing to validate. It is
        # also possible to set link options for only some of the links.
        return []
    max_link_number = max(0, min(constants.LINKS_KNET_MAX - 1, max_link_number))
    max_link_count = max_link_number + 1
    allowed_options = [
        "ip_version", # It tells knet which IP to prefer.
        "linknumber",
        "link_priority",
        "mcastport",
        "ping_interval",
        "ping_precision",
        "ping_timeout",
        "pong_count",
        "transport",
    ]
    validators = [
        validate.value_in("ip_version", ("ipv4", "ipv6")),
        validate.value_integer_in_range("linknumber", 0, max_link_number),
        validate.value_integer_in_range("link_priority", 0, 255),
        validate.value_port_number("mcastport"),
        validate.value_nonnegative_integer("ping_interval"),
        validate.value_nonnegative_integer("ping_precision"),
        validate.value_nonnegative_integer("ping_timeout"),
        validate.depends_on_option(
            "ping_interval",
            "ping_timeout",
            option_type="link",
            prerequisite_type="link"
        ),
        validate.depends_on_option(
            "ping_timeout",
            "ping_interval",
            option_type="link",
            prerequisite_type="link"
        ),
        validate.value_nonnegative_integer("pong_count"),
        validate.value_in("transport", ("sctp", "udp")),
    ]
    report_items = []
    used_link_number = defaultdict(int)
    for options in link_list:
        if "linknumber" in options:
            used_link_number[options["linknumber"]] += 1
        report_items += (
            validate.run_collection_of_option_validators(options, validators)
            +
            validate.names_in(allowed_options, options.keys(), "link")
        )
    non_unique_linknumbers = [
        number for number, count in used_link_number.items() if count > 1
    ]
    if non_unique_linknumbers:
        report_items.append(
            reports.corosync_link_number_duplication(non_unique_linknumbers)
        )
    link_count = len(link_list)
    if link_count > max_link_count:
        report_items.append(
            reports.corosync_too_many_links(link_count, max_link_count, "knet")
        )
    return report_items

def create_transport_udp(generic_options, compression_options, crypto_options):
    """
    Validate creating udp/udpu transport options

    dict generic_options -- generic transport options
    dict compression_options -- compression options
    dict crypto_options -- crypto options
    """
    # No need to support force:
    # * values are either an enum or numbers with no range set - nothing to force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    allowed_options = [
        "ip_version",
        "netmtu",
    ]
    validators = [
        validate.value_in("ip_version", ("ipv4", "ipv6")),
        validate.value_positive_integer("netmtu"),
    ]
    report_items = (
        validate.run_collection_of_option_validators(
            generic_options,
            validators
        )
        +
        validate.names_in(
            allowed_options,
            generic_options.keys(),
            "udp/udpu transport"
        )
    )
    if compression_options:
        report_items.append(
            reports.corosync_transport_unsupported_options(
                "compression",
                "udp/udpu",
                ("knet", )
            )
        )
    if crypto_options:
        report_items.append(
            reports.corosync_transport_unsupported_options(
                "crypto",
                "udp/udpu",
                ("knet", )
            )
        )
    return report_items

def create_transport_knet(generic_options, compression_options, crypto_options):
    """
    Validate creating knet transport options

    dict generic_options -- generic transport options
    dict compression_options -- compression options
    dict crypto_options -- crypto options
    """
    # No need to support force:
    # * values are either an enum or numbers with no range set - nothing to force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    generic_allowed = [
        "ip_version", # It tells knet which IP to prefer.
        "knet_pmtud_interval",
        "link_mode",
    ]
    generic_validators = [
        validate.value_in("ip_version", ("ipv4", "ipv6")),
        validate.value_nonnegative_integer("knet_pmtud_interval"),
        validate.value_in("link_mode", ("active", "passive", "rr")),
    ]
    compression_allowed = [
        "level",
        "model",
        "threshold",
    ]
    compression_validators = [
        validate.value_nonnegative_integer("level"),
        validate.value_not_empty(
            "model",
            "a compression model e.g. zlib, lz4 or bzip2"
        ),
        validate.value_nonnegative_integer("threshold"),
    ]
    crypto_type = "crypto"
    crypto_allowed = [
        "cipher",
        "hash",
        "model",
    ]
    crypto_validators = [
        validate.value_in(
            "cipher",
            ("none", "aes256", "aes192", "aes128", "3des")
        ),
        validate.value_in(
            "hash",
            ("none", "md5", "sha1", "sha256", "sha384", "sha512")
        ),
        validate.value_in("model", ("nss", "openssl")),
    ]
    report_items = (
        validate.run_collection_of_option_validators(
            generic_options,
            generic_validators
        )
        +
        validate.names_in(
            generic_allowed,
            generic_options.keys(),
            "knet transport"
        )
        +
        validate.run_collection_of_option_validators(
            compression_options,
            compression_validators
        )
        +
        validate.names_in(
            compression_allowed,
            compression_options.keys(),
            "compression"
        )
        +
        validate.run_collection_of_option_validators(
            crypto_options,
            crypto_validators
        )
        +
        validate.names_in(
            crypto_allowed,
            crypto_options.keys(),
            crypto_type
        )
    )
    if (
        # default values taken from `man corosync.conf`
        crypto_options.get("cipher", "aes256") != "none"
        and
        crypto_options.get("hash", "sha1") == "none"
    ):
        report_items.append(
            reports.prerequisite_option_must_be_enabled_as_well(
                "cipher",
                "hash",
                option_type="crypto",
                prerequisite_type="crypto"
            )
        )
    return report_items

def create_totem(options):
    """
    Validate creating the "totem" section

    dict options -- totem options
    """
    # No need to support force:
    # * values are either bool or numbers with no range set - nothing to force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    allowed_options = [
        "consensus",
        "downcheck",
        "fail_recv_const",
        "heartbeat_failures_allowed",
        "hold",
        "join",
        "max_messages",
        "max_network_delay",
        "merge",
        "miss_count_const",
        "send_join",
        "seqno_unchanged_const",
        "token",
        "token_coefficient",
        "token_retransmit",
        "token_retransmits_before_loss_const",
        "window_size",
    ]
    validators = [
        validate.value_nonnegative_integer("consensus"),
        validate.value_nonnegative_integer("downcheck"),
        validate.value_nonnegative_integer("fail_recv_const"),
        validate.value_nonnegative_integer("heartbeat_failures_allowed"),
        validate.value_nonnegative_integer("hold"),
        validate.value_nonnegative_integer("join"),
        validate.value_nonnegative_integer("max_messages"),
        validate.value_nonnegative_integer("max_network_delay"),
        validate.value_nonnegative_integer("merge"),
        validate.value_nonnegative_integer("miss_count_const"),
        validate.value_nonnegative_integer("send_join"),
        validate.value_nonnegative_integer("seqno_unchanged_const"),
        validate.value_nonnegative_integer("token"),
        validate.value_nonnegative_integer("token_coefficient"),
        validate.value_nonnegative_integer("token_retransmit"),
        validate.value_nonnegative_integer(
            "token_retransmits_before_loss_const"
        ),
        validate.value_nonnegative_integer("window_size"),
    ]
    report_items = (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(allowed_options, options.keys(), "totem")
    )
    return report_items

def create_quorum_options(options, has_qdevice):
    """
    Validate creating quorum options

    dict options -- quorum options to set
    bool has_qdevice -- is a qdevice set in corosync.conf?
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
            reports.prerequisite_option_must_be_enabled_as_well(
                "last_man_standing_window",
                "last_man_standing",
                option_type="quorum",
                prerequisite_type="quorum"
            )
        )
    return report_items

def update_quorum_options(options, has_qdevice, current_options):
    """
    Validate modifying quorum options

    dict options -- quorum options to set
    bool has_qdevice -- is a qdevice set in corosync.conf?
    dict current_options -- currently set quorum options
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
        current_options.get("last_man_standing", "0")
    )
    if (
        # Default value in corosync is 10 ms. However, that would always fail
        # the validation, so we use the default value of 0.
        options.get("last_man_standing_window", "0") != "0"
        and
        effective_lms == "0"
    ):
        report_items.append(
            reports.prerequisite_option_must_be_enabled_as_well(
                "last_man_standing_window",
                "last_man_standing",
                option_type="quorum",
                prerequisite_type="quorum"
            )
        )
    return report_items

def _validate_quorum_options(options, has_qdevice, allow_empty_values):
    validators = _get_quorum_options_validators(allow_empty_values)
    report_items = (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in( constants.QUORUM_OPTIONS, options.keys(), "quorum")
    )
    if has_qdevice:
        qdevice_incompatible_options = [
            name for name in options
            if name in constants.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
        ]
        if qdevice_incompatible_options:
            report_items.append(
                reports.corosync_options_incompatible_with_qdevice(
                    qdevice_incompatible_options
                )
            )
    return report_items

def _get_quorum_options_validators(allow_empty_values=False):
    allowed_bool = ("0", "1")
    validators = {
        "auto_tie_breaker": validate.value_in(
            "auto_tie_breaker",
            allowed_bool
        ),
        "last_man_standing": validate.value_in(
            "last_man_standing",
            allowed_bool
        ),
        "last_man_standing_window": validate.value_positive_integer(
            "last_man_standing_window"
        ),
        "wait_for_all": validate.value_in(
            "wait_for_all",
            allowed_bool
        ),
    }
    if not allow_empty_values:
        # make sure to return a list even in python3 so we can call append
        # on it
        return list(validators.values())
    return [
        validate.value_empty_or_valid(option_name, validator)
        for option_name, validator in validators.items()
    ]

def add_quorum_device(
    model, model_options, generic_options, heuristics_options, node_ids,
    force_model=False, force_options=False
):
    """
    Validate adding a quorum device

    string model -- quorum device model
    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    list node_ids -- list of existing node ids
    bool force_model -- continue even if the model is not valid
    bool force_options -- turn forceable errors into warnings
    """
    report_items = []

    model_validators = {
        "net": lambda: _qdevice_add_model_net_options(
            model_options,
            node_ids,
            force_options
        ),
    }
    if model in model_validators:
        report_items += model_validators[model]()
    else:
        report_items += validate.run_collection_of_option_validators(
            {"model": model},
            [
                validate.value_in(
                    "model",
                    list(model_validators.keys()),
                    **validate.allow_extra_values(
                        report_codes.FORCE_QDEVICE_MODEL, force_model
                    )
                )
            ]
        )
    return (
        report_items
        +
        _qdevice_add_generic_options(generic_options, force_options)
        +
        _qdevice_add_heuristics_options(heuristics_options, force_options)
    )

def update_quorum_device(
    model, model_options, generic_options, heuristics_options, node_ids,
    force_options=False
):
    """
    Validate updating a quorum device

    string model -- quorum device model
    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    list node_ids -- list of existing node ids
    bool force_options -- turn forceable errors into warnings
    """
    report_items = []

    model_validators = {
        "net": lambda: _qdevice_update_model_net_options(
            model_options,
            node_ids,
            force_options
        ),
    }
    if model in model_validators:
        report_items += model_validators[model]()
    return (
        report_items
        +
        _qdevice_update_generic_options(generic_options, force_options)
        +
        _qdevice_update_heuristics_options(
            heuristics_options,
            force_options
        )
    )

def _qdevice_add_generic_options(options, force_options=False):
    """
    Validate quorum device generic options when adding a quorum device

    dict options -- generic options
    bool force_options -- turn forceable errors into warnings
    """
    validators = _get_qdevice_generic_options_validators(
        force_options=force_options
    )
    report_items = validate.run_collection_of_option_validators(
        options,
        validators
    )
    report_items.extend(
        _validate_qdevice_generic_options_names(
            options,
            force_options=force_options
        )
    )
    return report_items

def _qdevice_update_generic_options(options, force_options=False):
    """
    Validate quorum device generic options when updating a quorum device

    dict options -- generic options
    bool force_options -- turn forceable errors into warnings
    """
    validators = _get_qdevice_generic_options_validators(
        allow_empty_values=True,
        force_options=force_options
    )
    report_items = validate.run_collection_of_option_validators(
        options,
        validators
    )
    report_items.extend(
        _validate_qdevice_generic_options_names(
            options,
            force_options=force_options
        )
    )
    return report_items

def _qdevice_add_heuristics_options(options, force_options=False):
    """
    Validate quorum device heuristics options when adding a quorum device

    dict options -- heuristics options
    bool force_options -- turn forceable errors into warnings
    """
    options_nonexec, options_exec = _split_heuristics_exec_options(options)
    validators = _get_qdevice_heuristics_options_validators(
        force_options=force_options
    )
    exec_options_reports, valid_exec_options = (
        _validate_heuristics_exec_option_names(options_exec)
    )
    for option in valid_exec_options:
        validators.append(
            validate.value_not_empty(option, "a command to be run")
        )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        _validate_heuristics_noexec_option_names(
            options_nonexec,
            force_options=force_options
        )
        +
        exec_options_reports
    )

def _qdevice_update_heuristics_options(options, force_options=False):
    """
    Validate quorum device heuristics options when updating a quorum device

    dict options -- heuristics options
    bool force_options -- turn forceable errors into warnings
    """
    options_nonexec, options_exec = _split_heuristics_exec_options(options)
    validators = _get_qdevice_heuristics_options_validators(
        allow_empty_values=True,
        force_options=force_options
    )
    # No validation necessary for values of valid exec options - they are
    # either empty (meaning they will be removed) or nonempty strings.
    exec_options_reports, dummy_valid_exec_options = (
        _validate_heuristics_exec_option_names(options_exec)
    )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        _validate_heuristics_noexec_option_names(
            options_nonexec,
            force_options=force_options
        )
        +
        exec_options_reports
    )

def _qdevice_add_model_net_options(options, node_ids, force_options=False):
    """
    Validate quorum device model options when adding a quorum device

    dict options -- model options
    list node_ids -- list of existing node ids
    bool force_options -- turn forceable errors into warnings
    """
    allowed_options = (
        _QDEVICE_NET_REQUIRED_OPTIONS + _QDEVICE_NET_OPTIONAL_OPTIONS
    )
    option_type = "quorum device model"
    validators = (
        [
            validate.is_required(option_name, option_type)
            for option_name in _QDEVICE_NET_REQUIRED_OPTIONS
        ]
        +
        _get_qdevice_model_net_options_validators(
            node_ids,
            force_options=force_options
        )
    )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            allowed_options,
            options.keys(),
            option_type,
            **validate.allow_extra_names(
                report_codes.FORCE_OPTIONS, force_options
            )
        )
    )

def _qdevice_update_model_net_options(options, node_ids, force_options=False):
    """
    Validate quorum device model options when updating a quorum device

    dict options -- model options
    list node_ids -- list of existing node ids
    bool force_options -- turn forceable errors into warnings
    """
    allowed_options = (
        _QDEVICE_NET_REQUIRED_OPTIONS + _QDEVICE_NET_OPTIONAL_OPTIONS
    )
    option_type = "quorum device model"
    validators = _get_qdevice_model_net_options_validators(
        node_ids,
        allow_empty_values=True,
        force_options=force_options
    )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            allowed_options,
            options.keys(),
            option_type,
            **validate.allow_extra_names(
                report_codes.FORCE_OPTIONS, force_options
            )
        )
    )

def _get_qdevice_generic_options_validators(
    allow_empty_values=False, force_options=False
):
    allow_extra_values = validate.allow_extra_values(
        report_codes.FORCE_OPTIONS, force_options
    )
    validators = {
        "sync_timeout": validate.value_positive_integer(
            "sync_timeout",
            **allow_extra_values
        ),
        "timeout": validate.value_positive_integer(
            "timeout",
            **allow_extra_values
        ),
    }
    if not allow_empty_values:
        # make sure to return a list even in python3 so we can call append
        # on it
        return list(validators.values())
    return [
        validate.value_empty_or_valid(option_name, validator)
        for option_name, validator in validators.items()
    ]

def _validate_qdevice_generic_options_names(options, force_options=False):
    option_type = "quorum device"
    allowed_options = [
        "sync_timeout",
        "timeout",
    ]
    report_items = []
    # In corosync.conf, generic options contain the "model" option. We treat
    # that option separately in pcs so we must not allow it to be passed in
    # generic options. That's why a standard validate.names_in cannot be used
    # in here.
    model_found = False
    invalid_options = []
    for name in options:
        if name not in allowed_options:
            if name == "model":
                model_found = True
            else:
                invalid_options.append(name)
    if model_found:
        report_items.append(
            reports.invalid_options(
                ["model"],
                allowed_options,
                option_type,
            )
        )
    if invalid_options:
        report_items.append(
            reports.invalid_options(
                invalid_options,
                allowed_options,
                option_type,
                severity=(
                    ReportItemSeverity.WARNING if force_options
                    else ReportItemSeverity.ERROR
                ),
                forceable=(
                    None if force_options else report_codes.FORCE_OPTIONS
                )
            )
        )
    return report_items

def _split_heuristics_exec_options(options):
    options_exec = dict()
    options_nonexec = dict()
    for name, value in options.items():
        if name.startswith("exec_"):
            options_exec[name] = value
        else:
            options_nonexec[name] = value
    return options_nonexec, options_exec

def _get_qdevice_heuristics_options_validators(
    allow_empty_values=False, force_options=False
):
    allow_extra_values = validate.allow_extra_values(
        report_codes.FORCE_OPTIONS, force_options
    )
    validators = {
        "mode": validate.value_in(
            "mode",
            ("off", "on", "sync"),
            **allow_extra_values
        ),
        "interval": validate.value_positive_integer(
            "interval",
            **allow_extra_values
        ),
        "sync_timeout": validate.value_positive_integer(
            "sync_timeout",
            **allow_extra_values
        ),
        "timeout": validate.value_positive_integer(
            "timeout",
            **allow_extra_values
        ),
    }
    if not allow_empty_values:
        # make sure to return a list even in python3 so we can call append
        # on it
        return list(validators.values())
    return [
        validate.value_empty_or_valid(option_name, validator)
        for option_name, validator in validators.items()
    ]

def _validate_heuristics_exec_option_names(options_exec):
    # We must be strict and do not allow to override this validation,
    # otherwise setting a cratfed exec_NAME could be misused for setting
    # arbitrary corosync.conf settings.
    regexp = constants.QUORUM_DEVICE_HEURISTICS_EXEC_NAME_RE
    report_list = []
    valid_options = []
    not_valid_options = []
    for name in options_exec:
        if regexp.match(name) is None:
            not_valid_options.append(name)
        else:
            valid_options.append(name)
    if not_valid_options:
        report_list.append(
            reports.invalid_userdefined_options(
                not_valid_options,
                "exec_NAME cannot contain '.:{}#' and whitespace characters",
                "heuristics",
                severity=ReportItemSeverity.ERROR,
                forceable=None
            )
        )
    return report_list, valid_options

def _validate_heuristics_noexec_option_names(
    options_nonexec, force_options=False
):
    allowed_options = [
        "interval",
        "mode",
        "sync_timeout",
        "timeout",
    ]
    return validate.names_in(
        allowed_options,
        options_nonexec.keys(),
        "heuristics",
        report_codes.FORCE_OPTIONS,
        allow_extra_names=force_options,
        allowed_option_patterns=["exec_NAME"]
    )

def _get_qdevice_model_net_options_validators(
    node_ids, allow_empty_values=False, force_options=False
):
    allow_extra_values = validate.allow_extra_values(
        report_codes.FORCE_OPTIONS, force_options
    )
    validators = {
        "connect_timeout": validate.value_integer_in_range(
            "connect_timeout",
            1000,
            2*60*1000,
            **allow_extra_values
        ),
        "force_ip_version": validate.value_in(
            "force_ip_version",
            ("0", "4", "6"),
            **allow_extra_values
        ),
        "port": validate.value_port_number(
            "port",
            **allow_extra_values
        ),
        "tie_breaker": validate.value_in(
            "tie_breaker",
            ["lowest", "highest"] + node_ids,
            **allow_extra_values
        ),
    }
    if not allow_empty_values:
        return (
            [
                validate.value_not_empty("host", "a qdevice host address"),
                _validate_qdevice_net_algorithm(**allow_extra_values)
            ]
            +
            # explicitely convert to a list for python 3
            list(validators.values())
        )
    return (
        [
            validate.value_not_empty("host", "a qdevice host address"),
            _validate_qdevice_net_algorithm(**allow_extra_values)
        ]
        +
        [
            validate.value_empty_or_valid(option_name, validator)
            for option_name, validator in validators.items()
        ]
    )

def _validate_qdevice_net_algorithm(
    code_to_allow_extra_values=None, allow_extra_values=False
):
    @validate._if_option_exists("algorithm")
    def validate_func(option_dict):
        allowed_algorithms = (
            "ffsplit",
            "lms",
        )
        value = validate.ValuePair.get(option_dict["algorithm"])
        if validate.is_empty_string(value.normalized):
            return [
                reports.invalid_option_value(
                    "algorithm",
                    value.original,
                    allowed_algorithms
                )
            ]
        return validate.value_in(
            "algorithm",
            allowed_algorithms,
            code_to_allow_extra_values=code_to_allow_extra_values,
            allow_extra_values=allow_extra_values
        )(option_dict)
    return validate_func
