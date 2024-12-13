# pylint: disable=too-many-lines
import math
import os.path
import time
from typing import (
    Any,
    Collection,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    cast,
)

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
    ssl,
)
from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncQuorumDeviceSettingsDto,
)
from pcs.common.file import RawFileError
from pcs.common.node_communicator import HostNotFound
from pcs.common.reports import ReportProcessor
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import (
    ReportItem,
    ReportItemList,
)
from pcs.common.str_tools import join_multilines
from pcs.common.tools import format_os_error
from pcs.common.types import (
    CorosyncTransportType,
    UnknownCorosyncTransportTypeException,
)
from pcs.lib import (
    node_communication_format,
    sbd,
    validate,
)
from pcs.lib.booth import sync as booth_sync
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.resource.guest_node import find_node_list as get_guest_nodes
from pcs.lib.cib.resource.remote_node import find_node_list as get_remote_nodes
from pcs.lib.communication import cluster
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    DistributeCorosyncConf,
    ReloadCorosyncConf,
)
from pcs.lib.communication.nodes import (
    CheckPacemakerStarted,
    DistributeFilesWithoutForces,
    EnableCluster,
    GetHostInfo,
    GetOnlineTargets,
    RemoveFilesWithoutForces,
    RemoveNodesFromCib,
    SendPcsdSslCertAndKey,
    StartCluster,
    UpdateKnownHosts,
)
from pcs.lib.communication.sbd import (
    CheckSbd,
    DisableSbdService,
    EnableSbdService,
    SetSbdConfig,
)
from pcs.lib.communication.tools import AllSameDataMixin, run_and_raise
from pcs.lib.communication.tools import run as run_com
from pcs.lib.corosync import (
    config_facade,
    config_parser,
    config_validators,
    qdevice_net,
)
from pcs.lib.corosync import constants as corosync_constants
from pcs.lib.env import (
    LibraryEnvironment,
    WaitType,
)
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.live import (
    get_cib,
    get_cib_xml,
    get_cib_xml_cmd_results,
    remove_node,
)
from pcs.lib.pacemaker.live import verify as verify_cmd
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pacemaker.values import get_valid_timeout_seconds
from pcs.lib.tools import (
    environment_file_to_dict,
    generate_binary_key,
    generate_uuid,
)


