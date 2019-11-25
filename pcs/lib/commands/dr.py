from pcs.common.reports import SimpleReportProcessor
from pcs.common import file_type_codes

from pcs.lib import node_communication_format, reports
from pcs.lib.communication.corosync import GetCorosyncConf
from pcs.lib.communication.nodes import DistributeFilesWithoutForces
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.dr.config.facade import DrRole
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.file.toolbox import for_file_type as get_file_toolbox
from pcs.lib.node import get_existing_nodes_names


def set_recovery_site(env: LibraryEnvironment, node_name: str) -> None:
    """
    Set up disaster recovery with the local cluster being the primary site

    env
    node_name -- a known host from the recovery site
    """
    if not env.is_corosync_conf_live:
        raise LibraryError(
            reports.live_environment_required([file_type_codes.COROSYNC_CONF])
        )
    report_processor = SimpleReportProcessor(env.report_processor)
    dr_env = env.get_dr_env()
    if dr_env.config.raw_file.exists():
        report_processor.report(reports.dr_config_already_exist())
    target_factory = env.get_node_target_factory()

    local_nodes, report_list = get_existing_nodes_names(
        env.get_corosync_conf(),
        error_on_missing_name=True
    )
    report_processor.report_list(report_list)

    if node_name in local_nodes:
        report_processor.report(reports.node_in_local_cluster(node_name))

    report_list, local_targets = target_factory.get_target_list_with_reports(
        local_nodes, allow_skip=False, report_none_host_found=False
    )
    report_processor.report_list(report_list)

    report_list, remote_targets = (
        target_factory.get_target_list_with_reports(
            [node_name], allow_skip=False, report_none_host_found=False
        )
    )
    report_processor.report_list(report_list)

    if report_processor.has_errors:
        raise LibraryError()

    com_cmd = GetCorosyncConf(env.report_processor)
    com_cmd.set_targets(remote_targets)
    remote_cluster_nodes, report_list = get_existing_nodes_names(
        CorosyncConfigFacade.from_string(
            run_and_raise(env.get_node_communicator(), com_cmd)
        ),
        error_on_missing_name=True
    )
    if report_processor.report_list(report_list):
        raise LibraryError()

    # ensure we have tokens for all nodes of remote cluster
    report_list, remote_targets = target_factory.get_target_list_with_reports(
        remote_cluster_nodes, allow_skip=False, report_none_host_found=False
    )
    if report_processor.report_list(report_list):
        raise LibraryError()
    dr_config_exporter = (
        get_file_toolbox(file_type_codes.PCS_DR_CONFIG).exporter
    )
    # create dr config for remote cluster
    remote_dr_cfg = dr_env.create_facade(DrRole.RECOVERY)
    remote_dr_cfg.add_site(DrRole.PRIMARY, local_nodes)
    # send config to all node of remote cluster
    distribute_file_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.pcs_dr_config_file(
            dr_config_exporter.export(remote_dr_cfg.config)
        )
    )
    distribute_file_cmd.set_targets(remote_targets)
    run_and_raise(env.get_node_communicator(), distribute_file_cmd)
    # create new dr config, with local cluster as primary site
    local_dr_cfg = dr_env.create_facade(DrRole.PRIMARY)
    local_dr_cfg.add_site(DrRole.RECOVERY, remote_cluster_nodes)
    distribute_file_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.pcs_dr_config_file(
            dr_config_exporter.export(local_dr_cfg.config)
        )
    )
    distribute_file_cmd.set_targets(local_targets)
    run_and_raise(env.get_node_communicator(), distribute_file_cmd)
    # Note: No token sync across multiple clusters. Most probably they are in
    # different subnetworks.
