from lxml import etree

from pcs.common import report_codes
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.lib import reports
from pcs.lib.cib.stonith import is_stonith_resource
from pcs.lib.cib.tools import find_unique_id
from pcs.lib.errors import ReportItemSeverity
from pcs.lib.pacemaker.values import sanitize_id, validate_id

def add_level(
    reporter, topology_el, resources_el, level, target_type, target_value,
    devices, cluster_status_nodes, force_device=False, force_node=False
):
    # pylint: disable=too-many-arguments
    """
    Validate and add a new fencing level. Raise LibraryError if not valid.

    object reporter -- report processor
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
    valid_level = _validate_level(reporter, level)
    _validate_target(
        reporter, cluster_status_nodes, target_type, target_value, force_node
    )
    _validate_devices(reporter, resources_el, devices, force_device)
    reporter.send()
    _validate_level_target_devices_does_not_exist(
        reporter, topology_el, level, target_type, target_value, devices
    )
    reporter.send()
    _append_level_element(
        topology_el, valid_level, target_type, target_value, devices
    )

def remove_all_levels(topology_el):
    """
    Remove all fencing levels.
    etree topology_el -- etree element to remove the levels from
    """
    for level_el in topology_el.findall("fencing-level"):
        level_el.getparent().remove(level_el)

def remove_levels_by_params(
    reporter, topology_el, level=None, target_type=None, target_value=None,
    devices=None, ignore_if_missing=False
):
    """
    Remove specified fencing level(s). Raise LibraryError if not found.

    object reporter -- report processor
    etree topology_el -- etree element to remove the levels from
    int|string level -- level (index) of the fencing level to remove
    constant target_type -- the removed fencing level target value type
    mixed target_value -- the removed fencing level target value
    Iterable devices -- list of stonith devices of the removed fencing level
    bool ignore_if_missing -- when True, do not raise if level not found
    """
    if target_type:
        _validate_target_typewise(reporter, target_type)
        reporter.send()

    level_el_list = _find_level_elements(
        topology_el, level, target_type, target_value, devices
    )

    if not level_el_list:
        if ignore_if_missing:
            return
        reporter.process(reports.fencing_level_does_not_exist(
            level, target_type, target_value, devices
        ))
    for el in level_el_list:
        el.getparent().remove(el)

def remove_device_from_all_levels(topology_el, device_id):
    """
    Remove specified stonith device from all fencing levels.

    etree topology_el -- etree element with levels to remove the device from
    string device_id -- stonith device to remove
    """
    for level_el in topology_el.findall("fencing-level"):
        new_devices = [
            dev
            for dev in level_el.get("devices").split(",")
            if dev != device_id
        ]
        if new_devices:
            level_el.set("devices", ",".join(new_devices))
        else:
            level_el.getparent().remove(level_el)

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
                level_el.get("target-value")
            )
        if target_type and target_value:
            export_levels.append({
                "target_type": target_type,
                "target_value": target_value,
                "level": level_el.get("index"),
                "devices": level_el.get("devices").split(",")
            })
    return export_levels

def verify(reporter, topology_el, resources_el, cluster_status_nodes):
    """
    Check if all cluster nodes and stonith devices used in fencing levels exist.

    All errors are stored into the passed reporter. Calling function is
    responsible for processing the report.

    object reporter -- report processor
    etree topology_el -- etree element with fencing levels to check
    etree resources_el -- etree element with resources definitions
    Iterable cluster_status_nodes -- list of status of existing cluster nodes
    """
    used_nodes = set()
    used_devices = set()

    for level_el in topology_el.iterfind("fencing-level"):
        used_devices.update(level_el.get("devices").split(","))
        if "target" in level_el.attrib:
            used_nodes.add(level_el.get("target"))

    if used_devices:
        _validate_devices(
            reporter,
            resources_el,
            sorted(used_devices),
            allow_force=False
        )

    for node in sorted(used_nodes):
        _validate_target_valuewise(
            reporter,
            cluster_status_nodes,
            TARGET_TYPE_NODE,
            node,
            allow_force=False
        )

def _validate_level(reporter, level):
    # TODO this should not rely on the report to be sent and the execution
    # ended in a caller
    try:
        candidate = int(level)
        if candidate > 0:
            return candidate
    except ValueError:
        pass
    reporter.append(
        reports.invalid_option_value("level", level, "a positive integer")
    )
    return None

def _validate_target(
    reporter, cluster_status_nodes, target_type, target_value,
    force_node=False
):
    _validate_target_typewise(reporter, target_type)
    _validate_target_valuewise(
        reporter, cluster_status_nodes, target_type, target_value, force_node
    )

def _validate_target_typewise(reporter, target_type):
    if target_type not in [
        TARGET_TYPE_NODE, TARGET_TYPE_ATTRIBUTE, TARGET_TYPE_REGEXP
    ]:
        reporter.append(reports.invalid_option_type(
            "target",
            ["node", "regular expression", "attribute_name=value"]
        ))

def _validate_target_valuewise(
    reporter, cluster_status_nodes, target_type, target_value, force_node=False,
    allow_force=True
):
    if target_type == TARGET_TYPE_NODE:
        node_found = False
        for node in cluster_status_nodes:
            if target_value == node.attrs.name:
                node_found = True
                break
        if not node_found:
            reporter.append(
                reports.node_not_found(
                    target_value,
                    severity=ReportItemSeverity.WARNING
                        if force_node and allow_force
                        else ReportItemSeverity.ERROR
                    ,
                    forceable=None if force_node or not allow_force
                        else report_codes.FORCE_NODE_DOES_NOT_EXIST
                )
            )

def _validate_devices(
    reporter, resources_el, devices, force_device=False, allow_force=True
):
    if not devices:
        reporter.append(
            reports.required_option_is_missing(["stonith devices"])
        )
    invalid_devices = []
    for dev in devices:
        errors = reporter.errors_count
        validate_id(dev, description="device id", reporter=reporter)
        if reporter.errors_count > errors:
            continue
        # TODO use the new finding function
        if not is_stonith_resource(resources_el, dev):
            invalid_devices.append(dev)
    if invalid_devices:
        reporter.append(
            reports.stonith_resources_do_not_exist(
                invalid_devices,
                ReportItemSeverity.WARNING if force_device and allow_force
                    else ReportItemSeverity.ERROR
                ,
                None if force_device or not allow_force
                    else report_codes.FORCE_STONITH_RESOURCE_DOES_NOT_EXIST
            )
        )

def _validate_level_target_devices_does_not_exist(
    reporter, tree, level, target_type, target_value, devices
):
    if _find_level_elements(tree, level, target_type, target_value, devices):
        reporter.append(
            reports.fencing_level_already_exists(
                level, target_type, target_value, devices
            )
        )

def _append_level_element(tree, level, target_type, target_value, devices):
    level_el = etree.SubElement(
        tree,
        "fencing-level",
        index=str(level),
        devices=",".join(devices)
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
        find_unique_id(tree, sanitize_id("fl-{0}-{1}".format(id_part, level)))
    )
    return level_el

def _find_level_elements(
    tree, level=None, target_type=None, target_value=None, devices=None
):
    xpath_target = ""
    if target_type and target_value:
        if target_type == TARGET_TYPE_NODE:
            xpath_target = "@target='{0}'".format(target_value)
        elif target_type == TARGET_TYPE_REGEXP:
            xpath_target = "@target-pattern='{0}'".format(target_value)
        elif target_type == TARGET_TYPE_ATTRIBUTE:
            xpath_target = (
                "@target-attribute='{0}' and @target-value='{1}'".format(
                    target_value[0], target_value[1]
                )
            )
    xpath_devices = ""
    if devices:
        xpath_devices = "@devices='{0}'".format(",".join(devices))
    xpath_level = ""
    if level:
        xpath_level = "@index='{0}'".format(level)

    xpath_attrs = " and ".join(
        filter(None, [xpath_level, xpath_devices, xpath_target])
    )
    if xpath_attrs:
        return tree.xpath("fencing-level[{0}]".format(xpath_attrs))
    return tree.findall("fencing-level")