def node_clear(
    env: LibraryEnvironment,
    node_name,
    allow_clear_cluster_node=False,
):
    """
    Remove specified node from various cluster caches.

    LibraryEnvironment env provides all for communication with externals
    string node_name
    bool allow_clear_cluster_node -- flag allows to clear node even if it's
        still in a cluster
    """
    _ensure_live_env(env)  # raises if env is not live

    current_nodes, report_list = get_existing_nodes_names(
        env.get_corosync_conf(), env.get_cib()
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    if node_name in current_nodes:
        if env.report_processor.report(
            ReportItem(
                severity=reports.item.get_severity(
                    report_codes.FORCE,
                    allow_clear_cluster_node,
                ),
                message=reports.messages.NodeToClearIsStillInCluster(node_name),
            )
        ).has_errors:
            raise LibraryError()

    remove_node(env.cmd_runner(), node_name)


def verify(env: LibraryEnvironment, verbose=False):
    runner = env.cmd_runner()
    (
        dummy_stdout,
        verify_stderr,
        verify_returncode,
        can_be_more_verbose,
    ) = verify_cmd(runner, verbose=verbose)

    # 1) Do not even try to think about upgrading!
    # 2) We do not need cib management in env (no need for push...).
    # So env.get_cib is not best choice here (there were considerations to
    # upgrade cib at all times inside env.get_cib). Go to a lower level here.
    if verify_returncode != 0:
        env.report_processor.report(
            ReportItem.error(
                reports.messages.InvalidCibContent(
                    verify_stderr,
                    can_be_more_verbose,
                )
            )
        )

        # Cib is sometimes loadable even if `crm_verify` fails (e.g. when
        # fencing topology is invalid). On the other hand cib with id
        # duplication is not loadable.
        # We try extra checks when cib is possible to load.
        cib_xml, dummy_stderr, returncode = get_cib_xml_cmd_results(runner)
        if returncode != 0:
            raise LibraryError()
    else:
        cib_xml = get_cib_xml(runner)

    cib = get_cib(cib_xml)
    env.report_processor.report_list(
        fencing_topology.verify(
            cib,
            ClusterState(env.get_cluster_state()).node_section.nodes,
        )
    )
    if env.report_processor.has_errors:
        raise LibraryError()


def setup(  # noqa:  PLR0913, PLR0915
    env: LibraryEnvironment,
    cluster_name: str,
    nodes: Sequence[Mapping[str, Any]],
    transport_type: Optional[str] = None,
    transport_options: Optional[Mapping[str, str]] = None,
    link_list: Optional[Sequence[Mapping[str, Any]]] = None,
    compression_options: Optional[Mapping[str, str]] = None,
    crypto_options: Optional[Mapping[str, str]] = None,
    totem_options: Optional[Mapping[str, str]] = None,
    quorum_options: Optional[Mapping[str, str]] = None,
    wait: WaitType = False,
    start: bool = False,
    enable: bool = False,
    no_keys_sync: bool = False,
    no_cluster_uuid: bool = False,
    force_flags: Collection[reports.types.ForceCode] = (),
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
    _ensure_live_env(env)  # raises if env is not live
    force = report_codes.FORCE in force_flags

    transport_type = transport_type or "knet"
    transport_options = transport_options or {}
    link_list = link_list or []
    compression_options = compression_options or {}
    crypto_options = crypto_options or {}
    totem_options = totem_options or {}
    quorum_options = quorum_options or {}
    nodes = [_normalize_dict(node, {"addrs"}) for node in nodes]
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
    addrs_defaulter = _get_addrs_defaulter(
        report_processor, {target.label: target for target in target_list}
    )
    nodes = [
        _set_defaults_in_dict(node, {"addrs": addrs_defaulter})
        for node in nodes
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
    wait_timeout = _get_validated_wait_timeout(report_processor, wait, start)

    # Validate the nodes
    com_cmd: AllSameDataMixin = GetHostInfo(report_processor)
    com_cmd.set_targets(target_list)
    report_processor.report_list(
        _host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd), force
        )
    )

    # If there is an error reading the file, this will report it and exit
    # safely before any change is made to the nodes.
    sync_ssl_certs = _is_ssl_cert_sync_enabled(report_processor)

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
                ReportItem.info(
                    reports.messages.PcsdSslCertAndKeyDistributionStarted(
                        sorted([target.label for target in target_list])
                    )
                )
            )
            # Local certificate and key cannot be used because the local node
            # may not be a part of the new cluter at all.
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
        ReportItem.info(reports.messages.ClusterSetupSuccess())
    ).has_errors:
        raise LibraryError()

    # Optionally enable and start cluster services.
    if enable:
        com_cmd = EnableCluster(env.report_processor)
        com_cmd.set_targets(target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    if start:
        _start_cluster(
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
    link_list: Sequence[Mapping[str, Any]],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
    quorum_options: Mapping[str, str],
    no_cluster_uuid: bool = False,
    force_flags: Collection[reports.types.ForceCode] = (),
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
    force = report_codes.FORCE in force_flags

    transport_type = transport_type or "knet"
    nodes = [_normalize_dict(node, {"addrs"}) for node in nodes]
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
    addrs_defaulter = _get_addrs_defaulter(
        report_processor,
        {target.label: target for target in target_list},
        default_to_name_if_no_target=True,
    )
    nodes = [
        _set_defaults_in_dict(node, {"addrs": addrs_defaulter})
        for node in nodes
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
    link_list: Sequence[Mapping[str, Any]],
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
    link_list: Sequence[Mapping[str, Any]],
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

    _verify_corosync_conf(corosync_conf)  # raises if corosync not valid
    return corosync_conf


def _config_update(
    report_processor: ReportProcessor,
    corosync_conf: config_facade.ConfigFacade,
    transport_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
) -> None:
    transport_type = corosync_conf.get_transport()
    report_list = config_validators.update_totem(totem_options)
    if transport_type in corosync_constants.TRANSPORTS_KNET:
        report_list += config_validators.update_transport_knet(
            transport_options,
            compression_options,
            crypto_options,
            corosync_conf.get_crypto_options(),
        )
    elif transport_type in corosync_constants.TRANSPORTS_UDP:
        report_list += config_validators.update_transport_udp(
            transport_options,
            compression_options,
            crypto_options,
        )
    else:
        report_processor.report(
            ReportItem.error(
                reports.messages.CorosyncConfigUnsupportedTransport(
                    transport_type, sorted(corosync_constants.TRANSPORTS_ALL)
                )
            )
        )
    if report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    corosync_conf.set_totem_options(totem_options)
    corosync_conf.set_transport_options(
        transport_options,
        compression_options,
        crypto_options,
    )
    _verify_corosync_conf(corosync_conf)  # raises if corosync not valid


def config_update(
    env: LibraryEnvironment,
    transport_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
) -> None:
    """
    Update corosync.conf in the local cluster

    env
    transport_options -- transport specific options
    compression_options -- only available for knet transport. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options -- only available for knet transport. In corosync.conf
        they are prefixed 'crypto_'
    totem_options -- options of section 'totem' in corosync.conf
    """
    _ensure_live_env(env)
    corosync_conf = env.get_corosync_conf()
    _config_update(
        env.report_processor,
        corosync_conf,
        transport_options,
        compression_options,
        crypto_options,
        totem_options,
    )
    env.push_corosync_conf(corosync_conf)


def config_update_local(
    env: LibraryEnvironment,
    corosync_conf_content: bytes,
    transport_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
) -> bytes:
    """
    Update corosync.conf passed as an argument and return the updated conf

    env
    corosync_conf_content -- corosync.conf to be updated
    transport_options -- transport specific options
    compression_options -- only available for knet transport. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options -- only available for knet transport. In corosync.conf
        they are prefixed 'crypto_'
    totem_options -- options of section 'totem' in corosync.conf
    """
    # As we are getting a corosync.conf content as an argument, we want to make
    # sure it was not given to LibraryEnvironment as well. Also we don't
    # allow/need CIB to be handled by LibraryEnvironment.
    _ensure_live_env(env)
    corosync_conf_instance = FileInstance.for_corosync_conf()
    try:
        corosync_conf: config_facade.ConfigFacade = cast(
            config_facade.ConfigFacade,
            corosync_conf_instance.raw_to_facade(corosync_conf_content),
        )
    except ParserErrorException as e:
        if env.report_processor.report_list(
            corosync_conf_instance.toolbox.parser.exception_to_report_list(
                e,
                corosync_conf_instance.toolbox.file_type_code,
                None,
                force_code=None,
                is_forced_or_warning=False,
            )
        ).has_errors:
            raise LibraryError() from e
    _config_update(
        env.report_processor,
        corosync_conf,
        transport_options,
        compression_options,
        crypto_options,
        totem_options,
    )
    return corosync_conf_instance.facade_to_raw(corosync_conf)


def get_corosync_conf_struct(env: LibraryEnvironment) -> CorosyncConfDto:
    """
    Read corosync.conf from the local node and return it in a structured form
    """
    corosync_conf = env.get_corosync_conf()
    quorum_device_dto: Optional[CorosyncQuorumDeviceSettingsDto] = None
    qd_model = corosync_conf.get_quorum_device_model()
    if qd_model is not None:
        (
            qd_model_options,
            qd_generic_options,
            qd_heuristics_options,
        ) = corosync_conf.get_quorum_device_settings()
        quorum_device_dto = CorosyncQuorumDeviceSettingsDto(
            model=qd_model,
            model_options=qd_model_options,
            generic_options=qd_generic_options,
            heuristics_options=qd_heuristics_options,
        )
    try:
        return CorosyncConfDto(
            cluster_name=corosync_conf.get_cluster_name(),
            cluster_uuid=corosync_conf.get_cluster_uuid(),
            transport=CorosyncTransportType.from_str(
                corosync_conf.get_transport()
            ),
            totem_options=corosync_conf.get_totem_options(),
            transport_options=corosync_conf.get_transport_options(),
            compression_options=corosync_conf.get_compression_options(),
            crypto_options=corosync_conf.get_crypto_options(),
            nodes=[node.to_dto() for node in corosync_conf.get_nodes()],
            links_options=corosync_conf.get_links_options(),
            quorum_options=corosync_conf.get_quorum_options(),
            quorum_device=quorum_device_dto,
        )
    except UnknownCorosyncTransportTypeException as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CorosyncConfigUnsupportedTransport(
                    e.transport, sorted(corosync_constants.TRANSPORTS_ALL)
                )
            )
        ) from e


def add_nodes(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    nodes,
    wait=False,
    start=False,
    enable=False,
    no_watchdog_validation=False,
    force_flags: Collection[reports.types.ForceCode] = (),
):
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Add specified nodes to the local cluster
    Raise LibraryError on any error.

    env LibraryEnvironment
    nodes list -- list of dicts which represents node.
        Supported keys are: name (required), addrs (list), devices (list),
        watchdog. See note below.
    wait -- specifies if command should try to wait for cluster to start up.
        Has no effect start is False. If set to False command will not wait for
        cluster to start. If None command will wait for some default timeout.
        If int wait set timeout to int value of seconds.
    start bool -- if True start cluster when it is set up
    enable bool -- if True enable cluster when it is set up
    no_watchdog_validation bool -- if True do not validate specified watchdogs
        on remote hosts
    force_flags list -- list of flags codes

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
    _ensure_live_env(env)  # raises if env is not live

    force = report_codes.FORCE in force_flags
    skip_offline_nodes = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()
    is_sbd_enabled = sbd.is_sbd_enabled(env.service_manager)
    corosync_conf = env.get_corosync_conf()
    corosync_node_options = {"name", "addrs"}
    sbd_node_options = {"devices", "watchdog"}

    keys_to_normalize = {"addrs"}
    if is_sbd_enabled:
        keys_to_normalize |= sbd_node_options
    new_nodes = [_normalize_dict(node, keys_to_normalize) for node in nodes]

    # get targets for existing nodes
    cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        corosync_conf,
        # Pcs is unable to communicate with nodes missing names. It cannot send
        # new corosync.conf to them. That might break the cluster. Hence we
        # error out.
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)
    (
        target_report_list,
        cluster_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        cluster_nodes_names,
        skip_non_existing=skip_offline_nodes,
    )
    report_processor.report_list(target_report_list)

    # get a target for qnetd if needed
    if corosync_conf.get_quorum_device_model() == "net":
        (
            qdevice_model_options,
            _,
            _,
        ) = corosync_conf.get_quorum_device_settings()
        try:
            qnetd_target = target_factory.get_target(
                qdevice_model_options["host"]
            )
        except HostNotFound:
            report_processor.report(
                ReportItem.error(
                    reports.messages.HostNotFound(
                        [qdevice_model_options["host"]]
                    )
                )
            )

    # Get targets for new nodes and report unknown (== not-authorized) nodes.
    # If a node doesn't contain the 'name' key, validation of inputs reports it.
    # That means we don't report missing names but cannot rely on them being
    # present either.
    (
        target_report_list,
        new_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        [node["name"] for node in new_nodes if "name" in node],
        allow_skip=False,
    )
    report_processor.report_list(target_report_list)

    # Set default values for not-specified node options.
    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole node add command / form significantly.
    new_nodes_target_dict = {
        target.label: target for target in new_nodes_target_list
    }
    addrs_defaulter = _get_addrs_defaulter(
        report_processor, new_nodes_target_dict
    )
    new_nodes_defaulters = {"addrs": addrs_defaulter}
    if is_sbd_enabled:
        watchdog_defaulter = _get_watchdog_defaulter(
            report_processor, new_nodes_target_dict
        )
        new_nodes_defaulters["devices"] = lambda _: []
        new_nodes_defaulters["watchdog"] = watchdog_defaulter
    new_nodes = [
        _set_defaults_in_dict(node, new_nodes_defaulters) for node in new_nodes
    ]
    new_nodes_dict = {
        node["name"]: node for node in new_nodes if "name" in node
    }

    # Validate inputs - node options names
    # We do not want to make corosync validators know about SBD options and
    # vice versa. Therefore corosync and SBD validators get only valid corosync
    # and SBD options respectively, and we need to check for any surplus
    # options here.
    report_processor.report_list(
        validate.NamesIn(
            corosync_node_options | sbd_node_options, option_type="node"
        ).validate(
            {
                # Get a dict containing options of all nodes. Values don't
                # matter for validate.NamesIn validator.
                option_name: ""
                for node_option_names in [node.keys() for node in new_nodes]
                for option_name in node_option_names
            }
        )
    )

    # Validate inputs - corosync part
    try:
        cib = env.get_cib()
        cib_nodes = get_remote_nodes(cib) + get_guest_nodes(cib)
    except LibraryError:
        cib_nodes = []
        report_processor.report(
            ReportItem(
                reports.item.get_severity(report_codes.FORCE, force),
                reports.messages.CibLoadErrorGetNodesForValidation(),
            )
        )
    # corosync validator rejects non-corosync keys
    new_nodes_corosync = [
        {key: node[key] for key in corosync_node_options if key in node}
        for node in new_nodes
    ]
    report_processor.report_list(
        config_validators.add_nodes(
            new_nodes_corosync,
            corosync_conf.get_nodes(),
            cib_nodes,
            force_unresolvable=force,
        )
    )

    # Validate inputs - SBD part
    if is_sbd_enabled:
        report_processor.report_list(
            sbd.validate_new_nodes_devices(
                {
                    node["name"]: node["devices"]
                    for node in new_nodes
                    if "name" in node
                }
            )
        )
    else:
        for node in new_nodes:
            sbd_options = sbd_node_options.intersection(node.keys())
            if sbd_options and "name" in node:
                report_processor.report(
                    ReportItem.error(
                        reports.messages.SbdNotUsedCannotSetSbdOptions(
                            sorted(sbd_options), node["name"]
                        )
                    )
                )

    # Validate inputs - flags part
    wait_timeout = _get_validated_wait_timeout(report_processor, wait, start)

    # Get online cluster nodes
    # This is the only call in which we accept skip_offline_nodes option for the
    # cluster nodes. In all the other actions we communicate only with the
    # online nodes. This allows us to simplify code as any communication issue
    # is considered an error, ends the command processing and is not possible
    # to skip it by skip_offline_nodes. We do not have to care about a situation
    # when a communication command cannot connect to some nodes and then the
    # next command can connect but fails due to the previous one did not
    # succeed.
    online_cluster_target_list = []
    if cluster_nodes_target_list:
        com_cmd: AllSameDataMixin = GetOnlineTargets(
            report_processor,
            ignore_offline_targets=skip_offline_nodes,
        )
        com_cmd.set_targets(cluster_nodes_target_list)
        online_cluster_target_list = run_com(
            env.get_node_communicator(), com_cmd
        )
        offline_cluster_target_list = [
            target
            for target in cluster_nodes_target_list
            if target not in online_cluster_target_list
        ]
        if not online_cluster_target_list:
            report_processor.report(
                ReportItem.error(
                    reports.messages.UnableToPerformOperationOnAnyNode()
                )
            )
        elif offline_cluster_target_list and skip_offline_nodes:
            # TODO: report (warn) how to fix offline nodes when they come online
            # report_processor.report(None)
            pass

    # Validate existing cluster nodes status
    atb_has_to_be_enabled = sbd.atb_has_to_be_enabled(
        env.service_manager, corosync_conf, len(new_nodes)
    )
    if atb_has_to_be_enabled:
        if online_cluster_target_list:
            com_cmd = CheckCorosyncOffline(
                report_processor, allow_skip_offline=False
            )
            com_cmd.set_targets(online_cluster_target_list)
            cluster_running_target_list = run_com(
                env.get_node_communicator(), com_cmd
            )
            if cluster_running_target_list:
                report_processor.report(
                    ReportItem.error(
                        reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning()
                    )
                )
            else:
                report_processor.report(
                    ReportItem.warning(
                        reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbd()
                    )
                )

    # Validate new nodes. All new nodes have to be online.
    com_cmd = GetHostInfo(report_processor)
    com_cmd.set_targets(new_nodes_target_list)
    report_processor.report_list(
        _host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd),
            force,
            # version of services may not be the same across the existing
            # cluster nodes, so it's not easy to make this check properly
            check_services_versions=False,
        )
    )

    # Validate SBD on new nodes
    if is_sbd_enabled:
        if no_watchdog_validation:
            report_processor.report(
                ReportItem.warning(
                    reports.messages.SbdWatchdogValidationInactive()
                )
            )
        com_cmd_sbd = CheckSbd(report_processor)
        for new_node_target in new_nodes_target_list:
            new_node = new_nodes_dict[new_node_target.label]
            # Do not send watchdog if validation is turned off. Listing of
            # available watchdogs in pcsd may restart the machine in some
            # corner cases.
            com_cmd_sbd.add_request(
                new_node_target,
                watchdog="" if no_watchdog_validation else new_node["watchdog"],
                device_list=new_node["devices"],
            )
        run_com(env.get_node_communicator(), com_cmd_sbd)

    # If there is an error reading the file, this will report it and exit
    # safely before any change is made to the nodes.
    sync_ssl_certs = _is_ssl_cert_sync_enabled(report_processor)

    if report_processor.has_errors:
        raise LibraryError()

    # Validation done. If errors occurred, an exception has been raised and we
    # don't get below this line.

    # First set up everything else than corosync. Once the new nodes are present
    # in corosync.conf, they're considered part of a cluster and the node add
    # command cannot be run again. So we need to minimize the amount of actions
    # (and therefore possible failures) after adding the nodes to corosync.

    # distribute auth tokens of all cluster nodes (including the new ones) to
    # all new nodes
    com_cmd = UpdateKnownHosts(
        env.report_processor,
        known_hosts_to_add=env.get_known_hosts(
            cluster_nodes_names + list(new_nodes_dict.keys())
        ),
        known_hosts_to_remove=[],
    )
    com_cmd.set_targets(new_nodes_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # qdevice setup
    if corosync_conf.get_quorum_device_model() == "net":
        qdevice_net.set_up_client_certificates(
            env.cmd_runner(),
            env.report_processor,
            env.communicator_factory,
            qnetd_target,
            corosync_conf.get_cluster_name(),
            new_nodes_target_list,
            # we don't want to allow skipping offline nodes which are being
            # added, otherwise qdevice will not work properly
            skip_offline_nodes=False,
            allow_skip_offline=False,
        )

    # sbd setup
    if is_sbd_enabled:
        sbd_cfg = environment_file_to_dict(sbd.get_local_sbd_config())

        com_cmd_sbd_cfg = SetSbdConfig(env.report_processor)
        for new_node_target in new_nodes_target_list:
            new_node = new_nodes_dict[new_node_target.label]
            com_cmd_sbd_cfg.add_request(
                new_node_target,
                sbd.create_sbd_config(
                    sbd_cfg,
                    new_node["name"],
                    watchdog=new_node["watchdog"],
                    device_list=new_node["devices"],
                ),
            )
        run_and_raise(env.get_node_communicator(), com_cmd_sbd_cfg)

        com_cmd = EnableSbdService(env.report_processor)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    else:
        com_cmd = DisableSbdService(env.report_processor)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # booth setup
    booth_sync.send_all_config_to_node(
        env.get_node_communicator(),
        env.report_processor,
        new_nodes_target_list,
        rewrite_existing=force,
        skip_wrong_config=force,
    )

    # distribute corosync and pacemaker authkeys and other config files
    files_action = {}
    severity = reports.item.get_severity(reports.codes.FORCE, force)
    if os.path.isfile(settings.corosync_authkey_file):
        try:
            with open(
                settings.corosync_authkey_file, "rb"
            ) as corosync_authkey_file:
                files_action.update(
                    node_communication_format.corosync_authkey_file(
                        corosync_authkey_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.COROSYNC_AUTHKEY,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.corosync_authkey_file,
                    ),
                )
            )

    if os.path.isfile(settings.pacemaker_authkey_file):
        try:
            with open(
                settings.pacemaker_authkey_file, "rb"
            ) as pcmk_authkey_file:
                files_action.update(
                    node_communication_format.pcmk_authkey_file(
                        pcmk_authkey_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.PACEMAKER_AUTHKEY,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pacemaker_authkey_file,
                    ),
                )
            )

    if os.path.isfile(settings.pcsd_dr_config_location):
        try:
            with open(
                settings.pcsd_dr_config_location, "rb"
            ) as pcs_dr_config_file:
                files_action.update(
                    node_communication_format.pcs_dr_config_file(
                        pcs_dr_config_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.PCS_DR_CONFIG,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_dr_config_location,
                    ),
                )
            )

    # pcs_settings.conf was previously synced using pcsdcli send_local_configs.
    # This has been changed temporarily until new system for distribution and
    # synchronization of configs will be introduced.
    if os.path.isfile(settings.pcsd_settings_conf_location):
        try:
            with open(
                settings.pcsd_settings_conf_location, "r"
            ) as pcs_settings_conf_file:
                files_action.update(
                    node_communication_format.pcs_settings_conf_file(
                        pcs_settings_conf_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.PCS_SETTINGS_CONF,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_settings_conf_location,
                    ),
                )
            )

    # stop here if one of the files could not be loaded and it was not forced
    if report_processor.has_errors:
        raise LibraryError()

    if files_action:
        com_cmd = DistributeFilesWithoutForces(
            env.report_processor, files_action
        )
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute and reload pcsd SSL certificate
    if sync_ssl_certs:
        report_processor.report(
            ReportItem.info(
                reports.messages.PcsdSslCertAndKeyDistributionStarted(
                    sorted([target.label for target in new_nodes_target_list])
                )
            )
        )

        try:
            with open(settings.pcsd_cert_location, "r") as file:
                ssl_cert = file.read()
        except OSError as e:
            report_processor.report(
                ReportItem.error(
                    reports.messages.FileIoError(
                        file_type_codes.PCSD_SSL_CERT,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_cert_location,
                    )
                )
            )
        try:
            with open(settings.pcsd_key_location, "r") as file:
                ssl_key = file.read()
        except OSError as e:
            report_processor.report(
                ReportItem.error(
                    reports.messages.FileIoError(
                        file_type_codes.PCSD_SSL_KEY,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_key_location,
                    )
                )
            )
        if report_processor.has_errors:
            raise LibraryError()

        com_cmd = SendPcsdSslCertAndKey(env.report_processor, ssl_cert, ssl_key)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # When corosync >= 2 is in use, the procedure for adding a node is:
    # 1. add the new node to corosync.conf on all existing nodes
    # 2. reload corosync.conf before the new node is started
    # 3. start the new node
    # If done otherwise, membership gets broken and qdevice hangs. Cluster
    # will recover after a minute or so but still it's a wrong way.

    corosync_conf.add_nodes(new_nodes_corosync)
    if atb_has_to_be_enabled:
        corosync_conf.set_quorum_options(dict(auto_tie_breaker="1"))

    _verify_corosync_conf(corosync_conf)  # raises if corosync not valid
    com_cmd = DistributeCorosyncConf(
        env.report_processor,
        corosync_conf.config.export(),
        allow_skip_offline=False,
    )
    com_cmd.set_targets(online_cluster_target_list + new_nodes_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = ReloadCorosyncConf(env.report_processor)
    com_cmd.set_targets(online_cluster_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Optionally enable and start cluster services.
    if enable:
        com_cmd = EnableCluster(env.report_processor)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    if start:
        _start_cluster(
            env.communicator_factory,
            env.report_processor,
            new_nodes_target_list,
            wait_timeout=wait_timeout,
        )


def _ensure_live_env(env: LibraryEnvironment):
    not_live = []
    if not env.is_cib_live:
        not_live.append(file_type_codes.CIB)
    if not env.is_corosync_conf_live:
        not_live.append(file_type_codes.COROSYNC_CONF)
    if not_live:
        raise LibraryError(
            ReportItem.error(reports.messages.LiveEnvironmentRequired(not_live))
        )


def _start_cluster(
    communicator_factory,
    report_processor: ReportProcessor,
    target_list,
    wait_timeout=False,
):
    # Large clusters take longer time to start up. So we make the timeout
    # longer for each 8 nodes:
    #  1 -  8 nodes: 1 * timeout
    #  9 - 16 nodes: 2 * timeout
    # 17 - 24 nodes: 3 * timeout
    # and so on ...
    # Users can override this and set their own timeout by specifying
    # the --request-timeout option.
    timeout = int(
        settings.default_request_timeout * math.ceil(len(target_list) / 8.0)
    )
    com_cmd = StartCluster(report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(
        communicator_factory.get_communicator(request_timeout=timeout), com_cmd
    )
    if wait_timeout is not False:
        if report_processor.report_list(
            _wait_for_pacemaker_to_start(
                communicator_factory.get_communicator(),
                report_processor,
                target_list,
                # wait_timeout is either None or a timeout
                timeout=wait_timeout,
            )
        ).has_errors:
            raise LibraryError()


def _wait_for_pacemaker_to_start(
    node_communicator,
    report_processor: ReportProcessor,
    target_list,
    timeout=None,
):
    timeout = 60 * 15 if timeout is None else timeout
    interval = 2
    stop_at = time.time() + timeout
    report_processor.report(
        ReportItem.info(
            reports.messages.WaitForNodeStartupStarted(
                sorted([target.label for target in target_list])
            )
        )
    )
    error_report_list = []
    has_errors = False
    while target_list:
        if time.time() > stop_at:
            error_report_list.append(
                ReportItem.error(reports.messages.WaitForNodeStartupTimedOut())
            )
            break
        time.sleep(interval)
        com_cmd = CheckPacemakerStarted(report_processor)
        com_cmd.set_targets(target_list)
        target_list = run_com(node_communicator, com_cmd)
        has_errors = has_errors or com_cmd.has_errors

    if error_report_list or has_errors:
        error_report_list.append(
            ReportItem.error(reports.messages.WaitForNodeStartupError())
        )
    return error_report_list


def _host_check_cluster_setup(
    host_info_dict, force, check_services_versions=True
):
    # pylint: disable=too-many-locals
    report_list = []
    # We only care about services which matter for creating a cluster. It does
    # not make sense to check e.g. booth when a) it will never be used b) it
    # will be used in a year - which means we should do the check in a year.
    service_version_dict = {
        "pacemaker": {},
        "corosync": {},
        "pcsd": {},
    }
    required_service_list = ["pacemaker", "corosync"]
    required_as_stopped_service_list = required_service_list + [
        "pacemaker_remote"
    ]
    severity = reports.item.get_severity(report_codes.FORCE, force)
    cluster_exists_on_nodes = False
    for host_name, host_info in host_info_dict.items():
        try:
            services = host_info["services"]
            if check_services_versions:
                for service, version_dict in service_version_dict.items():
                    version_dict[host_name] = services[service]["version"]
            missing_service_list = [
                service
                for service in required_service_list
                if not services[service]["installed"]
            ]
            if missing_service_list:
                report_list.append(
                    ReportItem.error(
                        reports.messages.ServiceNotInstalled(
                            host_name, sorted(missing_service_list)
                        )
                    )
                )
            cannot_be_running_service_list = [
                service
                for service in required_as_stopped_service_list
                if service in services and services[service]["running"]
            ]
            if cannot_be_running_service_list:
                cluster_exists_on_nodes = True
                report_list.append(
                    ReportItem(
                        severity=severity,
                        message=reports.messages.HostAlreadyInClusterServices(
                            host_name,
                            sorted(cannot_be_running_service_list),
                        ),
                    )
                )
            if host_info["cluster_configuration_exists"]:
                cluster_exists_on_nodes = True
                report_list.append(
                    ReportItem(
                        severity=severity,
                        message=reports.messages.HostAlreadyInClusterConfig(
                            host_name,
                        ),
                    )
                )
        except KeyError:
            report_list.append(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(host_name)
                )
            )

    if check_services_versions:
        for service, version_dict in service_version_dict.items():
            report_list.extend(
                _check_for_not_matching_service_versions(service, version_dict)
            )

    if cluster_exists_on_nodes and not force:
        # This is always a forceable error
        report_list.append(
            ReportItem(
                severity=reports.item.ReportItemSeverity.error(
                    report_codes.FORCE
                ),
                message=reports.messages.ClusterWillBeDestroyed(),
            )
        )
    return report_list


def _check_for_not_matching_service_versions(service, service_version_dict):
    if len(set(service_version_dict.values())) <= 1:
        return []
    return [
        ReportItem.error(
            reports.messages.ServiceVersionMismatch(
                service, service_version_dict
            )
        )
    ]


def _normalize_dict(input_dict, required_keys):
    normalized = dict(input_dict)
    for key in required_keys:
        if key not in normalized:
            normalized[key] = None
    return normalized


def _set_defaults_in_dict(input_dict, defaults):
    completed = dict(input_dict)
    for key, factory in defaults.items():
        if completed[key] is None:
            completed[key] = factory(input_dict)
    return completed


def _get_addrs_defaulter(
    report_processor: ReportProcessor,
    targets_dict,
    default_to_name_if_no_target: bool = False,
):
    def defaulter(node):
        if "name" not in node:
            return []
        address_for_use = None
        address_source = None
        target = targets_dict.get(node["name"])
        if target:
            address_for_use = target.first_addr
            address_source = reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
        elif default_to_name_if_no_target:
            address_for_use = node["name"]
            address_source = reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
        if address_for_use:
            report_processor.report(
                ReportItem.info(
                    reports.messages.UsingDefaultAddressForHost(
                        node["name"], address_for_use, address_source
                    )
                )
            )
            return [address_for_use]
        return []

    return defaulter


def _get_watchdog_defaulter(report_processor: ReportProcessor, targets_dict):
    del targets_dict

    def defaulter(node):
        report_processor.report(
            ReportItem.info(
                reports.messages.UsingDefaultWatchdog(
                    settings.sbd_watchdog_default,
                    node["name"],
                )
            )
        )
        return settings.sbd_watchdog_default

    return defaulter


def _get_validated_wait_timeout(report_processor, wait, start):
    try:
        if wait is False:
            return False
        if not start:
            report_processor.report(
                ReportItem.error(
                    reports.messages.WaitForNodeStartupWithoutStart()
                )
            )
        return get_valid_timeout_seconds(wait)
    except LibraryError as e:
        report_processor.report_list(e.args)
    return None


def _is_ssl_cert_sync_enabled(report_processor: ReportProcessor):
    try:
        if os.path.isfile(settings.pcsd_config):
            with open(settings.pcsd_config, "r") as cfg_file:
                cfg = environment_file_to_dict(cfg_file.read())
                return (
                    cfg.get("PCSD_SSL_CERT_SYNC_ENABLED", "false").lower()
                    == "true"
                )
    except OSError as e:
        report_processor.report(
            ReportItem.error(
                reports.messages.FileIoError(
                    file_type_codes.PCSD_ENVIRONMENT_CONFIG,
                    RawFileError.ACTION_READ,
                    format_os_error(e),
                    file_path=settings.pcsd_config,
                )
            )
        )
    return False


def _verify_corosync_conf(corosync_conf_facade):
    # This is done in pcs.lib.env.LibraryEnvironment.push_corosync_conf
    # usually. But there are special cases here which use custom corosync.conf
    # pushing so the check must be done individually.
    (
        bad_sections,
        bad_attr_names,
        bad_attr_values,
    ) = config_parser.verify_section(corosync_conf_facade.config)
    if bad_sections or bad_attr_names or bad_attr_values:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CorosyncConfigCannotSaveInvalidNamesValues(
                    bad_sections,
                    bad_attr_names,
                    bad_attr_values,
                )
            )
        )


