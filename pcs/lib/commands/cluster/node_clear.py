from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import ReportItem
from pcs.lib.commands.cluster.common import ensure_live_env
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.live import remove_node


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
    ensure_live_env(env)  # raises if env is not live

    current_nodes, report_list = get_existing_nodes_names(
        env.get_corosync_conf(), env.get_cib()
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    if node_name in current_nodes:
        env.report_processor.report(
            ReportItem(
                severity=reports.item.get_severity(
                    report_codes.FORCE,
                    allow_clear_cluster_node,
                ),
                message=reports.messages.NodeToClearIsStillInCluster(node_name),
            )
        )
        if env.report_processor.has_errors:
            raise LibraryError()

    remove_node(env.cmd_runner(), node_name)
