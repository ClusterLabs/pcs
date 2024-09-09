from typing import (
    Any,
    Optional,
)

from pcs.common import reports as report
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    FencingTargetType,
    FencingTargetValue,
)
from pcs.common.pacemaker.fencing_topology import CibFencingTopologyDto
from pcs.common.types import StringSequence
from pcs.lib.cib import fencing_topology as cib_fencing_topology
from pcs.lib.cib.tools import get_fencing_topology
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import ClusterState


def add_level(
    lib_env: LibraryEnvironment,
    level: str,
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
    devices: StringSequence,
    level_id: Optional[str] = None,
    force_device: bool = False,
    force_node: bool = False,
) -> None:
    """
    Validate and add a new fencing level

    lib_env -- environment
    level -- level (index) of the new fencing level
    target_type -- the new fencing level target value type
    target_value -- the new fencing level target value
    devices -- list of stonith devices for the new fencing level
    level_id -- user specified id for the level element
    force_device -- continue even if a stonith device does not exist
    force_node -- continue even if a node (target) does not exist
    """
    cib = lib_env.get_cib()
    cib_fencing_topology.add_level(
        lib_env.report_processor,
        cib,
        level,
        target_type,
        target_value,
        devices,
        ClusterState(lib_env.get_cluster_state()).node_section.nodes,
        level_id,
        force_device,
        force_node,
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()
    lib_env.push_cib()


# DEPRECATED, use get_config_dto
def get_config(lib_env: LibraryEnvironment) -> list[dict[str, Any]]:
    """
    Get fencing levels configuration.

    Return a list of levels where each level is a dict with keys: target_type,
    target_value, level and devices. Devices is a list of stonith device ids.

    lib_env -- environment
    """
    cib = lib_env.get_cib()
    return cib_fencing_topology.export(get_fencing_topology(cib))


def get_config_dto(env: LibraryEnvironment) -> CibFencingTopologyDto:
    """
    Get fencing level configuration.

    env -- library environment
    """
    return cib_fencing_topology.fencing_topology_el_to_dto(
        get_fencing_topology(env.get_cib())
    )


def remove_all_levels(lib_env: LibraryEnvironment) -> None:
    """
    Remove all fencing levels

    lib_env -- environment
    """
    cib_fencing_topology.remove_all_levels(
        get_fencing_topology(lib_env.get_cib())
    )
    lib_env.push_cib()


def remove_levels_by_params(
    lib_env: LibraryEnvironment,
    level: Optional[str] = None,
    target_type: Optional[FencingTargetType] = None,
    target_value: Optional[FencingTargetValue] = None,
    devices: Optional[StringSequence] = None,
    # TODO remove, deprecated backward compatibility layer
    ignore_if_missing: bool = False,
    # TODO remove, deprecated backward compatibility layer
    target_may_be_a_device: bool = False,
) -> None:
    """
    Remove specified fencing level(s).

    lib_env -- environment
    level -- level (index) of the fencing level to remove
    target_type -- the removed fencing level target value type
    target_value -- the removed fencing level target value
    devices -- list of stonith devices of the removed fencing level
    ignore_if_missing -- when True, do not report if level not found
    target_may_be_a_device -- enables backward compatibility mode for old CLI
    """
    topology_el = get_fencing_topology(lib_env.get_cib())
    report_list = cib_fencing_topology.remove_levels_by_params(
        topology_el,
        level,
        target_type,
        target_value,
        devices,
        ignore_if_missing,
        validate_device_ids=(not target_may_be_a_device),
    )

    if not target_may_be_a_device or target_type != TARGET_TYPE_NODE:
        if lib_env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()
        lib_env.push_cib()
        return

    # TODO remove, deprecated backward compatibility mode
    # CLI command parameters are: level, node, stonith, stonith... Both the
    # node and the stonith list are optional. If the node is omitted and the
    # stonith list is present, there is no way to figure it out, since there is
    # no specification of what the parameter is. Hence the pre-lib code tried
    # both. First it assumed the first parameter is a node. If that fence level
    # didn't exist, it assumed the first parameter is a device. Since it was
    # only possible to specify node as a target back then, this is enabled only
    # in that case.
    # CLI has no way to figure out what the first parameter is. Therefore, the
    # lib must try both cases if asked to do so.
    if not report.has_errors(report_list):
        lib_env.report_processor.report_list(report_list)
        lib_env.push_cib()
        return

    level_not_found = False
    for report_item in report_list:
        if (
            report_item.message.code
            == report.codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST
        ):
            level_not_found = True
            break
    if not level_not_found:
        lib_env.report_processor.report_list(report_list)
        raise LibraryError()

    target_and_devices = [target_value]
    if devices:
        target_and_devices.extend(devices)
    report_list_second = cib_fencing_topology.remove_levels_by_params(
        topology_el,
        level,
        None,
        None,
        target_and_devices,  # type: ignore
        ignore_if_missing,
        validate_device_ids=(not target_may_be_a_device),
    )
    if not report.has_errors(report_list_second):
        lib_env.report_processor.report_list(report_list_second)
        lib_env.push_cib()
        return

    lib_env.report_processor.report_list(report_list)
    lib_env.report_processor.report_list(report_list_second)
    raise LibraryError()


def verify(lib_env: LibraryEnvironment) -> None:
    """
    Check if all cluster nodes and stonith devices used in fencing levels exist

    lib_env -- environment
    """
    cib = lib_env.get_cib()
    lib_env.report_processor.report_list(
        cib_fencing_topology.verify(
            cib,
            ClusterState(lib_env.get_cluster_state()).node_section.nodes,
        )
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()
