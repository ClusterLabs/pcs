from contextlib import contextmanager

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.node import update_node_instance_attrs
from pcs.lib.cib.tools import IdProvider
from pcs.lib.env import (
    LibraryEnvironment,
    WaitType,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import get_local_node_name
from pcs.lib.pacemaker.state import ClusterState


@contextmanager
def cib_runner_nodes(lib_env: LibraryEnvironment, wait: WaitType):
    wait_timeout = lib_env.ensure_wait_satisfiable(wait)
    yield (
        lib_env.get_cib(),
        lib_env.cmd_runner(),
        ClusterState(lib_env.get_cluster_state()).node_section.nodes,
    )
    lib_env.push_cib(wait_timeout=wait_timeout)


def standby_unstandby_local(
    lib_env: LibraryEnvironment, standby, wait: WaitType = False
):
    """
    Change local node standby mode

    LibraryEnvironment lib_env
    bool standby -- True: enable standby, False: disable standby
    mixed wait -- False: no wait, None: wait with default timeout, str or int:
        wait with specified timeout
    """
    return _set_instance_attrs_local_node(
        lib_env, _create_standby_unstandby_dict(standby), wait
    )


def standby_unstandby_list(
    lib_env: LibraryEnvironment, standby, node_names, wait: WaitType = False
):
    """
    Change specified nodes standby mode

    LibraryEnvironment lib_env
    bool standby -- True: enable standby, False: disable standby
    iterable node_names -- nodes to apply the change to
    mixed wait -- False: no wait, None: wait with default timeout, str or int:
        wait with specified timeout
    """
    return _set_instance_attrs_node_list(
        lib_env, _create_standby_unstandby_dict(standby), node_names, wait
    )


def standby_unstandby_all(
    lib_env: LibraryEnvironment, standby, wait: WaitType = False
):
    """
    Change all nodes standby mode

    LibraryEnvironment lib_env
    bool standby -- True: enable standby, False: disable standby
    mixed wait -- False: no wait, None: wait with default timeout, str or int:
        wait with specified timeout
    """
    return _set_instance_attrs_all_nodes(
        lib_env, _create_standby_unstandby_dict(standby), wait
    )


def maintenance_unmaintenance_local(
    lib_env: LibraryEnvironment, maintenance, wait: WaitType = False
):
    """
    Change local node maintenance mode

    LibraryEnvironment lib_env
    bool maintenance -- True: enable maintenance, False: disable maintenance
    mixed wait -- False: no wait, None: wait with default timeout, str or int:
        wait with specified timeout
    """
    return _set_instance_attrs_local_node(
        lib_env, _create_maintenance_unmaintenance_dict(maintenance), wait
    )


def maintenance_unmaintenance_list(
    lib_env: LibraryEnvironment, maintenance, node_names, wait: WaitType = False
):
    """
    Change specified nodes maintenance mode

    LibraryEnvironment lib_env
    bool maintenance -- True: enable maintenance, False: disable maintenance
    iterable node_names -- nodes to apply the change to
    mixed wait -- False: no wait, None: wait with default timeout, str or int:
        wait with specified timeout
    """
    return _set_instance_attrs_node_list(
        lib_env,
        _create_maintenance_unmaintenance_dict(maintenance),
        node_names,
        wait,
    )


def maintenance_unmaintenance_all(
    lib_env: LibraryEnvironment, maintenance, wait: WaitType = False
):
    """
    Change all nodes maintenance mode

    LibraryEnvironment lib_env
    bool maintenance -- True: enable maintenance, False: disable maintenance
    mixed wait -- False: no wait, None: wait with default timeout, str or int:
        wait with specified timeout
    """
    return _set_instance_attrs_all_nodes(
        lib_env, _create_maintenance_unmaintenance_dict(maintenance), wait
    )


def _create_standby_unstandby_dict(standby):
    return {"standby": "on" if standby else ""}


def _create_maintenance_unmaintenance_dict(maintenance):
    return {"maintenance": "on" if maintenance else ""}


def _set_instance_attrs_local_node(
    lib_env: LibraryEnvironment, attrs, wait: WaitType
):
    if not lib_env.is_cib_live:
        # If we are not working with a live cluster we cannot get the local node
        # name.
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequiredForLocalNode()
            )
        )

    with cib_runner_nodes(lib_env, wait) as (cib, runner, state_nodes):
        update_node_instance_attrs(
            cib,
            IdProvider(cib),
            get_local_node_name(runner),
            attrs,
            state_nodes=state_nodes,
        )


def _set_instance_attrs_node_list(
    lib_env: LibraryEnvironment, attrs, node_names, wait: WaitType
):
    with cib_runner_nodes(lib_env, wait) as (cib, dummy_runner, state_nodes):
        known_nodes = [node.attrs.name for node in state_nodes]
        report_list = [
            ReportItem.error(reports.messages.NodeNotFound(node))
            for node in node_names
            if node not in known_nodes
        ]
        if report_list:
            raise LibraryError(*report_list)

        for node in node_names:
            update_node_instance_attrs(
                cib, IdProvider(cib), node, attrs, state_nodes=state_nodes
            )


def _set_instance_attrs_all_nodes(
    lib_env: LibraryEnvironment, attrs, wait: WaitType
):
    with cib_runner_nodes(lib_env, wait) as (cib, dummy_runner, state_nodes):
        for node in [node.attrs.name for node in state_nodes]:
            update_node_instance_attrs(
                cib, IdProvider(cib), node, attrs, state_nodes=state_nodes
            )
