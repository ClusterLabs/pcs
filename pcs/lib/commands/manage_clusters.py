from typing import cast

from pcs.common import reports
from pcs.lib.cluster import validations
from pcs.lib.communication.corosync import GetClusterInfoFromStatus
from pcs.lib.communication.nodes import GetClusterKnownHosts
from pcs.lib.communication.tools import run
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import RawFileError, raw_file_error_report
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.sync_files import (
    sync_known_hosts_in_cluster,
    sync_pcs_settings_in_cluster,
    update_known_hosts_locally,
    update_pcs_settings_locally,
)
from pcs.lib.permissions.config.facade import FacadeV2 as PcsSettingsFacade
from pcs.lib.permissions.config.types import ClusterEntry
from pcs.lib.permissions.tools import read_pcs_settings_conf


def add_existing_cluster(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    node_name: str,
) -> None:
    """
    Add an existing cluster to the local pcs configuration for management.

    Contact the specified node to discover cluster details and tokens needed
    for communication with cluster nodes. Update the local pcs_settings and
    known-hosts configuration files. If the local node is in a cluster,
    synchronize the updated configuration files to local cluster nodes.

    node_name -- name of a node from the cluster to be added
    """

    node_communicator = env.get_node_communicator()
    remote_request_targets = env.get_node_target_factory().get_target_list(
        [node_name]
    )

    cluster_info_cmd = GetClusterInfoFromStatus(env.report_processor)
    cluster_info_cmd.set_targets(remote_request_targets)
    cluster_name, cluster_nodes = run(node_communicator, cluster_info_cmd)
    if env.report_processor.has_errors:
        raise LibraryError()

    if not cluster_name:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.NodeNotInCluster(),
                context=reports.ReportItemContext(node_name),
            )
        )
        raise LibraryError()

    pcs_settings_conf, report_list = read_pcs_settings_conf()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    if pcs_settings_conf.is_cluster_name_in_use(cluster_name):
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.ClusterNameAlreadyInUse(cluster_name)
            )
        )
        raise LibraryError()

    # When using the regular node_communicator, we are handling the requests
    # with the permissions of the user that used this lib command, but only
    # hacluster is allowed to do some actions.
    # We already know the hacluster token here, so we allow non-hacluster
    # users to send the request with permission of hacluster
    no_privilege_transition_node_communicator = (
        env.get_node_communicator_no_privilege_transition()
    )

    # we want to continue even when not able to get the known hosts
    # so we are overriding all of the communication errors to be warnings in
    # this case
    get_cluster_known_hosts_cmd = GetClusterKnownHosts(
        env.report_processor, cluster_name, force_all_errors=True
    )
    get_cluster_known_hosts_cmd.set_targets(remote_request_targets)
    new_hosts = run(
        no_privilege_transition_node_communicator, get_cluster_known_hosts_cmd
    )

    is_in_cluster = env.has_corosync_conf
    if is_in_cluster:
        corosync_conf = env.get_corosync_conf()
        local_cluster_name = corosync_conf.get_cluster_name()
        # TODO: should probably send to remote nodes as well (defined in cib)
        # this was previously not done, so we are keeping it this way
        local_corosync_nodes, _ = get_existing_nodes_names(corosync_conf)
        local_request_targets = env.get_node_target_factory().get_target_list(
            local_corosync_nodes, allow_skip=False
        )

    if new_hosts:
        known_hosts, report_list = __read_known_hosts()
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        if is_in_cluster:
            sync_known_hosts_in_cluster(
                known_hosts,
                new_hosts,
                [],
                local_cluster_name,
                local_request_targets,
                no_privilege_transition_node_communicator,
                env.report_processor,
            )
        else:
            update_known_hosts_locally(
                known_hosts, new_hosts, [], env.report_processor
            )

    if env.report_processor.has_errors:
        raise LibraryError()

    pcs_settings_conf.add_cluster(ClusterEntry(cluster_name, cluster_nodes))
    if is_in_cluster:
        sync_pcs_settings_in_cluster(
            pcs_settings_conf,
            local_cluster_name,
            local_request_targets,
            no_privilege_transition_node_communicator,
            env.report_processor,
        )
    else:
        update_pcs_settings_locally(pcs_settings_conf, env.report_processor)

    if env.report_processor.has_errors:
        raise LibraryError()


def add_cluster(
    env: LibraryEnvironment, cluster_name: str, cluster_nodes: list[str]
) -> None:
    """
    Add cluster to local pcsd settings. Synchronize the pcs_settings file to
    all cluster nodes if the local node is in a cluster.

    cluster_name -- name of the new cluster
    cluster_nodes -- names of nodes in the new cluster
    """
    if env.report_processor.report_list(
        validations.validate_add_cluster(cluster_name, cluster_nodes)
    ).has_errors:
        raise LibraryError()

    pcs_settings_conf, report_list = read_pcs_settings_conf()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    if pcs_settings_conf.is_cluster_name_in_use(cluster_name):
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.ClusterNameAlreadyInUse(cluster_name)
            )
        )
        raise LibraryError()

    pcs_settings_conf.add_cluster(ClusterEntry(cluster_name, cluster_nodes))

    __add_remove_clusters_common(env, pcs_settings_conf)


def remove_clusters(
    env: LibraryEnvironment, clusters_to_remove: list[str]
) -> None:
    """
    Remove clusters from local pcsd settings. Synchronize the pcs_settings file
    to all cluster nodes if the local node is in a cluster.

    clusters_to_remove -- names of clusters to be removed
    """
    if env.report_processor.report_list(
        validations.validate_remove_clusters(clusters_to_remove)
    ).has_errors:
        raise LibraryError()

    pcs_settings_conf, report_list = read_pcs_settings_conf()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    for cluster_name in clusters_to_remove:
        pcs_settings_conf.remove_cluster(cluster_name)

    __add_remove_clusters_common(env, pcs_settings_conf)


def __add_remove_clusters_common(
    env: LibraryEnvironment, pcs_settings_conf: PcsSettingsFacade
) -> None:
    """
    Common code for adding and removing clusters, extracted to reduce code
    duplication

    Save the pcs_settings file locally, or synchronize the file to all cluster
    nodes if the local node is in a cluster.
    """
    if not env.has_corosync_conf:
        update_pcs_settings_locally(pcs_settings_conf, env.report_processor)
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    corosync_conf = env.get_corosync_conf()
    cluster_name = corosync_conf.get_cluster_name()
    corosync_nodes, _ = get_existing_nodes_names(corosync_conf)
    request_targets = env.get_node_target_factory().get_target_list(
        corosync_nodes, allow_skip=False
    )

    sync_pcs_settings_in_cluster(
        pcs_settings_conf,
        cluster_name,
        request_targets,
        env.get_node_communicator_no_privilege_transition(),
        env.report_processor,
    )
    if env.report_processor.has_errors:
        raise LibraryError()


def __read_known_hosts() -> tuple[KnownHostsFacade, reports.ReportItemList]:
    file_instance = FileInstance.for_known_hosts()
    report_list: reports.ReportItemList = []

    if not file_instance.raw_file.exists():
        return KnownHostsFacade.create(data_version=0), report_list

    try:
        return cast(
            KnownHostsFacade, file_instance.read_to_facade()
        ), report_list
    except RawFileError as e:
        report_list.append(raw_file_error_report(e))
    except ParserErrorException as e:
        report_list.extend(file_instance.parser_exception_to_report_list(e))
    return KnownHostsFacade.create(data_version=0), report_list
