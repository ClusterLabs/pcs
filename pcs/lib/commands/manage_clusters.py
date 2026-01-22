from typing import Sequence, cast

from pcs.common import reports
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS, PCS_SETTINGS_CONF
from pcs.common.host import PcsKnownHost
from pcs.common.node_communicator import Communicator, RequestTarget
from pcs.lib.communication.corosync import GetClusterInfoFromStatus
from pcs.lib.communication.nodes import GetClusterKnownHosts
from pcs.lib.communication.tools import run
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import RawFileError, raw_file_error_report
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.save_sync import (
    save_sync_new_known_hosts,
    save_sync_new_version,
)
from pcs.lib.permissions.config.facade import FacadeV2 as PcsSettingsFacade
from pcs.lib.permissions.config.types import ClusterEntry


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

    pcs_settings_conf, report_list = __read_pcs_settings()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    if pcs_settings_conf.is_cluster_name_in_use(cluster_name):
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.ClusterNameAlreadyInUse(cluster_name)
            )
        )
        raise LibraryError()

    # we want to continue even when not able to get the known hosts
    # so we are overriding all of the communication errors to be warnings in
    # this case
    get_cluster_known_hosts_cmd = GetClusterKnownHosts(
        env.report_processor, cluster_name, force_all_errors=True
    )
    get_cluster_known_hosts_cmd.set_targets(remote_request_targets)
    new_hosts = run(node_communicator, get_cluster_known_hosts_cmd)

    is_in_cluster = FileInstance.for_corosync_conf().raw_file.exists()

    if is_in_cluster:
        corosync_conf = env.get_corosync_conf()
        local_cluster_name = corosync_conf.get_cluster_name()
        # TODO: should probably send to remote nodes as well (defined in cib)
        # this was previously not done, so we are keeping it this way
        local_corosync_nodes, _ = get_existing_nodes_names(corosync_conf)
        local_request_targets = env.get_node_target_factory().get_target_list(
            local_corosync_nodes
        )

    if new_hosts:
        known_hosts, report_list = __read_known_hosts()
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        if is_in_cluster:
            __sync_known_hosts_in_cluster(
                known_hosts,
                new_hosts,
                local_cluster_name,
                local_request_targets,
                node_communicator,
                env.report_processor,
            )
        else:
            __update_known_hosts_locally(
                known_hosts, new_hosts, env.report_processor
            )

    if env.report_processor.has_errors:
        raise LibraryError()

    new_cluster_entry = ClusterEntry(cluster_name, cluster_nodes)
    if is_in_cluster:
        __sync_pcs_settings_in_cluster(
            pcs_settings_conf,
            new_cluster_entry,
            local_cluster_name,
            local_request_targets,
            node_communicator,
            env.report_processor,
        )
    else:
        __update_pcs_settings_locally(
            pcs_settings_conf, new_cluster_entry, env.report_processor
        )

    if env.report_processor.has_errors:
        raise LibraryError()


def __read_pcs_settings() -> tuple[PcsSettingsFacade, reports.ReportItemList]:
    file_instance = FileInstance.for_pcs_settings_config()
    report_list: reports.ReportItemList = []
    if not file_instance.raw_file.exists():
        return PcsSettingsFacade.create(data_version=0), report_list

    try:
        return cast(
            PcsSettingsFacade, file_instance.read_to_facade()
        ), report_list
    except RawFileError as e:
        report_list.append(raw_file_error_report(e))
    except ParserErrorException as e:
        report_list.extend(file_instance.parser_exception_to_report_list(e))
    return PcsSettingsFacade.create(), report_list


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
    return KnownHostsFacade.create(), report_list


def __sync_known_hosts_in_cluster(
    known_hosts: KnownHostsFacade,
    new_hosts: Sequence[PcsKnownHost],
    local_cluster_name: str,
    request_targets: Sequence[RequestTarget],
    node_communicator: Communicator,
    report_processor: reports.ReportProcessor,
) -> None:
    conflict_detected, failed_nodes, new_file = save_sync_new_known_hosts(
        known_hosts,
        new_hosts,
        [],
        local_cluster_name,
        request_targets,
        node_communicator,
        report_processor,
    )
    if conflict_detected:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncConflictRepeatAction()
            )
        )
        try:
            if new_file is not None:
                FileInstance.for_known_hosts().write_facade(
                    new_file, can_overwrite=True
                )
        except RawFileError as e:
            report_processor.report(raw_file_error_report(e))

    if failed_nodes:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                    [PCS_KNOWN_HOSTS], sorted(failed_nodes)
                )
            )
        )


def __update_known_hosts_locally(
    known_hosts: KnownHostsFacade,
    new_hosts: Sequence[PcsKnownHost],
    report_processor: reports.ReportProcessor,
) -> None:
    known_hosts.update_known_hosts(new_hosts)
    known_hosts.set_data_version(known_hosts.data_version + 1)

    try:
        FileInstance.for_known_hosts().write_facade(
            known_hosts, can_overwrite=True
        )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))


def __sync_pcs_settings_in_cluster(
    pcs_settings: PcsSettingsFacade,
    new_cluster_entry: ClusterEntry,
    local_cluster_name: str,
    request_targets: Sequence[RequestTarget],
    node_communicator: Communicator,
    report_processor: reports.ReportProcessor,
) -> None:
    pcs_settings.add_cluster(new_cluster_entry)
    conflict_detected, failed_nodes, new_file = save_sync_new_version(
        PCS_SETTINGS_CONF,
        pcs_settings,
        local_cluster_name,
        request_targets,
        node_communicator,
        report_processor,
        fetch_on_conflict=True,
        reject_is_error=True,
    )
    if conflict_detected:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncConflictRepeatAction()
            )
        )
        try:
            if new_file is not None:
                FileInstance.for_pcs_settings_config().write_facade(
                    new_file, can_overwrite=True
                )
        except RawFileError as e:
            report_processor.report(raw_file_error_report(e))

    if failed_nodes:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                    [PCS_SETTINGS_CONF], sorted(failed_nodes)
                )
            )
        )


def __update_pcs_settings_locally(
    pcs_settings_conf: PcsSettingsFacade,
    new_cluster_entry: ClusterEntry,
    report_processor: reports.ReportProcessor,
) -> None:
    pcs_settings_conf.add_cluster(new_cluster_entry)
    pcs_settings_conf.set_data_version(pcs_settings_conf.data_version + 1)
    try:
        FileInstance.for_pcs_settings_config().write_facade(
            pcs_settings_conf, can_overwrite=True
        )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
