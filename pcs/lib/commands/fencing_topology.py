from typing import Optional

from pcs.common.types import StringCollection
from pcs.lib.cib import fencing_topology as cib_fencing_topology
from pcs.lib.cib.tools import (
    get_fencing_topology,
    get_resources,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import ClusterState


def add_level(
    lib_env: LibraryEnvironment,
    level,
    target_type,
    target_value,
    devices,
    force_device=False,
    force_node=False,
):
    """
    Validate and add a new fencing level

    LibraryEnvironment lib_env -- environment
    int|string level -- level (index) of the new fencing level
    constant target_type -- the new fencing level target value type
    mixed target_value -- the new fencing level target value
    Iterable devices -- list of stonith devices for the new fencing level
    bool force_device -- continue even if a stonith device does not exist
    bool force_node -- continue even if a node (target) does not exist
    """
    cib = lib_env.get_cib()
    cib_fencing_topology.add_level(
        lib_env.report_processor,
        get_fencing_topology(cib),
        get_resources(cib),
        level,
        target_type,
        target_value,
        devices,
        ClusterState(lib_env.get_cluster_state()).node_section.nodes,
        force_device,
        force_node,
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()
    lib_env.push_cib()


def get_config(lib_env: LibraryEnvironment):
    """
    Get fencing levels configuration.

    Return a list of levels where each level is a dict with keys: target_type,
    target_value. level and devices. Devices is a list of stonith device ids.

    LibraryEnvironment lib_env -- environment
    """
    cib = lib_env.get_cib()
    return cib_fencing_topology.export(get_fencing_topology(cib))


def remove_all_levels(lib_env: LibraryEnvironment):
    """
    Remove all fencing levels
    LibraryEnvironment lib_env -- environment
    """
    cib_fencing_topology.remove_all_levels(
        get_fencing_topology(lib_env.get_cib())
    )
    lib_env.push_cib()


def remove_levels_by_params(
    lib_env: LibraryEnvironment,
    level=None,
    # TODO create a special type, so that it cannot accept any string
    target_type: Optional[str] = None,
    target_value=None,
    devices: Optional[StringCollection] = None,
):
    """
    Remove specified fencing level(s).

    LibraryEnvironment lib_env -- environment
    int|string level -- level (index) of the fencing level to remove
    target_type -- the removed fencing level target value type
    mixed target_value -- the removed fencing level target value
    devices -- list of stonith devices of the removed fencing level
    """
    topology_el = get_fencing_topology(lib_env.get_cib())
    report_list = cib_fencing_topology.remove_levels_by_params(
        topology_el,
        level,
        target_type,
        target_value,
        devices,
    )
    if lib_env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    lib_env.push_cib()


def verify(lib_env: LibraryEnvironment):
    """
    Check if all cluster nodes and stonith devices used in fencing levels exist

    LibraryEnvironment lib_env -- environment
    """
    cib = lib_env.get_cib()
    lib_env.report_processor.report_list(
        cib_fencing_topology.verify(
            get_fencing_topology(cib),
            get_resources(cib),
            ClusterState(lib_env.get_cluster_state()).node_section.nodes,
        )
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()
