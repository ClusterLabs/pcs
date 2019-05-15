# pylint: disable=too-many-lines
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


def create(
    cluster_name, node_list, transport, ip_version, force_unresolvable=False
):
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    """
    Validate creating a new minimalistic corosync.conf

    string cluster_name -- the name of the new cluster
    list node_list -- nodes of the new cluster; dict: name, addrs
    string transport -- corosync transport used in the new cluster
    string ip_version -- which IP family node addresses should be
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
    nodes_with_empty_addr = set()
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
        if transport in constants.TRANSPORTS_KNET + constants.TRANSPORTS_UDP:
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
        for link_index, addr in enumerate(node.get("addrs") or []):
            if addr == "":
                if node.get("name"):
                    # No way to report name if none is set. Unnamed nodes cause
                    # errors anyway.
                    nodes_with_empty_addr.add(node.get("name"))
                continue
            all_addrs_count[addr] += 1
            _validate_addr_type(
                addr, link_index, ip_version, get_addr_type,
                # these will get populated in the function
                addr_types, unresolvable_addresses, report_items
            )
        addr_types_per_node.append(addr_types)
    # Report all unresolvable addresses at once instead on each own.
    # Report all empty and unresolvable addresses at once instead on each own.
    if nodes_with_empty_addr:
        report_items.append(
            reports.node_addresses_cannot_be_empty(nodes_with_empty_addr)
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )

    # Reporting single-node errors finished.
    # Now report nodelist and inter-node errors.
    if not node_list:
        report_items.append(reports.corosync_nodes_missing())
    non_unique_names = {
        name for name, count in all_names_count.items() if count > 1
    }
    if non_unique_names:
        all_names_usable = False
        report_items.append(
            reports.node_names_duplication(non_unique_names)
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

def _extract_existing_addrs_and_names(
    coro_existing_nodes, pcmk_existing_nodes, pcmk_names=True
):
    existing_names = set()
    existing_addrs = set()
    existing_addr_types_dict = dict()
    for node in coro_existing_nodes:
        existing_names.add(node.name)
        existing_addrs.update(set(node.addrs_plain()))
        for addr in node.addrs:
            # If two nodes have FQDN and one has IPv4, we want to keep the IPv4
            if (
                addr.type not in (ADDR_FQDN, ADDR_UNRESOLVABLE)
                or
                addr.link not in existing_addr_types_dict
            ):
                existing_addr_types_dict[addr.link] = addr.type
    for node in pcmk_existing_nodes:
        if pcmk_names:
            existing_names.add(node.name)
        existing_addrs.add(node.addr)
    return existing_addrs, existing_addr_types_dict, existing_names

def _validate_addr_type(
    addr, link_index, ip_version, get_addr_type,
    # these will get populated in the function
    addr_types, unresolvable_addresses, report_items
):
    addr_types.append(get_addr_type(addr))
    if get_addr_type(addr) == ADDR_UNRESOLVABLE:
        unresolvable_addresses.add(addr)
    elif (
        get_addr_type(addr) == ADDR_IPV4
        and
        ip_version == constants.IP_VERSION_6
    ):
        report_items.append(
            reports.corosync_address_ip_version_wrong_for_link(
                addr, ADDR_IPV6, link_number=link_index
            )
        )
    elif (
        get_addr_type(addr) == ADDR_IPV6
        and
        ip_version == constants.IP_VERSION_4
    ):
        report_items.append(
            reports.corosync_address_ip_version_wrong_for_link(
                addr, ADDR_IPV4, link_number=link_index
            )
        )

def _report_unresolvable_addresses_if_any(
    unresolvable_addresses, force_unresolvable
):
    if not unresolvable_addresses:
        return []
    return [
        reports.get_problem_creator(
            force_code=report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
            is_forced=force_unresolvable,
        )(
            reports.node_addresses_unresolvable,
            unresolvable_addresses,
        )
    ]

def add_nodes(
    node_list, coro_existing_nodes, pcmk_existing_nodes,
    force_unresolvable=False
):
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """
    Validate adding nodes to a config with a nonempty nodelist

    list node_list -- new nodes data; list of dict: name, addrs
    list coro_existing_nodes -- existing corosync nodes; list of CorosyncNode
    list pcmk_existing_nodes -- existing pacemaker nodes; list of PacemakerNode
    bool force_unresolvable -- if True, report unresolvable addresses as
        warnings instead of errors
    """
    # extract info from existing nodes
    existing_addrs, existing_addr_types_dict, existing_names = (
        _extract_existing_addrs_and_names(
            coro_existing_nodes, pcmk_existing_nodes
        )
    )
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
    nodes_with_empty_addr = set()

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
            if addr == "":
                if node.get("name"):
                    # No way to report name if none is set. Unnamed nodes cause
                    # errors anyway.
                    nodes_with_empty_addr.add(node.get("name"))
                continue
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
    # Report all empty and unresolvable addresses at once instead on each own.
    if nodes_with_empty_addr:
        report_items.append(
            reports.node_addresses_cannot_be_empty(nodes_with_empty_addr)
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )

    # Reporting single-node errors finished.
    # Now report nodelist and inter-node errors.
    if not node_list:
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
    non_unique_names = {
        name for name, count in new_names_count.items() if count > 1
    }
    if non_unique_names:
        report_items.append(
            reports.node_names_duplication(non_unique_names)
        )
    non_unique_addrs = {
        addr for addr, count in new_addrs_count.items() if count > 1
    }
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

    if not set(existing_node_names) - set(nodes_names_to_remove):
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

def _check_link_options_count(link_count, max_allowed_link_count):
    report_items = []
    # make sure we don't report negative counts
    link_count = max(link_count, 0)
    max_allowed_link_count = max(max_allowed_link_count, 0)
    if link_count > max_allowed_link_count:
        # link_count < max_allowed_link_count is a valid scenario - for some
        # links no options have been specified
        report_items.append(
            reports.corosync_too_many_links_options(
                link_count, max_allowed_link_count
            )
        )
    return report_items

def _get_link_options_validators_udp(allow_empty_values=False):
    # This only returns validators checking single values. Add checks for
    # intervalues relationships as needed.
    validators = {
        "bindnetaddr": validate.value_ip_address("bindnetaddr"),
        "broadcast": validate.value_in("broadcast", ("0", "1")),
        "mcastaddr": validate.value_ip_address("mcastaddr"),
        "mcastport": validate.value_port_number("mcastport"),
        "ttl": validate.value_integer_in_range("ttl", 0, 255),
    }
    return validate.wrap_with_empty_or_valid(
        validators,
        wrap=allow_empty_values
    )

def _update_link_options_udp(new_options, current_options):
    allowed_options = constants.LINK_OPTIONS_UDP
    validators = _get_link_options_validators_udp(allow_empty_values=True)
    report_items = (
        validate.run_collection_of_option_validators(
            new_options, validators
        )
        +
        validate.names_in(allowed_options, new_options.keys(), "link")
    )

    # default values taken from `man corosync.conf`
    target_broadcast = _get_option_after_update(
        new_options, current_options, "broadcast", "0"
    )
    target_mcastaddr = _get_option_after_update(
        new_options, current_options, "mcastaddr", None
    )
    if target_broadcast == "1" and target_mcastaddr is not None:
        report_items.append(
            reports.prerequisite_option_must_be_disabled(
                "mcastaddr",
                "broadcast",
                option_type="link",
                prerequisite_type="link"
            )
        )

    return report_items

def create_link_list_udp(link_list, max_allowed_link_count):
    """
    Validate creating udp/udpu link (interface) list options

    iterable link_list -- list of link options
    integer max_allowed_link_count -- how many links is defined by addresses
    """
    if not link_list:
        # It is not mandatory to set link options. If an empty link list is
        # provided, everything is fine and we have nothing to validate.
        return []

    allowed_options = constants.LINK_OPTIONS_UDP
    validators = _get_link_options_validators_udp()
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
    report_items.extend(
        _check_link_options_count(len(link_list), max_allowed_link_count)
    )
    return report_items

def create_link_list_knet(link_list, max_allowed_link_count):
    """
    Validate creating knet link (interface) list options

    iterable link_list -- list of link options
    integer max_allowed_link_count -- how many links is defined by addresses
    """
    if not link_list:
        # It is not mandatory to set link options. If an empty link list is
        # provided, everything is fine and we have nothing to validate. It is
        # also possible to set link options for only some of the links.
        return []

    report_items = []
    used_link_number = defaultdict(int)
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
                        reports.corosync_link_does_not_exist_cannot_update(
                            options["linknumber"],
                            link_count=max_allowed_link_count
                        )
                    )
        report_items += _add_link_options_knet(options)
    non_unique_linknumbers = [
        number for number, count in used_link_number.items() if count > 1
    ]
    if non_unique_linknumbers:
        report_items.append(
            reports.corosync_link_number_duplication(non_unique_linknumbers)
        )
    report_items.extend(
        _check_link_options_count(len(link_list), max_allowed_link_count)
    )
    return report_items

def _get_link_options_validators_knet(
    allow_empty_values=False, including_linknumber=True
):
    # This only returns validators checking single values. Add checks for
    # intervalues relationships as needed.
    validators = {
        "link_priority": validate.value_integer_in_range(
            "link_priority", 0, 255
        ),
        "mcastport": validate.value_port_number("mcastport"),
        "ping_interval": validate.value_nonnegative_integer("ping_interval"),
        "ping_precision": validate.value_nonnegative_integer("ping_precision"),
        "ping_timeout": validate.value_nonnegative_integer("ping_timeout"),
        "pong_count": validate.value_nonnegative_integer("pong_count"),
        "transport": validate.value_in("transport", ("sctp", "udp")),
    }
    if including_linknumber:
        validators["linknumber"] = validate.value_integer_in_range(
            "linknumber",
            0,
            constants.LINKS_KNET_MAX - 1
        )
    return validate.wrap_with_empty_or_valid(
        validators,
        wrap=allow_empty_values
    )

def _get_link_options_validators_knet_relations():
    return [
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
    ]

def _add_link_options_knet(options):
    allowed_options = constants.LINK_OPTIONS_KNET_USER
    validators = _get_link_options_validators_knet()
    validators += _get_link_options_validators_knet_relations()
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(allowed_options, options.keys(), "link")
    )

def _update_link_options_knet(new_options, current_options):
    # Changing linknumber is not allowed in update. It would effectivelly
    # delete one link and add a new one. Link update is meant for the cases
    # when there is only one link which cannot be removed and another one
    # cannot be added.
    allowed_options = [
        option for option in constants.LINK_OPTIONS_KNET_USER
        if option != "linknumber"
    ]
    validators = _get_link_options_validators_knet(
        allow_empty_values=True, including_linknumber=False
    )
    validators_relations = _get_link_options_validators_knet_relations()

    # check dependencies in resulting options
    after_update = {}
    for option_name in ("ping_interval", "ping_timeout"):
        option_value = _get_option_after_update(
            new_options, current_options, option_name, None
        )
        if option_value is not None:
            after_update[option_name] = option_value

    return (
        validate.run_collection_of_option_validators(new_options, validators)
        +
        validate.run_collection_of_option_validators(
            after_update, validators_relations
        )
        +
        validate.names_in(allowed_options, new_options.keys(), "link")
    )

def add_link(
    node_addr_map, link_options,
    coro_existing_nodes, pcmk_existing_nodes, linknumbers_existing, transport,
    ip_version,
    force_unresolvable=False
):
    # pylint: disable=too-many-locals
    """
    Validate adding a link

    dict node_addr_map -- key: node name, value: node address for the new link
    dict link_options -- link options
    list coro_existing_nodes -- existing corosync nodes; list of CorosyncNode
    list pcmk_existing_nodes -- existing pacemaker nodes; list of PacemakerNode
    iterable linknumbers_existing -- all currently existing links (linknumbers)
    string transport -- corosync transport used in the cluster
    string ip_version -- ip family defined to be used in the cluster
    bool force_unresolvable -- if True, report unresolvable addresses as
        warnings instead of errors
    """
    report_items = []
    # We only support adding one link (that's the "1"), this may change later.
    number_of_links_to_add = 1

    # Check the transport supports adding links
    if transport not in constants.TRANSPORTS_KNET:
        report_items.append(
            reports.corosync_cannot_add_remove_links_bad_transport(
                transport,
                constants.TRANSPORTS_KNET,
                add_or_not_remove=True,
            )
        )
        return report_items

    # Check the allowed number of links is not exceeded
    if (
        len(linknumbers_existing) + number_of_links_to_add
        >
        constants.LINKS_KNET_MAX
    ):
        report_items.append(
            reports.corosync_cannot_add_remove_links_too_many_few_links(
                number_of_links_to_add,
                len(linknumbers_existing) + number_of_links_to_add,
                constants.LINKS_KNET_MAX,
                add_or_not_remove=True,
            )
        )
        # Since only one link can be added there is no point in validating the
        # link if it cannot be added. If it was possible to add more links at
        # once, it would make sense to continue walidating them (e.g. adding 4
        # links to a cluster with 5 links where max number of links is 8).
        return report_items

    # Check all nodes have their addresses specified
    existing_addrs, dummy_existing_addr_types_dict, existing_names = (
        _extract_existing_addrs_and_names(
            coro_existing_nodes, pcmk_existing_nodes, pcmk_names=False
        )
    )
    report_items += [
        reports.corosync_bad_node_addresses_count(
            actual_count=0,
            min_count=number_of_links_to_add,
            max_count=number_of_links_to_add,
            node_name=node
        )
        for node in sorted(existing_names - set(node_addr_map.keys()))
    ]
    report_items += [
        reports.node_not_found(node)
        for node in sorted(set(node_addr_map.keys()) - existing_names)
    ]

    get_addr_type = _addr_type_analyzer()
    unresolvable_addresses = set()
    nodes_with_empty_addr = set()
    addr_types = []
    for node_name, node_addr in node_addr_map.items():
        if node_addr == "":
            nodes_with_empty_addr.add(node_name)
        else:
            _validate_addr_type(
                node_addr, None, ip_version, get_addr_type,
                # these will get appended in the function
                addr_types, unresolvable_addresses, report_items
            )
    if nodes_with_empty_addr:
        report_items.append(
            reports.node_addresses_cannot_be_empty(nodes_with_empty_addr)
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )

    # Check mixing IPv4 and IPv6 in the link
    if ADDR_IPV4 in addr_types and ADDR_IPV6 in addr_types:
        report_items.append(reports.corosync_ip_version_mismatch_in_links())

    # Check addresses are unique
    report_items += _report_non_unique_addresses(
        existing_addrs,
        node_addr_map.values()
    )

    # Check link options
    report_items += _add_link_options_knet(link_options)
    if "linknumber" in link_options:
        if link_options["linknumber"] in linknumbers_existing:
            report_items.append(
                reports.corosync_link_already_exists_cannot_add(
                    link_options["linknumber"]
                )
            )

    return report_items

def remove_links(linknumbers_to_remove, linknumbers_existing, transport):
    """
    Validate removing links

    iterable linknumbers_to_remove -- links to be removed (linknumbers strings)
    iterable linknumbers_existing -- all existing linknumbers (strings)
    string transport -- corosync transport used in the cluster
    """
    report_items = []

    if transport not in constants.TRANSPORTS_KNET:
        report_items.append(
            reports.corosync_cannot_add_remove_links_bad_transport(
                transport,
                constants.TRANSPORTS_KNET,
                add_or_not_remove=False,
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
            reports.corosync_link_number_duplication(to_remove_duplicates)
        )

    to_remove = frozenset(linknumbers_to_remove)
    existing = frozenset(linknumbers_existing)
    left = existing - to_remove
    nonexistent = to_remove - existing

    if not to_remove:
        report_items.append(
            reports.corosync_cannot_add_remove_links_no_links_specified(
                add_or_not_remove=False,
            )
        )
    if len(left) < constants.LINKS_KNET_MIN:
        report_items.append(
            reports.corosync_cannot_add_remove_links_too_many_few_links(
                # only existing links can be removed, do not count nonexistent
                # ones
                len(to_remove & existing),
                len(left),
                constants.LINKS_KNET_MIN,
                add_or_not_remove=False,
            )
        )
    if nonexistent:
        report_items.append(
            reports.corosync_link_does_not_exist_cannot_remove(
                nonexistent,
                existing
            )
        )

    return report_items

def update_link(
    linknumber, node_addr_map, link_options,
    current_link_options, coro_existing_nodes, pcmk_existing_nodes,
    linknumbers_existing, transport, ip_version,
    force_unresolvable=False
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    """
    Validate changing an existing link

    string linknumber -- the link to be changed
    dict node_addr_map -- key: node name, value: node address for the new link
    dict link_options -- link options
    dict current_link_options -- current options of the link to be changed
    list coro_existing_nodes -- existing corosync nodes; list of CorosyncNode
    list pcmk_existing_nodes -- existing pacemaker nodes; list of PacemakerNode
    iterable linknumbers_existing -- all currently existing links (linknumbers)
    string transport -- corosync transport used in the cluster
    string ip_version -- ip family defined to be used in the cluster
    bool force_unresolvable -- if True, report unresolvable addresses as
        warnings instead of errors
    """
    report_items = []
    # check the link exists
    if linknumber not in linknumbers_existing:
        # All other validations work with what is set for the existing link. If
        # the linknumber is wrong, there is no point in returning possibly
        # misleading errors.
        return [
            reports.corosync_link_does_not_exist_cannot_update(
                linknumber, existing_link_list=linknumbers_existing
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
    for node in coro_existing_nodes:
        existing_names.add(node.name)
        if node.name in node_addr_map:
            link_addr_types.append(get_addr_type(node_addr_map[node.name]))
            unchanged_addrs |= set(node.addrs_plain(except_link=linknumber))
        else:
            addr = node.addr_plain_for_link(linknumber)
            if addr:
                link_addr_types.append(get_addr_type(addr))
            unchanged_addrs |= set(node.addrs_plain())
    for node in pcmk_existing_nodes:
        unchanged_addrs.add(node.addr)
    # report unknown nodes
    report_items += [
        reports.node_not_found(node)
        for node in sorted(set(node_addr_map.keys()) - existing_names)
    ]
    # validate new addresses
    unresolvable_addresses = set()
    nodes_with_empty_addr = set()
    dummy_addr_types = []
    for node_name, node_addr in node_addr_map.items():
        if node_addr == "":
            nodes_with_empty_addr.add(node_name)
        else:
            _validate_addr_type(
                node_addr, linknumber, ip_version, get_addr_type,
                # these will get appended in the function
                dummy_addr_types, unresolvable_addresses, report_items
            )
    if nodes_with_empty_addr:
        report_items.append(
            reports.node_addresses_cannot_be_empty(nodes_with_empty_addr)
        )
    report_items += _report_unresolvable_addresses_if_any(
        unresolvable_addresses, force_unresolvable
    )
    # Check mixing IPv4 and IPv6 in the link - get addresses after update
    if ADDR_IPV4 in link_addr_types and ADDR_IPV6 in link_addr_types:
        report_items.append(reports.corosync_ip_version_mismatch_in_links())
    # Check address are unique. If new addresses are unique and no new address
    # already exists in the set of addresses not changed by the update, then
    # the new addresses are unique.
    report_items += _report_non_unique_addresses(
        unchanged_addrs,
        node_addr_map.values()
    )

    return report_items

def _report_non_unique_addresses(existing_addrs, new_addrs):
    report_items = []

    already_existing_addrs = existing_addrs.intersection(new_addrs)
    if already_existing_addrs:
        report_items.append(
            reports.node_addresses_already_exist(already_existing_addrs)
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
            reports.node_addresses_duplication(non_unique_addrs)
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
    # * values are either an enum or numbers with no range set - nothing to
    #   force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    allowed_options = [
        "ip_version",
        "netmtu",
    ]
    validators = [
        validate.value_in("ip_version", constants.IP_VERSION_VALUES),
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
    # * values are either an enum or numbers with no range set - nothing to
    #   force
    # * names are strictly set as we cannot risk the user overwrites some
    #   setting they should not to
    # * changes to names and values in corosync are very rare
    generic_allowed = [
        "ip_version", # It tells knet which IP to prefer.
        "knet_pmtud_interval",
        "link_mode",
    ]
    generic_validators = [
        validate.value_in("ip_version", constants.IP_VERSION_VALUES),
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
            ("none", "aes256", "aes192", "aes128")
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
        crypto_options.get("cipher", "none") != "none"
        and
        crypto_options.get("hash", "none") == "none"
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
        validate.names_in(constants.QUORUM_OPTIONS, options.keys(), "quorum")
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
    return validate.wrap_with_empty_or_valid(
        validators,
        wrap=allow_empty_values
    )

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
    return validate.wrap_with_empty_or_valid(
        validators,
        wrap=allow_empty_values
    )

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
    return validate.wrap_with_empty_or_valid(
        validators,
        wrap=allow_empty_values
    )

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
        extra_names_allowed=force_options,
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
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # pylint: disable=protected-access
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
            extra_values_allowed=extra_values_allowed
        )(option_dict)
    return validate_func

def _get_option_after_update(
    new_options, current_options, option_name, default_value
):
    if option_name in new_options:
        if new_options[option_name] == "":
            return default_value
        return new_options[option_name]
    return current_options.get(option_name, default_value)
