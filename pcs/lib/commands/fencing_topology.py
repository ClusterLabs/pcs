from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.common.fencing_topology import (
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.lib.cib import fencing_topology as cib_fencing_topology
from pcs.lib.cib.tools import (
    get_fencing_topology,
    get_resources,
)
from pcs.lib.pacemaker.live import get_cluster_status_xml
from pcs.lib.pacemaker.state import ClusterState

def add_level(
    lib_env, level, target_type, target_value, devices,
    force_device=False, force_node=False
):
    """
    Validate and add a new fencing level

    LibraryError lib_env -- environment
    int|string level -- level (index) of the new fencing level
    constant target_type -- the new fencing level target value type
    mixed target_value -- the new fencing level target value
    Iterable devices -- list of stonith devices for the new fencing level
    bool force_device -- continue even if a stonith device does not exist
    bool force_node -- continue even if a node (target) does not exist
    """
    version_check = None
    if target_type == TARGET_TYPE_REGEXP:
        version_check = (2, 3, 0)
    elif target_type == TARGET_TYPE_ATTRIBUTE:
        version_check = (2, 4, 0)

    cib = lib_env.get_cib(version_check)
    cib_fencing_topology.add_level(
        lib_env.report_processor,
        get_fencing_topology(cib),
        get_resources(cib),
        level,
        target_type,
        target_value,
        devices,
        ClusterState(
            get_cluster_status_xml(lib_env.cmd_runner())
        ).node_section.nodes,
        force_device,
        force_node
    )
    lib_env.report_processor.send()
    lib_env.push_cib(cib)

def get_config(lib_env):
    """
    Get fencing levels configuration.

    Return a list of levels where each level is a dict with keys: target_type,
    target_value. level and devices. Devices is a list of stonith device ids.

    LibraryError lib_env -- environment
    """
    cib = lib_env.get_cib()
    return cib_fencing_topology.export(get_fencing_topology(cib))

def remove_all_levels(lib_env):
    """
    Remove all fencing levels
    LibraryError lib_env -- environment
    """
    cib = lib_env.get_cib()
    cib_fencing_topology.remove_all_levels(get_fencing_topology(cib))
    lib_env.push_cib(cib)

def remove_levels_by_params(
    lib_env, level=None, target_type=None, target_value=None, devices=None,
    ignore_if_missing=False
):
    """
    Remove specified fencing level(s)

    LibraryError lib_env -- environment
    int|string level -- level (index) of the new fencing level
    constant target_type -- the new fencing level target value type
    mixed target_value -- the new fencing level target value
    Iterable devices -- list of stonith devices for the new fencing level
    bool ignore_if_missing -- when True, do not report if level not found
    """
    cib = lib_env.get_cib()
    cib_fencing_topology.remove_levels_by_params(
        lib_env.report_processor,
        get_fencing_topology(cib),
        level,
        target_type,
        target_value,
        devices,
        ignore_if_missing
    )
    lib_env.report_processor.send()
    lib_env.push_cib(cib)

def verify(lib_env):
    """
    Check if all cluster nodes and stonith devices used in fencing levels exist

    LibraryError lib_env -- environment
    """
    cib = lib_env.get_cib()
    cib_fencing_topology.verify(
        lib_env.report_processor,
        get_fencing_topology(cib),
        get_resources(cib),
        ClusterState(
            get_cluster_status_xml(lib_env.cmd_runner())
        ).node_section.nodes
    )
    lib_env.report_processor.send()
