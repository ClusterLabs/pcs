from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib.nvpair_multi import NVSET_INSTANCE, find_nvsets
from pcs.lib.cib.resource.primitive import find_primitives_by_agent
from pcs.lib.cib.tools import get_resources
from pcs.lib.commands.cluster.common import ensure_live_env
from pcs.lib.communication import cluster
from pcs.lib.communication.corosync import CheckCorosyncOffline
from pcs.lib.communication.tools import (
    CommunicationCommandInterface,
    run,
    run_and_raise,
)
from pcs.lib.corosync import config_validators
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.live import (
    get_cib,
    get_cib_file_runner_env,
    get_cib_xml,
    has_cib_xml,
)
from pcs.lib.resource_agent.types import ResourceAgentName


def rename(
    env: LibraryEnvironment,
    new_name: str,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Change the name of the local cluster

    new_name -- new name for the cluster
    """

    def warn_dlm_resources(resources: _Element) -> reports.ReportItemList:
        if find_primitives_by_agent(
            resources, ResourceAgentName("ocf", "pacemaker", "controld")
        ):
            return [
                reports.ReportItem.warning(
                    reports.messages.DlmClusterRenameNeeded()
                )
            ]
        return []

    def warn_gfs2_resources(resources: _Element) -> reports.ReportItemList:
        for resource in find_primitives_by_agent(
            resources, ResourceAgentName("ocf", "heartbeat", "Filesystem")
        ):
            for nvset in find_nvsets(resource, NVSET_INSTANCE):
                if any(
                    (
                        nvpair.get("name") == "fstype"
                        and nvpair.get("value") == "gfs2"
                    )
                    for nvpair in nvset
                ):
                    return [
                        reports.ReportItem.warning(
                            reports.messages.Gfs2LockTableRenameNeeded()
                        )
                    ]
        return []

    ensure_live_env(env)

    if env.report_processor.report_list(
        config_validators.rename_cluster(
            new_name, force_cluster_name=reports.codes.FORCE in force_flags
        )
    ).has_errors:
        raise LibraryError()

    cib = None
    if has_cib_xml():
        cib = get_cib(get_cib_xml(env.cmd_runner(get_cib_file_runner_env())))
        resources = get_resources(cib)
        env.report_processor.report_list(warn_dlm_resources(resources))
        env.report_processor.report_list(warn_gfs2_resources(resources))

    corosync_conf = env.get_corosync_conf()
    skip_offline = reports.codes.SKIP_OFFLINE_NODES in force_flags

    corosync_nodes, report_list = get_existing_nodes_names(corosync_conf, None)
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    target_list = env.get_node_target_factory().get_target_list(
        corosync_nodes,
        allow_skip=skip_offline,
    )

    node_communicator = env.get_node_communicator()
    com_cmd: CommunicationCommandInterface

    com_cmd = CheckCorosyncOffline(env.report_processor, skip_offline)
    com_cmd.set_targets(target_list)
    running_targets = run(node_communicator, com_cmd)
    if running_targets:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.CorosyncNotRunningCheckFinishedRunning(
                    [target.label for target in running_targets]
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    # The 'cluster-name' property has to be removed from CIB on all nodes, so
    # that it is initialized with the new cluster name from corosync after the
    # cluster is started
    com_cmd = cluster.RemoveCibClusterName(env.report_processor, skip_offline)
    com_cmd.set_targets(target_list)
    run_and_raise(node_communicator, com_cmd)

    corosync_conf.set_cluster_name(new_name)
    env.push_corosync_conf(corosync_conf, skip_offline)
