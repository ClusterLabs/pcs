from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.node import CibNodeListDto
from pcs.common.reports.item import ReportItem
from pcs.common.types import StringSequence
from pcs.lib.cib import node
from pcs.lib.cib.node import update_node_instance_attrs
from pcs.lib.cib.rule.in_effect import get_rule_evaluator
from pcs.lib.cib.tools import IdProvider, get_nodes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.live import get_local_node_name
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pacemaker.state import Node as NodeState


@contextmanager
def _cib_runner_nodes(
    lib_env: LibraryEnvironment,
) -> Iterator[tuple[_Element, CommandRunner, list[NodeState]]]:
    yield (
        lib_env.get_cib(),
        lib_env.cmd_runner(),
        ClusterState(lib_env.get_cluster_state()).node_section.nodes,
    )
    lib_env.push_cib()


def standby_unstandby_local(lib_env: LibraryEnvironment, standby: bool) -> None:
    """
    Change local node standby mode

    standby -- True: enable standby, False: disable standby
    """
    _set_instance_attrs_local_node(
        lib_env, _create_standby_unstandby_dict(standby)
    )


def standby_unstandby_list(
    lib_env: LibraryEnvironment,
    standby: bool,
    node_names: StringSequence,
) -> None:
    """
    Change specified nodes standby mode

    standby -- True: enable standby, False: disable standby
    node_names -- nodes to apply the change to
    """
    _set_instance_attrs_node_list(
        lib_env, _create_standby_unstandby_dict(standby), node_names
    )


def standby_unstandby_all(lib_env: LibraryEnvironment, standby: bool) -> None:
    """
    Change all nodes standby mode

    standby -- True: enable standby, False: disable standby
    """
    _set_instance_attrs_all_nodes(
        lib_env, _create_standby_unstandby_dict(standby)
    )


def maintenance_unmaintenance_local(
    lib_env: LibraryEnvironment, maintenance: bool
) -> None:
    """
    Change local node maintenance mode

    maintenance -- True: enable maintenance, False: disable maintenance
    """
    _set_instance_attrs_local_node(
        lib_env, _create_maintenance_unmaintenance_dict(maintenance)
    )


def maintenance_unmaintenance_list(
    lib_env: LibraryEnvironment,
    maintenance: bool,
    node_names: StringSequence,
) -> None:
    """
    Change specified nodes maintenance mode

    maintenance -- True: enable maintenance, False: disable maintenance
    node_names -- nodes to apply the change to
    """
    _set_instance_attrs_node_list(
        lib_env, _create_maintenance_unmaintenance_dict(maintenance), node_names
    )


def maintenance_unmaintenance_all(
    lib_env: LibraryEnvironment, maintenance: bool
) -> None:
    """
    Change all nodes maintenance mode

    maintenance -- True: enable maintenance, False: disable maintenance
    """
    _set_instance_attrs_all_nodes(
        lib_env, _create_maintenance_unmaintenance_dict(maintenance)
    )


def _create_standby_unstandby_dict(standby: bool) -> dict[str, str]:
    return {"standby": "on" if standby else ""}


def _create_maintenance_unmaintenance_dict(maintenance: bool) -> dict[str, str]:
    return {"maintenance": "on" if maintenance else ""}


def _set_instance_attrs_local_node(
    lib_env: LibraryEnvironment, attrs: Mapping[str, str]
) -> None:
    if not lib_env.is_cib_live:
        # If we are not working with a live cluster we cannot get the local node
        # name.
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequiredForLocalNode()
            )
        )

    with _cib_runner_nodes(lib_env) as (cib, runner, state_nodes):
        update_node_instance_attrs(
            cib,
            IdProvider(cib),
            get_local_node_name(runner),
            attrs,
            state_nodes=state_nodes,
        )


def _set_instance_attrs_node_list(
    lib_env: LibraryEnvironment,
    attrs: Mapping[str, str],
    node_names: StringSequence,
) -> None:
    with _cib_runner_nodes(lib_env) as (cib, dummy_runner, state_nodes):
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
    lib_env: LibraryEnvironment, attrs: Mapping[str, str]
) -> None:
    with _cib_runner_nodes(lib_env) as (cib, dummy_runner, state_nodes):
        for node in [node.attrs.name for node in state_nodes]:
            update_node_instance_attrs(
                cib, IdProvider(cib), node, attrs, state_nodes=state_nodes
            )


def get_config_dto(
    lib_env: LibraryEnvironment, evaluate_expired: bool = False
) -> CibNodeListDto:
    cib = lib_env.get_cib()
    rule_in_effect_eval = get_rule_evaluator(
        cib, lib_env.cmd_runner(), lib_env.report_processor, evaluate_expired
    )
    return CibNodeListDto(
        nodes=[
            node.node_el_to_dto(node_el, rule_eval=rule_in_effect_eval)
            for node_el in node.get_all_node_elements(get_nodes(cib))
        ]
    )
