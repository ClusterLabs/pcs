from typing import (
    Final,
    Optional,
    Sequence,
    Set,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.fencing_topology import (
    TARGET_TYPE_ATTRIBUTE,
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
)
from pcs.common.reports import (
    ReportItemList,
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.reports import codes as report_codes
from pcs.common.reports import has_errors
from pcs.common.reports.item import ReportItem
from pcs.common.types import StringCollection
from pcs.common.validate import is_integer
from pcs.lib.cib.const import TAG_FENCING_LEVEL
from pcs.lib.cib.resource.stonith import is_stonith_resource
from pcs.lib.cib.tools import (
    find_unique_id,
    get_element_by_id,
    get_root,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import _Element as StateElement
from pcs.lib.pacemaker.values import (
    sanitize_id,
    validate_id,
)

_DEVICES_ATTRIBUTE: Final = "devices"


def add_level(
    reporter: ReportProcessor,
    topology_el: _Element,
    resources_el: _Element,
    level,
    target_type,
    target_value,
    devices,
    cluster_status_nodes: Sequence[StateElement],
    force_device=False,
    force_node=False,
):
    """
    Validate and add a new fencing level. Raise LibraryError if not valid.

    reporter -- report processor
    etree topology_el -- etree element to add the level to
    etree resources_el -- etree element with resources definitions
    int|string level -- level (index) of the new fencing level
    constant target_type -- the new fencing level target value type
    mixed target_value -- the new fencing level target value
    Iterable devices -- list of stonith devices for the new fencing level
    Iterable cluster_status_nodes -- list of status of existing cluster nodes
    bool force_device -- continue even if a stonith device does not exist
    bool force_node -- continue even if a node (target) does not exist
    """
    # pylint: disable=too-many-arguments
    reporter.report_list(
        _validate_level(level)
        + _validate_target(
            cluster_status_nodes, target_type, target_value, force_node
        )
        + _validate_devices(resources_el, devices, force_device)
    )
    if reporter.has_errors:
        raise LibraryError()
    reporter.report_list(
        _validate_level_target_devices_does_not_exist(
            topology_el, level, target_type, target_value, devices
        )
    )
    if reporter.has_errors:
        raise LibraryError()
    _append_level_element(
        topology_el, int(level), target_type, target_value, devices
    )


def remove_all_levels(topology_el):
    """
    Remove all fencing levels.
    etree topology_el -- etree element to remove the levels from
    """
    # Do not ever remove a fencing-topology element, even if it is empty. There
    # may be ACLs set in pacemaker which allow "write" for fencing-level
    # elements (adding, changing and removing) but not fencing-topology
    # elements. In such a case, removing a fencing-topology element would cause
    # the whole change to be rejected by pacemaker with a "permission denied"
    # message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    for level_el in topology_el.findall("fencing-level"):
        level_el.getparent().remove(level_el)


def remove_levels_by_params(
    topology_el: _Element,
    level=None,
    # TODO create a special type, so that it cannot accept any string
    target_type: Optional[str] = None,
    target_value=None,
    devices: Optional[StringCollection] = None,
) -> ReportItemList:
    """
    Remove specified fencing level(s)

    topology_el -- etree element to remove the levels from
    int|string level -- level (index) of the fencing level to remove
    target_type -- the removed fencing level target value type
    mixed target_value -- the removed fencing level target value
    devices -- list of stonith devices of the removed fencing level
    """
    # Do not ever remove a fencing-topology element, even if it is empty. There
    # may be ACLs set in pacemaker which allow "write" for fencing-level
    # elements (adding, changing and removing) but not fencing-topology
    # elements. In such a case, removing a fencing-topology element would cause
    # the whole change to be rejected by pacemaker with a "permission denied"
    # message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    report_list: ReportItemList = []
    if target_type:
        report_list.extend(_validate_target_typewise(target_type))
        if has_errors(report_list):
            return report_list

    if devices is not None:
        for device_id in devices:
            validate_id(
                device_id, description="stonith id", reporter=report_list
            )

    level_el_list = _find_level_elements(
        topology_el, level, target_type, target_value, devices
    )

    if not level_el_list:
        report_list.append(
            ReportItem.error(
                reports.messages.CibFencingLevelDoesNotExist(
                    level,
                    target_type,
                    target_value,
                    sorted(devices) if devices else [],
                )
            )
        )
    if has_errors(report_list):
        return report_list
    for el in level_el_list:
        el.getparent().remove(el)
    return report_list


def remove_device_from_all_levels_dont_remove_elements(
    topology_el: _Element, device_id: str
) -> list[_Element]:
    """
    Remove specified stonith device from all fencing levels. Do not remove
    fencing-level elements with empty devices attribute. Instead, return a list
    of all the elements from which the device was removed.

    topology_el -- etree element with levels to remove the device from
    device_id -- stonith device to remove
    """
    elements = []
    for level_el in topology_el.findall(TAG_FENCING_LEVEL):
        old_devices = level_el.get(_DEVICES_ATTRIBUTE, "")
        _remove_device_from_level(level_el, device_id)
        new_devices = level_el.get(_DEVICES_ATTRIBUTE, "")

        if old_devices != new_devices:
            elements.append(level_el)

    return elements


def remove_device_from_all_levels(
    topology_el: _Element, device_id: str
) -> None:
    """
    Remove specified stonith device from all fencing levels.

    topology_el -- etree element with levels to remove the device from
    device_id -- stonith device to remove
    """
    # Do not ever remove a fencing-topology element, even if it is empty. There
    # may be ACLs set in pacemaker which allow "write" for fencing-level
    # elements (adding, changing and removing) but not fencing-topology
    # elements. In such a case, removing a fencing-topology element would cause
    # the whole change to be rejected by pacemaker with a "permission denied"
    # message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    for level_el in remove_device_from_all_levels_dont_remove_elements(
        topology_el, device_id
    ):
        _remove_fencing_level_if_empty(level_el)


def remove_device_from_one_level(
    topology_el: _Element, level_id: str, device_id: str
) -> None:
    """
    Remove specified stonith device from specified fencing level.

    topology_el -- etree element with levels to remove the device from
    level_id -- level element from which the device is removed
    device_id -- stonith device to remove
    """
    level_el = get_element_by_id(get_root(topology_el), level_id)
    _remove_device_from_level(level_el, device_id)
    _remove_fencing_level_if_empty(level_el)


def _remove_device_from_level(level_el: _Element, device_id: str) -> None:
    new_devices = [
        dev
        for dev in level_el.get(_DEVICES_ATTRIBUTE, "").split(",")
        if dev != device_id
    ]
    level_el.set(_DEVICES_ATTRIBUTE, ",".join(new_devices))


def _remove_fencing_level_if_empty(level_el: _Element) -> None:
    if level_el.get(_DEVICES_ATTRIBUTE, "") != "":
        return

    parent = level_el.getparent()
    if parent is not None:
        parent.remove(level_el)


def export(topology_el):
    """
    Export all fencing levels.

    Return a list of levels where each level is a dict with keys: target_type,
    target_value. level and devices. Devices is a list of stonith device ids.

    etree topology_el -- etree element to export
    """
    export_levels = []
    for level_el in topology_el.iterfind("fencing-level"):
        target_type = target_value = None
        if "target" in level_el.attrib:
            target_type = TARGET_TYPE_NODE
            target_value = level_el.get("target")
        elif "target-pattern" in level_el.attrib:
            target_type = TARGET_TYPE_REGEXP
            target_value = level_el.get("target-pattern")
        elif "target-attribute" in level_el.attrib:
            target_type = TARGET_TYPE_ATTRIBUTE
            target_value = (
                level_el.get("target-attribute"),
                level_el.get("target-value"),
            )
        if target_type and target_value:
            export_levels.append(
                {
                    "target_type": target_type,
                    "target_value": target_value,
                    "level": level_el.get("index"),
                    "devices": level_el.get("devices").split(","),
                }
            )
    return export_levels


def verify(
    topology_el: _Element,
    resources_el: _Element,
    cluster_status_nodes: Sequence[StateElement],
) -> ReportItemList:
    """
    Check if all cluster nodes and stonith devices used in fencing levels exist.

    topology_el -- fencing levels to check
    resources_el -- resources definitions
    cluster_status_nodes -- list of status of existing cluster nodes
    """
    report_list: ReportItemList = []
    used_nodes: Set[str] = set()
    used_devices: Set[str] = set()

    for level_el in topology_el.iterfind("fencing-level"):
        used_devices.update(str(level_el.get("devices", "")).split(","))
        if "target" in level_el.attrib:
            used_nodes.add(str(level_el.get("target", "")))

    if used_devices:
        report_list.extend(
            _validate_devices(
                resources_el, sorted(used_devices), allow_force=False
            )
        )

    for node in sorted(used_nodes):
        report_list.extend(
            _validate_target_valuewise(
                cluster_status_nodes, TARGET_TYPE_NODE, node, allow_force=False
            )
        )
    return report_list


def _validate_level(level) -> ReportItemList:
    report_list: ReportItemList = []
    if not is_integer(level, 1, 9):
        report_list.append(
            ReportItem.error(
                reports.messages.InvalidOptionValue("level", level, "1..9")
            )
        )
    return report_list


def _validate_target(
    cluster_status_nodes: Sequence[StateElement],
    target_type,
    target_value,
    force_node=False,
) -> ReportItemList:
    return _validate_target_typewise(target_type) + _validate_target_valuewise(
        cluster_status_nodes, target_type, target_value, force_node
    )


def _validate_target_typewise(target_type) -> ReportItemList:
    report_list: ReportItemList = []
    if target_type not in [
        TARGET_TYPE_NODE,
        TARGET_TYPE_ATTRIBUTE,
        TARGET_TYPE_REGEXP,
    ]:
        report_list.append(
            ReportItem.error(
                reports.messages.InvalidOptionType(
                    "target",
                    ["node", "regular expression", "attribute_name=value"],
                )
            )
        )
    return report_list


def _validate_target_valuewise(
    cluster_status_nodes: Sequence[StateElement],
    target_type,
    target_value,
    force_node=False,
    allow_force=True,
) -> ReportItemList:
    report_list: ReportItemList = []
    if target_type == TARGET_TYPE_NODE:
        node_found = False
        for node in cluster_status_nodes:
            if target_value == node.attrs.name:
                node_found = True
                break
        if not node_found:
            report_list.append(
                ReportItem(
                    severity=ReportItemSeverity(
                        level=(
                            ReportItemSeverity.WARNING
                            if force_node and allow_force
                            else ReportItemSeverity.ERROR
                        ),
                        force_code=(
                            None
                            if force_node or not allow_force
                            else report_codes.FORCE
                        ),
                    ),
                    message=reports.messages.NodeNotFound(target_value),
                )
            )
    return report_list


def _validate_devices(
    resources_el: _Element, devices, force_device=False, allow_force=True
) -> ReportItemList:
    report_list: ReportItemList = []
    if not devices:
        report_list.append(
            ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["stonith devices"])
            )
        )
    invalid_devices = []
    for dev in devices:
        validate_id_report_list: ReportItemList = []
        validate_id(
            dev, description="device id", reporter=validate_id_report_list
        )
        report_list.extend(validate_id_report_list)
        if has_errors(validate_id_report_list):
            continue
        # TODO use the new finding function
        if not is_stonith_resource(resources_el, dev):
            invalid_devices.append(dev)
    if invalid_devices:
        report_list.append(
            ReportItem(
                severity=ReportItemSeverity(
                    level=(
                        ReportItemSeverity.WARNING
                        if force_device and allow_force
                        else ReportItemSeverity.ERROR
                    ),
                    force_code=(
                        None
                        if force_device or not allow_force
                        else report_codes.FORCE
                    ),
                ),
                message=reports.messages.StonithResourcesDoNotExist(
                    invalid_devices
                ),
            )
        )
    return report_list


