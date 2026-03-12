from typing import Any, Mapping, Optional, Sequence

from pcs import settings
from pcs.common import reports, ssl
from pcs.lib import node_communication_format
from pcs.lib.commands.cluster.common import (
    ensure_live_env,
    get_validated_wait_timeout,
    is_ssl_cert_sync_enabled,
    start_cluster,
    verify_corosync_conf,
)
from pcs.lib.commands.cluster.node_provisioning import (
    get_addrs_defaulter,
    host_check_cluster_setup,
    normalize_dict,
    set_defaults_in_dict,
)
from pcs.lib.communication import cluster
from pcs.lib.communication.nodes import (
    DistributeFilesWithoutForces,
    EnableCluster,
    GetHostInfo,
    RemoveFilesWithoutForces,
    SendPcsdSslCertAndKey,
    UpdateKnownHosts,
)
from pcs.lib.communication.tools import AllSameDataMixin, run_and_raise
from pcs.lib.communication.tools import run as run_com
from pcs.lib.corosync import config_facade, config_validators
from pcs.lib.corosync import constants as corosync_constants
from pcs.lib.env import LibraryEnvironment, WaitType
from pcs.lib.errors import LibraryError
from pcs.lib.tools import generate_binary_key, generate_uuid


def setup(  # noqa:  PLR0913, PLR0915
    env: LibraryEnvironment,
    cluster_name: str,
    nodes: Sequence[Mapping[str, Any]],
    transport_type: Optional[str] = None,
    transport_options: Optional[Mapping[str, str]] = None,
    link_list: Optional[Sequence[Mapping[str, str]]] = None,
    compression_options: Optional[Mapping[str, str]] = None,
    crypto_options: Optional[Mapping[str, str]] = None,
    totem_options: Optional[Mapping[str, str]] = None,
    quorum_options: Optional[Mapping[str, str]] = None,
    wait: WaitType = False,
    start: bool = False,
    enable: bool = False,
    no_keys_sync: bool = False,
    no_cluster_uuid: bool = False,
    force_flags: reports.types.ForceFlags = (),
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Set up cluster on specified nodes.
    Validation of the inputs is done here. Possible existing clusters are
    destroyed (when using force). Authkey files for corosync and pacemaker,
    known hosts and newly generated corosync.conf are distributed to all
    nodes.
    Raise LibraryError on any error.

    env
    cluster_name -- name of a cluster to set up
    nodes -- list of dicts which represents node.
        Supported keys are: name (required), addrs. See note below.
    transport_type -- transport type of a cluster
    transport_options -- transport specific options
    link_list -- list of links, depends of transport_type
    compression_options -- only available for knet transport. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options -- only available for knet transport'. In corosync.conf
        they are prefixed 'crypto_'
    totem_options -- options of section 'totem' in corosync.conf
    quorum_options -- options of section 'quorum' in corosync.conf
    wait -- specifies if command should try to wait for cluster to start up.
        Has no effect start is False. If set to False command will not wait for
        cluster to start. If None command will wait for some default timeout.
        If int wait set timeout to int value of seconds.
    start -- if True start cluster when it is set up
    enable -- if True enable cluster when it is set up
    no_keys_sync -- if True do not create and distribute files: pcsd ssl
        cert and key, pacemaker authkey, corosync authkey
    no_cluster_uuid -- if True, do not generate a unique cluster UUID into
        the 'totem' section of corosync.conf
    force_flags -- list of flags codes

    The command is defaulting node addresses if they are not specified. The
    defaulting is done for each node individually if and only if the "addrs" key
    is not present for the node. If the "addrs" key is present and holds an
    empty list, no defaulting is done.
    This will default addresses for node2 and won't modify addresses for other
    nodes (no addresses will be defined for node3):
    nodes=[
        {"name": "node1", "addrs": ["node1-addr"]},
        {"name": "node2"},
        {"name": "node3", "addrs": []},
    ]
    """
    ensure_live_env(env)  # raises if env is not live
    force = reports.codes.FORCE in force_flags

    transport_type = transport_type or "knet"
    transport_options = transport_options or {}
    link_list = link_list or []
    compression_options = compression_options or {}
    crypto_options = crypto_options or {}
    totem_options = totem_options or {}
    quorum_options = quorum_options or {}
    nodes = [normalize_dict(node, {"addrs"}) for node in nodes]
    if (
        transport_type in corosync_constants.TRANSPORTS_KNET
        and not crypto_options
    ):
        crypto_options = {
            "cipher": "aes256",
            "hash": "sha256",
        }

    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()

    # Get targets for all nodes and report unknown (== not-authorized) nodes.
    # If a node doesn't contain the 'name' key, validation of inputs reports it.
    # That means we don't report missing names but cannot rely on them being
    # present either.
    (
        target_report_list,
        target_list,
    ) = target_factory.get_target_list_with_reports(
        [node["name"] for node in nodes if "name" in node],
        allow_skip=False,
    )
    report_processor.report_list(target_report_list)

    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole cluster setup command / form significantly.
    addrs_defaulter = get_addrs_defaulter(
        report_processor, {target.label: target for target in target_list}
    )
    nodes = [
        set_defaults_in_dict(node, {"addrs": addrs_defaulter}) for node in nodes
    ]

    # Validate inputs.
    report_processor.report_list(
        _validate_create_corosync_conf(
            cluster_name,
            nodes,
            transport_type,
            transport_options,
            link_list,
            compression_options,
            crypto_options,
            totem_options,
            quorum_options,
            force,
        )
    )

    # Validate flags
    wait_timeout = get_validated_wait_timeout(report_processor, wait, start)

    # Validate the nodes
    com_cmd: AllSameDataMixin = GetHostInfo(report_processor)
    com_cmd.set_targets(target_list)
    report_processor.report_list(
        host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd), force
        )
    )

    # If there is an error reading the file, this will report it and exit
    # safely before any change is made to the nodes.
    sync_ssl_certs = is_ssl_cert_sync_enabled(report_processor)

    if report_processor.has_errors:
        raise LibraryError()

    # Validation done. If errors occurred, an exception has been raised and we
    # don't get below this line.

    # Destroy cluster on all nodes.
    com_cmd = cluster.Destroy(env.report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute auth tokens.
    com_cmd = UpdateKnownHosts(
        env.report_processor,
        known_hosts_to_add=env.get_known_hosts(
            [target.label for target in target_list]
        ),
        known_hosts_to_remove=[],
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # TODO This should be in the file distribution call but so far we don't
    # have a call which allows to save and delete files at the same time.
    com_cmd = RemoveFilesWithoutForces(
        env.report_processor,
        {"pcsd settings": {"type": "pcsd_settings"}},
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    if not no_keys_sync:
        # Distribute configuration files except corosync.conf. Sending
        # corosync.conf serves as a "commit" as its presence on a node marks the
        # node as a part of a cluster.
        corosync_authkey = generate_binary_key(
            random_bytes_count=settings.corosync_authkey_bytes
        )
        pcmk_authkey = generate_binary_key(
            random_bytes_count=settings.pacemaker_authkey_bytes
        )
        actions = {}
        actions.update(
            node_communication_format.corosync_authkey_file(corosync_authkey)
        )
        actions.update(
            node_communication_format.pcmk_authkey_file(pcmk_authkey)
        )
        com_cmd = DistributeFilesWithoutForces(env.report_processor, actions)
        com_cmd.set_targets(target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

        # Distribute and reload pcsd SSL certificate
        if sync_ssl_certs:
            report_processor.report(
                reports.ReportItem.info(
                    reports.messages.PcsdSslCertAndKeyDistributionStarted(
                        sorted([target.label for target in target_list])
                    )
                )
            )
            # Local certificate and key cannot be used because the local node
            # may not be a part of the new cluster at all.
            ssl_key_raw = ssl.generate_key()
            ssl_key = ssl.dump_key(ssl_key_raw)
            ssl_cert = ssl.dump_cert(
                ssl.generate_cert(ssl_key_raw, target_list[0].label)
            )
            com_cmd = SendPcsdSslCertAndKey(
                env.report_processor, ssl_cert, ssl_key
            )
            com_cmd.set_targets(target_list)
            run_and_raise(env.get_node_communicator(), com_cmd)

    # Create and distribute corosync.conf. Once a node saves corosync.conf it
    # is considered to be in a cluster.
    # raises if corosync not valid
    com_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.corosync_conf_file(
            _create_corosync_conf(
                cluster_name,
                nodes,
                transport_type,
                transport_options,
                link_list,
                compression_options,
                crypto_options,
                totem_options,
                quorum_options,
                no_cluster_uuid,
            ).config.export()
        ),
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    if env.report_processor.report(
        reports.ReportItem.info(reports.messages.ClusterSetupSuccess())
    ).has_errors:
        raise LibraryError()

    # Optionally enable and start cluster services.
    if enable:
        com_cmd = EnableCluster(env.report_processor)
        com_cmd.set_targets(target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    if start:
        start_cluster(
            env.communicator_factory,
            env.report_processor,
            target_list,
            wait_timeout=wait_timeout,
        )


def setup_local(  # noqa: PLR0913
    env: LibraryEnvironment,
    cluster_name: str,
    nodes: Sequence[Mapping[str, Any]],
    transport_type: Optional[str],
    transport_options: Mapping[str, str],
    link_list: Sequence[Mapping[str, str]],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
    quorum_options: Mapping[str, str],
    no_cluster_uuid: bool = False,
    force_flags: reports.types.ForceFlags = (),
) -> bytes:
    """
    Return corosync.conf text based on specified parameters.
    Raise LibraryError on any error.

    env
    cluster_name -- name of a cluster to set up
    nodes list -- list of dicts which represents node.
        Supported keys are: name (required), addrs. See note bellow.
    transport_type -- transport type of a cluster
    transport_options -- transport specific options
    link_list -- list of links, depends of transport_type
    compression_options -- only available for knet transport. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options -- only available for knet transport'. In corosync.conf
        they are prefixed 'crypto_'
    totem_options -- options of section 'totem' in corosync.conf
    quorum_options -- options of section 'quorum' in corosync.conf
    no_cluster_uuid -- if True, do not generate a unique cluster UUID into
        the totem section of corosync.conf
    force_flags -- list of flags codes

    The command is defaulting node addresses if they are not specified. The
    defaulting is done for each node individually if and only if the "addrs" key
    is not present for the node. If the "addrs" key is present and holds an
    empty list, no defaulting is done.
    This will default addresses for node2 and won't modify addresses for other
    nodes (no addresses will be defined for node3):
    nodes=[
        {"name": "node1", "addrs": ["node1-addr"]},
        {"name": "node2"},
        {"name": "node3", "addrs": []},
    ]
    """
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-positional-arguments
    force = reports.codes.FORCE in force_flags

    transport_type = transport_type or "knet"
    nodes = [normalize_dict(node, {"addrs"}) for node in nodes]
    if (
        transport_type in corosync_constants.TRANSPORTS_KNET
        and not crypto_options
    ):
        crypto_options = {
            "cipher": "aes256",
            "hash": "sha256",
        }

    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()

    # Get targets just for address defaulting, no need to report unknown nodes
    _, target_list = target_factory.get_target_list_with_reports(
        [node["name"] for node in nodes if "name" in node],
        allow_skip=False,
    )

    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole cluster setup command / form significantly.

    # If there is no address for a node in known-hosts, use its name as the
    # default address
    addrs_defaulter = get_addrs_defaulter(
        report_processor,
        {target.label: target for target in target_list},
        default_to_name_if_no_target=True,
    )
    nodes = [
        set_defaults_in_dict(node, {"addrs": addrs_defaulter}) for node in nodes
    ]

    # Validate inputs.
    if report_processor.report_list(
        _validate_create_corosync_conf(
            cluster_name,
            nodes,
            transport_type,
            transport_options,
            link_list,
            compression_options,
            crypto_options,
            totem_options,
            quorum_options,
            force,
        )
    ).has_errors:
        raise LibraryError()

    # Validation done. If errors occurred, an exception has been raised and we
    # don't get below this line.

    return (
        _create_corosync_conf(
            cluster_name,
            nodes,
            transport_type,
            transport_options,
            link_list,
            compression_options,
            crypto_options,
            totem_options,
            quorum_options,
            no_cluster_uuid,
        )
        .config.export()
        .encode("utf-8")
    )


def _validate_create_corosync_conf(  # noqa: PLR0913
    cluster_name: str,
    nodes: Sequence[Mapping[str, Any]],
    transport_type: str,
    transport_options: Mapping[str, str],
    link_list: Sequence[Mapping[str, str]],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
    quorum_options: Mapping[str, str],
    force: bool,
) -> reports.ReportItemList:
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments

    # Get IP version for node addresses validation. Defaults taken from man
    # corosync.conf
    ip_version = (
        corosync_constants.IP_VERSION_4
        if transport_type == "udp"
        else corosync_constants.IP_VERSION_64
    )
    if (
        transport_options.get("ip_version")
        in corosync_constants.IP_VERSION_VALUES
    ):
        ip_version = transport_options["ip_version"]

    report_list = []
    report_list += config_validators.create(
        cluster_name,
        nodes,
        transport_type,
        ip_version,
        force_unresolvable=force,
        force_cluster_name=force,
    )
    max_node_addr_count = max((len(node["addrs"]) for node in nodes), default=0)
    if transport_type in corosync_constants.TRANSPORTS_KNET:
        report_list += config_validators.create_transport_knet(
            transport_options, compression_options, crypto_options
        )
        report_list += config_validators.create_link_list_knet(
            link_list, max_node_addr_count
        )

    elif transport_type in corosync_constants.TRANSPORTS_UDP:
        report_list += config_validators.create_transport_udp(
            transport_options, compression_options, crypto_options
        )
        report_list += config_validators.create_link_list_udp(
            link_list, max_node_addr_count
        )
    return (
        report_list
        + config_validators.create_totem(totem_options)
        # We are creating the config and we know there is no qdevice in it.
        + config_validators.create_quorum_options(quorum_options, False)
    )


def _create_corosync_conf(  # noqa: PLR0913
    cluster_name: str,
    nodes: Sequence[Mapping[str, Any]],
    transport_type: str,
    transport_options: Mapping[str, str],
    link_list: Sequence[Mapping[str, str]],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
    quorum_options: Mapping[str, str],
    no_cluster_uuid: bool,
) -> config_facade.ConfigFacade:
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    corosync_conf = config_facade.ConfigFacade.create(
        cluster_name, nodes, transport_type
    )
    corosync_conf.set_totem_options(totem_options)
    corosync_conf.set_quorum_options(quorum_options)
    corosync_conf.create_link_list(link_list)
    corosync_conf.set_transport_options(
        transport_options,
        compression_options,
        crypto_options,
    )
    if not no_cluster_uuid:
        corosync_conf.set_cluster_uuid(generate_uuid())

    verify_corosync_conf(corosync_conf)  # raises if corosync not valid
    return corosync_conf
