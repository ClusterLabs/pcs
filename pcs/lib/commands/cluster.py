from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.env_tools import get_nodes
from pcs.lib.errors import LibraryError
from pcs.lib.node import (
    node_addresses_contain_name,
    node_addresses_contain_host,
)
from pcs.lib.pacemaker.live import remove_node


def node_clear(env, node_name, allow_clear_cluster_node=False):
    """
    Remove specified node from various cluster caches.

    LibraryEnvironment env provides all for communication with externals
    string node_name
    bool allow_clear_cluster_node -- flag allows to clear node even if it's
        still in a cluster
    """
    mocked_envs = []
    if not env.is_cib_live:
        mocked_envs.append("CIB")
    if not env.is_corosync_conf_live:
        mocked_envs.append("COROSYNC_CONF")
    if mocked_envs:
        raise LibraryError(reports.live_environment_required(mocked_envs))

    current_nodes = get_nodes(env.get_corosync_conf(), env.get_cib())
    if(
        node_addresses_contain_name(current_nodes, node_name)
        or
        node_addresses_contain_host(current_nodes, node_name)
    ):
        env.report_processor.process(
            reports.get_problem_creator(
                report_codes.FORCE_CLEAR_CLUSTER_NODE,
                allow_clear_cluster_node
            )(
                reports.node_to_clear_is_still_in_cluster,
                node_name
            )
        )

    remove_node(env.cmd_runner(), node_name)
