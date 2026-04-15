from typing import Optional

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.cluster_dto import (
    ClusterComponentVersionDto,
    ClusterDaemonsInfoDto,
)
from pcs.common.services_dto import ServiceStatusDto
from pcs.common.str_tools import join_multilines
from pcs.common.tools import Version, get_version_from_string
from pcs.common.version_dto import VersionDto
from pcs.lib import sbd
from pcs.lib.cib.node_rename import rename_in_cib
from pcs.lib.commands.cluster.utils import ensure_live_env, verify_corosync_conf
from pcs.lib.communication import cluster
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    DistributeCorosyncConf,
    ReloadCorosyncConf,
)
from pcs.lib.communication.nodes import GetOnlineTargets, RemoveNodesFromCib
from pcs.lib.communication.tools import AllSameDataMixin, run_and_raise
from pcs.lib.communication.tools import run as run_com
from pcs.lib.corosync import config_validators
from pcs.lib.corosync.live import get_corosync_version
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.live import (
    get_cib_file_runner_env,
    get_pacemaker_version,
    has_cib_xml,
    remove_node,
)


def node_clear(
    env: LibraryEnvironment,
    node_name: str,
    allow_clear_cluster_node: bool = False,
) -> None:
    """
    Remove specified node from various cluster caches.

    allow_clear_cluster_node -- flag allows to clear node even if it's
        still in a cluster
    """
    ensure_live_env(env)  # raises if env is not live

    current_nodes, report_list = get_existing_nodes_names(
        env.get_corosync_conf(), env.get_cib()
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    if node_name in current_nodes:
        env.report_processor.report(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE,
                    allow_clear_cluster_node,
                ),
                message=reports.messages.NodeToClearIsStillInCluster(node_name),
            )
        )
        if env.report_processor.has_errors:
            raise LibraryError()

    remove_node(env.cmd_runner(), node_name)


def remove_nodes(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    node_list,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Remove nodes from a cluster.

    env LibraryEnvironment
    node_list iterable -- names of nodes to remove
    force_flags list -- list of flags codes
    """
    ensure_live_env(env)  # raises if env is not live

    force_quorum_loss = reports.codes.FORCE in force_flags
    skip_offline = reports.codes.SKIP_OFFLINE_NODES in force_flags

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
            reports.ReportItem.error(
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
                reports.ReportItem.warning(
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
                reports.ReportItem.error(
                    reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning()
                )
            )
        else:
            report_processor.report(
                reports.ReportItem.warning(
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
                    reports.ReportItem(
                        severity=reports.item.get_severity(
                            reports.codes.FORCE,
                            force_quorum_loss,
                        ),
                        message=reports.messages.CorosyncQuorumWillBeLost(),
                    )
                )
        elif failures or not targets_to_remove:
            report_processor.report(
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        reports.codes.FORCE,
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
            reports.ReportItem.warning(
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

    verify_corosync_conf(corosync_conf)  # raises if corosync not valid
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


def remove_nodes_from_cib(env: LibraryEnvironment, node_list) -> None:
    """
    Remove specified nodes from CIB. When pcmk is running 'crm_node -R <node>'
    will be used. Otherwise nodes will be removed directly from CIB file.

    env LibraryEnvironment
    node_list iterable -- names of nodes to remove
    """
    # TODO: more advanced error handling
    if not env.is_cib_live:
        raise LibraryError(
            reports.ReportItem.error(
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
            env_extend=get_cib_file_runner_env(),
        )
        if retval != 0:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.NodeRemoveInPacemakerFailed(
                        node_list_to_remove=[node],
                        reason=join_multilines([stderr, stdout]),
                    )
                )
            )


def rename_node_cib(
    env: LibraryEnvironment,
    old_name: str,
    new_name: str,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Rename a cluster node in CIB configuration elements.

    old_name -- current node name
    new_name -- new node name
    """

    if old_name == new_name:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.NodeRenameNamesEqual(old_name)
            )
        )
        raise LibraryError()

    if env.is_cib_live:
        if not env.is_corosync_conf_live:
            env.report_processor.report(
                reports.ReportItem.error(
                    reports.messages.LiveEnvironmentNotConsistent(
                        [file_type_codes.COROSYNC_CONF],
                        [file_type_codes.CIB],
                    )
                )
            )
            raise LibraryError()
        corosync_node_names, corosync_nodes_report_list = (
            get_existing_nodes_names(env.get_corosync_conf())
        )
        force_severity = reports.item.get_severity(
            reports.codes.FORCE,
            reports.codes.FORCE in force_flags,
        )
        if new_name not in corosync_node_names:
            corosync_nodes_report_list.append(
                reports.ReportItem(
                    severity=force_severity,
                    message=reports.messages.CibNodeRenameNewNodeNotInCorosync(
                        new_name=new_name,
                    ),
                )
            )
        if old_name in corosync_node_names:
            corosync_nodes_report_list.append(
                reports.ReportItem(
                    severity=force_severity,
                    message=reports.messages.CibNodeRenameOldNodeInCorosync(
                        old_name=old_name,
                    ),
                )
            )

        env.report_processor.report_list(corosync_nodes_report_list)

    if env.report_processor.has_errors:
        raise LibraryError()

    cib = env.get_cib()
    cib_updated, report_list = rename_in_cib(cib, old_name, new_name)
    env.report_processor.report_list(report_list)

    if cib_updated:
        env.push_cib()
        return

    env.report_processor.report(
        reports.ReportItem.info(reports.messages.CibNodeRenameNoChange())
    )