def _validate_level_target_devices_does_not_exist(
    tree, level, target_type, target_value, devices
) -> ReportItemList:
    report_list: ReportItemList = []
    if _find_level_elements(tree, level, target_type, target_value, devices):
        report_list.append(
            ReportItem.error(
                reports.messages.CibFencingLevelAlreadyExists(
                    level, target_type, target_value, devices
                )
            )
        )
    return report_list


def _append_level_element(tree, level, target_type, target_value, devices):
    level_el = etree.SubElement(
        tree, "fencing-level", index=str(level), devices=",".join(devices)
    )
    if target_type == TARGET_TYPE_NODE:
        level_el.set("target", target_value)
        id_part = target_value
    elif target_type == TARGET_TYPE_REGEXP:
        level_el.set("target-pattern", target_value)
        id_part = target_value
    elif target_type == TARGET_TYPE_ATTRIBUTE:
        level_el.set("target-attribute", target_value[0])
        level_el.set("target-value", target_value[1])
        id_part = target_value[0]
    level_el.set(
        "id",
        find_unique_id(tree, sanitize_id(f"fl-{id_part}-{level}")),
    )
    return level_el


def _find_level_elements(
    tree, level=None, target_type=None, target_value=None, devices=None
):
    xpath_vars = {}

    xpath_target = ""
    if target_type and target_value:
        if target_type == TARGET_TYPE_NODE:
            xpath_target = "@target=$var_target"
            xpath_vars["var_target"] = target_value
        elif target_type == TARGET_TYPE_REGEXP:
            xpath_target = "@target-pattern=$var_target_pattern"
            xpath_vars["var_target_pattern"] = target_value
        elif target_type == TARGET_TYPE_ATTRIBUTE:
            xpath_target = (
                "@target-attribute=$var_target_attribute "
                "and @target-value=$var_target_value"
            )
            xpath_vars["var_target_attribute"] = target_value[0]
            xpath_vars["var_target_value"] = target_value[1]
    xpath_devices = ""
    if devices:
        xpath_devices = "@devices=$var_devices"
    xpath_level = ""
    if level:
        xpath_level = "@index=$var_level"

    xpath_attrs = " and ".join(
        filter(None, [xpath_level, xpath_devices, xpath_target])
    )
    if xpath_attrs:
        return tree.xpath(
            f"fencing-level[{xpath_attrs}]",
            var_devices=(",".join(devices) if devices else ""),
            var_level=level,
            **xpath_vars,
        )
    return tree.findall("fencing-level")
