from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.tools import (
    get_fencing_topology,
    get_resources,
)
from pcs.lib.env_tools import get_nodes
from pcs.lib.errors import LibraryError
from pcs.lib.node import (
    node_addresses_contain_name,
    node_addresses_contain_host,
)
from pcs.lib.pacemaker.live import (
    get_cib,
    get_cib_xml,
    get_cib_xml_cmd_results,
    get_cluster_status_xml,
    remove_node,
    verify as verify_cmd,
)
from pcs.lib.pacemaker.state import ClusterState


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

def verify(env, verbose=False):
    runner = env.cmd_runner()
    dummy_stdout, verify_stderr, verify_returncode = verify_cmd(
        runner,
        verbose=verbose,
        cib_content=None if env.is_cib_live else env.initial_mocked_cib_content
    )

    #1) Do not even try to think about upgrading!
    #2) We do not need cib management in env (no need for push...).
    #So env.get_cib is not best choice here (there were considerations to
    #upgrade cib at all times inside env.get_cib). Go to a lower level here.
    if verify_returncode != 0:
        env.report_processor.append(reports.invalid_cib_content(verify_stderr))

        #Cib is sometimes loadable even if `crm_verify` fails (e.g. when
        #fencing topology is invalid). On the other hand cib with id duplication
        #is not loadable.
        #We try extra checks when cib is possible to load.
        cib_xml, dummy_stderr, returncode = get_cib_xml_cmd_results(runner)
        if returncode != 0:
            #can raise; raise LibraryError is better but in this case we prefer
            #be consistent with raising below
            env.report_processor.send()
    else:
        cib_xml = get_cib_xml(runner)

    cib = get_cib(cib_xml)
    fencing_topology.verify(
        env.report_processor,
        get_fencing_topology(cib),
        get_resources(cib),
        ClusterState(get_cluster_status_xml(runner)).node_section.nodes
    )
    #can raise
    env.report_processor.send()