def rename_node_corosync(
    env: LibraryEnvironment,
    old_name: str,
    new_name: str,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Rename a cluster node in corosync.conf and distribute it to all nodes.

    old_name -- current node name
    new_name -- new node name
    """
    if old_name == new_name:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.NodeRenameNamesEqual(old_name)
            )
        )
        raise LibraryError()

    if not env.is_corosync_conf_live:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.LiveEnvironmentRequired(
                    [file_type_codes.COROSYNC_CONF]
                )
            )
        )
        raise LibraryError()

    corosync_conf = env.get_corosync_conf()
    corosync_node_names, corosync_nodes_report_list = get_existing_nodes_names(
        corosync_conf
    )
    if old_name not in corosync_node_names:
        corosync_nodes_report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncNodeRenameOldNodeNotFound(old_name)
            )
        )
    if new_name in corosync_node_names:
        corosync_nodes_report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncNodeRenameNewNodeAlreadyExists(
                    new_name
                )
            )
        )
    env.report_processor.report_list(corosync_nodes_report_list)

    if env.report_processor.has_errors:
        raise LibraryError()

    rename_report_list = corosync_conf.rename_node(old_name, new_name)
    env.report_processor.report_list(rename_report_list)
    env.push_corosync_conf(
        corosync_conf,
        skip_offline_nodes=(reports.codes.SKIP_OFFLINE_NODES in force_flags),
    )


def get_host_daemons_info(env: LibraryEnvironment) -> ClusterDaemonsInfoDto:
    def _version_to_dto(version: Optional[Version]) -> VersionDto:
        return (
            VersionDto(*version.as_full_tuple)
            if version
            else VersionDto(0, 0, 0)
        )

    all_cluster_services = [
        "booth",
        "corosync",
        "corosync-qdevice",
        "pacemaker",
        "pacemaker_remote",
        "pcsd",
        "sbd",
    ]

    return ClusterDaemonsInfoDto(
        cluster_configuration_exists=(env.has_corosync_conf or has_cib_xml()),
        services=[
            ServiceStatusDto(
                service=service,
                installed=env.service_manager.is_installed(service),
                enabled=env.service_manager.is_enabled(service),
                running=env.service_manager.is_running(service),
            )
            for service in all_cluster_services
        ],
        versions=ClusterComponentVersionDto(
            corosync=_version_to_dto(get_corosync_version(env.cmd_runner())),
            pacemaker=_version_to_dto(get_pacemaker_version(env.cmd_runner())),
            pcsd=_version_to_dto(get_version_from_string(settings.pcs_version)),
        ),
    )