def remove_nodes(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    node_list,
    force_flags: Collection[reports.types.ForceCode] = (),
):
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Remove nodes from a cluster.

    env LibraryEnvironment
    node_list iterable -- names of nodes to remove
    force_flags list -- list of flags codes
    """
    _ensure_live_env(env)  # raises if env is not live

    force_quorum_loss = report_codes.FORCE in force_flags
    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()
    corosync_conf = env.get_corosync_conf()

    # validations

    cluster_nodes_names, report_list = get_existing_nodes_names(
        corosync_conf,
        # Pcs is unable to communicate with nodes missing names. It cannot send
        # new corosync.conf to them. That might break the cluster. Hence we
        # error out.
        error_on_missing_name=True,
    )
    report_processor.report_list(report_list)

    report_processor.report_list(
        config_validators.remove_nodes(
            node_list,
            corosync_conf.get_nodes(),
            corosync_conf.get_quorum_device_model(),
            corosync_conf.get_quorum_device_settings(),
        )
    )
    if report_processor.has_errors:
        # If there is an error, there is usually not much sense in doing other
        # validations:
        # - if there would be no node left in the cluster, it's pointless
        #   to check for quorum loss or if at least one remaining node is online
        # - if only one node is being removed and it doesn't exist, it's again
        #   pointless to check for other issues
        raise LibraryError()

    (
        target_report_list,
        cluster_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        cluster_nodes_names,
        skip_non_existing=skip_offline,
    )
    known_nodes = {target.label for target in cluster_nodes_target_list}
    unknown_nodes = {
        name for name in cluster_nodes_names if name not in known_nodes
    }
    report_processor.report_list(target_report_list)

    com_cmd: AllSameDataMixin = GetOnlineTargets(
        report_processor,
        ignore_offline_targets=skip_offline,
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    online_target_list = run_com(env.get_node_communicator(), com_cmd)
    offline_target_list = [
        target
        for target in cluster_nodes_target_list
        if target not in online_target_list
    ]
    staying_online_target_list = [
        target for target in online_target_list if target.label not in node_list
    ]
    targets_to_remove = [
        target
        for target in cluster_nodes_target_list
        if target.label in node_list
    ]
    if not staying_online_target_list:
        report_processor.report(
            ReportItem.error(
                reports.messages.UnableToConnectToAnyRemainingNode()
            )
        )
        # If no remaining node is online, there is no point in checking quorum
        # loss or anything as we would just get errors.
        raise LibraryError()

    if skip_offline:
        staying_offline_nodes = [
            target.label
            for target in offline_target_list
            if target.label not in node_list
        ] + [name for name in unknown_nodes if name not in node_list]
        if staying_offline_nodes:
            report_processor.report(
                ReportItem.warning(
                    reports.messages.UnableToConnectToAllRemainingNodes(
                        sorted(staying_offline_nodes)
                    )
                )
            )

    atb_has_to_be_enabled = sbd.atb_has_to_be_enabled(
        env.service_manager, corosync_conf, -len(node_list)
    )
    if atb_has_to_be_enabled:
        com_cmd = CheckCorosyncOffline(
            report_processor, allow_skip_offline=False
        )
        com_cmd.set_targets(staying_online_target_list)
        cluster_running_target_list = run_com(
            env.get_node_communicator(), com_cmd
        )
        if cluster_running_target_list:
            report_processor.report(
                ReportItem.error(
                    reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning()
                )
            )
        else:
            report_processor.report(
                ReportItem.warning(
                    reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbd()
                )
            )
    else:
        # Check if removing the nodes would cause quorum loss. We ask the nodes
        # to be removed for their view of quorum. If they are all stopped or
        # not in a quorate partition, their removal cannot cause quorum loss.
        # That's why we ask them and not the remaining nodes.
        # example: 5-node cluster, 3 online nodes, removing one online node,
        # results in 4-node cluster with 2 online nodes => quorum lost
        # Check quorum loss only if ATB does not need to be enabled. If it is
        # required, cluster has to be turned off and therefore it loses quorum.
        com_cmd = cluster.GetQuorumStatus(report_processor)
        com_cmd.set_targets(targets_to_remove)
        failures, quorum_status_facade = run_com(
            env.get_node_communicator(), com_cmd
        )
        if quorum_status_facade:
            if quorum_status_facade.stopping_nodes_cause_quorum_loss(node_list):
                report_processor.report(
                    ReportItem(
                        severity=reports.item.get_severity(
                            report_codes.FORCE,
                            force_quorum_loss,
                        ),
                        message=reports.messages.CorosyncQuorumWillBeLost(),
                    )
                )
        elif failures or not targets_to_remove:
            report_processor.report(
                ReportItem(
                    severity=reports.item.get_severity(
                        report_codes.FORCE,
                        force_quorum_loss,
                    ),
                    message=reports.messages.CorosyncQuorumLossUnableToCheck(),
                )
            )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    unknown_to_remove = [name for name in unknown_nodes if name in node_list]
    if unknown_to_remove:
        report_processor.report(
            ReportItem.warning(
                reports.messages.NodesToRemoveUnreachable(
                    sorted(unknown_to_remove)
                )
            )
        )
    if targets_to_remove:
        com_cmd = cluster.DestroyWarnOnFailure(report_processor)
        com_cmd.set_targets(targets_to_remove)
        run_and_raise(env.get_node_communicator(), com_cmd)

    corosync_conf.remove_nodes(node_list)
    if atb_has_to_be_enabled:
        corosync_conf.set_quorum_options(dict(auto_tie_breaker="1"))

    _verify_corosync_conf(corosync_conf)  # raises if corosync not valid
    com_cmd = DistributeCorosyncConf(
        env.report_processor,
        corosync_conf.config.export(),
        allow_skip_offline=False,
    )
    com_cmd.set_targets(staying_online_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = ReloadCorosyncConf(env.report_processor)
    com_cmd.set_targets(staying_online_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # try to remove nodes from pcmk using crm_node -R <node> --force and if not
    # successful remove it directly from CIB file on all nodes in parallel
    com_cmd = RemoveNodesFromCib(env.report_processor, node_list)
    com_cmd.set_targets(staying_online_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def remove_nodes_from_cib(env: LibraryEnvironment, node_list):
    """
    Remove specified nodes from CIB. When pcmk is running 'crm_node -R <node>'
    will be used. Otherwise nodes will be removed directly from CIB file.

    env LibraryEnvironment
    node_list iterable -- names of nodes to remove
    """
    # TODO: more advanced error handling
    if not env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired([file_type_codes.CIB])
            )
        )

    if env.service_manager.is_running("pacemaker"):
        for node in node_list:
            # this may raise a LibraryError
            # NOTE: crm_node cannot remove multiple nodes at once
            remove_node(env.cmd_runner(), node)
        return

    # TODO: We need to remove nodes from the CIB file. We don't want to do it
    # using environment as this is a special case in which we have to edit CIB
    # file directly.
    for node in node_list:
        stdout, stderr, retval = env.cmd_runner().run(
            [
                settings.cibadmin_exec,
                "--delete-all",
                "--force",
                f"--xpath=/cib/configuration/nodes/node[@uname='{node}']",
            ],
            env_extend={"CIB_file": os.path.join(settings.cib_dir, "cib.xml")},
        )
        if retval != 0:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.NodeRemoveInPacemakerFailed(
                        node_list_to_remove=[node],
                        reason=join_multilines([stderr, stdout]),
                    )
                )
            )


def add_link(
    env: LibraryEnvironment,
    node_addr_map,
    link_options=None,
    force_flags: Collection[reports.types.ForceCode] = (),
):
    """
    Add a corosync link to a cluster

    env LibraryEnvironment
    dict node_addr_map -- key: node name, value: node address for the link
    dict link_options -- link options
    force_flags list -- list of flags codes
    """
    _ensure_live_env(env)  # raises if env is not live

    link_options = link_options or {}
    force = report_codes.FORCE in force_flags
    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    corosync_conf = env.get_corosync_conf()

    # validations

    dummy_cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        corosync_conf,
        # New link addresses are assigned to nodes based on node names. If
        # there are nodes with no names, we cannot assign them new link
        # addresses. This is a no-go situation.
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)

    try:
        cib = env.get_cib()
        cib_nodes = get_remote_nodes(cib) + get_guest_nodes(cib)
    except LibraryError:
        cib_nodes = []
        report_processor.report(
            ReportItem(
                reports.item.get_severity(report_codes.FORCE, force),
                reports.messages.CibLoadErrorGetNodesForValidation(),
            )
        )

    report_processor.report_list(
        config_validators.add_link(
            node_addr_map,
            link_options,
            corosync_conf.get_nodes(),
            cib_nodes,
            [str(num) for num in corosync_conf.get_used_linknumber_list()],
            corosync_conf.get_transport(),
            corosync_conf.get_ip_version(),
            force_unresolvable=force,
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    corosync_conf.add_link(node_addr_map, link_options)
    env.push_corosync_conf(corosync_conf, skip_offline)


def remove_links(
    env: LibraryEnvironment,
    linknumber_list,
    force_flags: Collection[reports.types.ForceCode] = (),
):
    """
    Remove corosync links from a cluster

    env LibraryEnvironment
    iterable linknumber_list -- linknumbers (as strings) of links to be removed
    force_flags list -- list of flags codes
    """
    # TODO library interface should make sure linknumber_list is an iterable of
    # strings. The layer in which the check should be done does not exist yet.
    _ensure_live_env(env)  # raises if env is not live

    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    corosync_conf = env.get_corosync_conf()

    # validations

    report_processor.report_list(
        config_validators.remove_links(
            linknumber_list,
            [str(num) for num in corosync_conf.get_used_linknumber_list()],
            corosync_conf.get_transport(),
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    corosync_conf.remove_links(linknumber_list)

    env.push_corosync_conf(corosync_conf, skip_offline)


def update_link(
    env: LibraryEnvironment,
    linknumber,
    node_addr_map=None,
    link_options=None,
    force_flags: Collection[reports.types.ForceCode] = (),
):
    """
    Change an existing corosync link

    env LibraryEnvironment
    string linknumber -- the link to be changed
    dict node_addr_map -- key: node name, value: node address for the link
    dict link_options -- link options
    force_flags list -- list of flags codes
    """
    _ensure_live_env(env)  # raises if env is not live

    node_addr_map = node_addr_map or {}
    link_options = link_options or {}
    force = report_codes.FORCE in force_flags
    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    corosync_conf = env.get_corosync_conf()

    # validations

    dummy_cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        corosync_conf,
        # Pcs is unable to communicate with nodes missing names. It cannot send
        # new corosync.conf to them. That might break the cluster. Hence we
        # error out.
        # This check is done later as well, when sending corosync.conf to
        # nodes. But we need node names to be present so we can set new
        # addresses to them. We may as well do the check right now.
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)

    report_processor.report_list(
        config_validators.update_link(
            linknumber,
            node_addr_map,
            link_options,
            corosync_conf.get_links_options().get(linknumber, {}),
            corosync_conf.get_nodes(),
            # cluster must be stopped for updating a link and then we cannot get
            # nodes from CIB
            [],
            [str(num) for num in corosync_conf.get_used_linknumber_list()],
            corosync_conf.get_transport(),
            corosync_conf.get_ip_version(),
            force_unresolvable=force,
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    corosync_conf.update_link(linknumber, node_addr_map, link_options)
    env.push_corosync_conf(corosync_conf, skip_offline)


def corosync_authkey_change(
    env: LibraryEnvironment,
    corosync_authkey: Optional[bytes] = None,
    force_flags: Collection[reports.types.ForceCode] = (),
) -> None:
    """
    Distribute new corosync authkey to all cluster nodes.

    env -- LibraryEnvironment
    corosync_authkey -- new authkey; if None, generate a random one
    force_flags -- list of flags codes
    """
    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()

    cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        env.get_corosync_conf(),
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)
    (
        target_report_list,
        cluster_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        cluster_nodes_names,
        allow_skip=False,
    )
    report_processor.report_list(target_report_list)
    if corosync_authkey is not None:
        if len(corosync_authkey) != settings.corosync_authkey_bytes:
            report_processor.report(
                ReportItem(
                    severity=reports.item.get_severity(
                        report_codes.FORCE,
                        report_codes.FORCE in force_flags,
                    ),
                    message=reports.messages.CorosyncAuthkeyWrongLength(
                        len(corosync_authkey),
                        settings.corosync_authkey_bytes,
                        settings.corosync_authkey_bytes,
                    ),
                )
            )
    else:
        corosync_authkey = generate_binary_key(
            random_bytes_count=settings.corosync_authkey_bytes
        )

    if report_processor.has_errors:
        raise LibraryError()

    com_cmd: AllSameDataMixin = GetOnlineTargets(
        report_processor,
        ignore_offline_targets=report_codes.SKIP_OFFLINE_NODES in force_flags,
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    online_cluster_target_list = run_and_raise(
        env.get_node_communicator(), com_cmd
    )

    if not online_cluster_target_list:
        if report_processor.report(
            ReportItem.error(
                reports.messages.UnableToPerformOperationOnAnyNode()
            )
        ).has_errors:
            raise LibraryError()

    com_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.corosync_authkey_file(corosync_authkey),
    )
    com_cmd.set_targets(online_cluster_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = ReloadCorosyncConf(env.report_processor)
    com_cmd.set_targets(online_cluster_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def _generate_cluster_uuid(
    corosync_conf: config_facade.ConfigFacade, is_forced: bool
) -> Tuple[ReportItemList, config_facade.ConfigFacade]:
    report_list = []
    if corosync_conf.get_cluster_uuid():
        report_list.append(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    report_codes.FORCE, is_forced
                ),
                message=reports.messages.ClusterUuidAlreadySet(),
            )
        )
        if not is_forced:
            return report_list, corosync_conf

    corosync_conf.set_cluster_uuid(generate_uuid())
    return report_list, corosync_conf


def generate_cluster_uuid(
    env: LibraryEnvironment,
    force_flags: Collection[reports.types.ForceCode] = (),
) -> None:
    """
    Add or update cluster UUID in live cluster

    env
    """
    _ensure_live_env(env)
    corosync_conf = env.get_corosync_conf()
    report_list, corosync_conf = _generate_cluster_uuid(
        corosync_conf, report_codes.FORCE in force_flags
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    env.push_corosync_conf(corosync_conf)


def generate_cluster_uuid_local(
    env: LibraryEnvironment,
    corosync_conf_content: bytes,
    force_flags: Collection[reports.types.ForceCode] = (),
) -> bytes:
    """
    Add or update cluster UUID in corosync.conf passed as an argument and return
    the updated config

    env
    corosync_conf_content -- corosync.conf to be updated
    """
    _ensure_live_env(env)
    corosync_conf_instance = FileInstance.for_corosync_conf()
    try:
        corosync_conf: config_facade.ConfigFacade = cast(
            config_facade.ConfigFacade,
            corosync_conf_instance.raw_to_facade(corosync_conf_content),
        )
    except ParserErrorException as e:
        if env.report_processor.report_list(
            corosync_conf_instance.toolbox.parser.exception_to_report_list(
                e,
                corosync_conf_instance.toolbox.file_type_code,
                None,
                force_code=None,
                is_forced_or_warning=False,
            )
        ).has_errors:
            raise LibraryError() from e

    report_list, corosync_conf = _generate_cluster_uuid(
        corosync_conf, report_codes.FORCE in force_flags
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    return corosync_conf_instance.facade_to_raw(corosync_conf)


def wait_for_pcmk_idle(env: LibraryEnvironment, wait_value: WaitType) -> None:
    """
    Wait for the cluster to settle into stable state.

    env
    wait_value -- value describing the timeout the command
    """
    timeout = env.ensure_wait_satisfiable(wait_value)
    env.wait_for_idle(timeout)
