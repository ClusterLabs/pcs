from collections.abc import Sequence
from typing import (
    Any,
    Final,
    Optional,
    Type,
    TypeVar,
    cast,
)

from lxml import etree
from lxml.etree import (
    _Attrib,
    _Element,
)

from pcs.common import reports
from pcs.common.fencing_topology import (
    TARGET_TYPE_ATTRIBUTE,
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    FencingTargetType,
    FencingTargetValue,
)
from pcs.common.pacemaker.fencing_topology import (
    CibFencingLevelAttributeDto,
    CibFencingLevelNodeDto,
    CibFencingLevelRegexDto,
    CibFencingTopologyDto,
)
from pcs.common.reports import (
    ReportItemList,
    ReportItemSeverity,
    ReportProcessor,
    has_errors,
)
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import ReportItem
from pcs.common.types import StringSequence
from pcs.common.validate import is_integer
from pcs.lib.cib.const import TAG_FENCING_LEVEL
from pcs.lib.cib.resource.stonith import is_stonith
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    get_element_by_id,
    get_fencing_topology,
    multivalue_attr_contains_value,
    multivalue_attr_delete_value,
    multivalue_attr_has_any_values,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import _Element as StateElement
from pcs.lib.pacemaker.values import (
    sanitize_id,
    validate_id,
)

_DEVICES_ATTRIBUTE: Final = "devices"

FencingLevelDto = TypeVar(
    "FencingLevelDto",
    CibFencingLevelAttributeDto,
    CibFencingLevelNodeDto,
    CibFencingLevelRegexDto,
)


def _generate_level_id(
    id_provider: IdProvider,
    level: str,
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
) -> str:
    if target_type == TARGET_TYPE_ATTRIBUTE:
        # For attribute target type, the value is tuple[str, str]
        id_part = target_value[0]
    else:
        # For all other target types, the value is str
        id_part = str(target_value)
    return id_provider.allocate_id(sanitize_id(f"fl-{id_part}-{level}"))


def add_level(  # noqa: PLR0913
    reporter: ReportProcessor,
    cib: _Element,
    level: str,
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
    devices: StringSequence,
    cluster_status_nodes: Sequence[StateElement],
    level_id: Optional[str] = None,
    force_device: bool = False,
    force_node: bool = False,
) -> None:
    """
    Validate and add a new fencing level. Raise LibraryError if not valid.

    reporter -- report processor
    cib -- the whole cib
    level -- level (index) of the new fencing level
    target_type -- the new fencing level target value type
    target_value -- the new fencing level target value
    devices -- list of stonith devices for the new fencing level
    cluster_status_nodes -- list of status of existing cluster nodes
    level_id -- user specified id for the level element
    force_device -- continue even if a stonith device does not exist
    force_node -- continue even if a node (target) does not exist
    """
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    id_provider = IdProvider(cib)
    validate_id_reports: ReportItemList = []
    if level_id is not None:
        validate_id(level_id, "fencing level id", reporter=validate_id_reports)
    reporter.report_list(
        (id_provider.book_ids(level_id) if level_id else [])
        + validate_id_reports
        + _validate_level(level)
        + _validate_target(
            cluster_status_nodes, target_type, target_value, force_node
        )
        + _validate_devices(cib, devices, force_device)
    )
    if reporter.has_errors:
        raise LibraryError()
    topology_el = get_fencing_topology(cib)
    reporter.report_list(
        _validate_level_target_devices_does_not_exist(
            topology_el, level, target_type, target_value, devices
        )
    )
    if reporter.has_errors:
        raise LibraryError()
    _append_level_element(
        topology_el,
        level,
        target_type,
        target_value,
        devices,
        (
            level_id
            or _generate_level_id(id_provider, level, target_type, target_value)
        ),
    )


def remove_all_levels(topology_el: _Element) -> None:
    """
    Remove all fencing levels.
    topology_el -- etree element to remove the levels from
    """
    # Do not ever remove a fencing-topology element, even if it is empty. There
    # may be ACLs set in pacemaker which allow "write" for fencing-level
    # elements (adding, changing and removing) but not fencing-topology
    # elements. In such a case, removing a fencing-topology element would cause
    # the whole change to be rejected by pacemaker with a "permission denied"
    # message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    for level_el in topology_el.findall(TAG_FENCING_LEVEL):
        # Parent is guaranteed by CIB schema
        cast(_Element, level_el.getparent()).remove(level_el)


def remove_levels_by_params(
    topology_el: _Element,
    level: Optional[str] = None,
    target_type: Optional[FencingTargetType] = None,
    target_value: Optional[FencingTargetValue] = None,
    devices: Optional[StringSequence] = None,
) -> ReportItemList:
    """
    Remove specified fencing level(s)

    topology_el -- etree element to remove the levels from
    level -- level (index) of the fencing level to remove
    target_type -- the removed fencing level target value type
    target_value -- the removed fencing level target value
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
                    level or "",
                    target_type,
                    target_value,
                    sorted(devices) if devices else [],
                )
            )
        )
    if has_errors(report_list):
        return report_list
    for el in level_el_list:
        # Parent guaranteed by CIB schema
        cast(_Element, el.getparent()).remove(el)
    return report_list


def find_levels_with_device(
    topology_el: _Element, device_id: str
) -> list[_Element]:
    """
    Return list of all fencing-level elements that reference the specified
    device

    topology_el -- etree element with fencing levels
    device_id -- id of the stonith device
    """
    return [
        level_el
        for level_el in topology_el.findall(TAG_FENCING_LEVEL)
        if multivalue_attr_contains_value(
            level_el, _DEVICES_ATTRIBUTE, device_id
        )
    ]


def remove_device_from_level(level_el: _Element, device_id: str) -> None:
    """
    Remove specified stonith device from fencing level.

    level_el -- level element from which the device is removed
    device_id -- stonith device to remove
    """
    multivalue_attr_delete_value(level_el, _DEVICES_ATTRIBUTE, device_id)


def has_any_devices(level_el: _Element) -> bool:
    """
    Return whether there are any devices references in the fencing level

    level_el -- fencing level element
    """
    return multivalue_attr_has_any_values(level_el, _DEVICES_ATTRIBUTE)


# DEPRECATED, use fencing_topology_el_to_dto
def export(topology_el: _Element) -> list[dict[str, Any]]:
    """
    Export all fencing levels.

    Return a list of levels where each level is a dict with keys: target_type,
    target_value. level and devices. Devices is a list of stonith device ids.

    etree topology_el -- etree element to export
    """
    export_levels = []
    for level_el in topology_el.iterfind(TAG_FENCING_LEVEL):
        target_type: Optional[FencingTargetType] = None
        target_value: Optional[FencingTargetValue] = None
        if "target" in level_el.attrib:
            target_type = TARGET_TYPE_NODE
            target_value = level_el.get("target")
        elif "target-pattern" in level_el.attrib:
            target_type = TARGET_TYPE_REGEXP
            target_value = level_el.get("target-pattern")
        elif "target-attribute" in level_el.attrib:
            target_type = TARGET_TYPE_ATTRIBUTE
            target_value = (
                str(level_el.attrib["target-attribute"]),
                str(level_el.attrib["target-value"]),
            )
        if target_type and target_value:
            export_levels.append(
                {
                    "target_type": target_type,
                    "target_value": target_value,
                    "level": level_el.get("index"),
                    "devices": str(level_el.attrib[_DEVICES_ATTRIBUTE]).split(
                        ","
                    ),
                }
            )
    return export_levels


def _fencing_level_dto_factory(
    dto_type: Type[FencingLevelDto],
    level_el_attrib: _Attrib,
) -> FencingLevelDto:
    if dto_type is CibFencingLevelRegexDto:
        target_args = {"target_pattern": str(level_el_attrib["target-pattern"])}
    elif dto_type is CibFencingLevelAttributeDto:
        target_args = {
            "target_attribute": str(level_el_attrib["target-attribute"]),
            "target_value": str(level_el_attrib["target-value"]),
        }
    else:
        target_args = {"target": str(level_el_attrib["target"])}

    return dto_type(
        id=str(level_el_attrib["id"]),
        index=int(level_el_attrib["index"]),
        devices=[
            device.strip()
            for device in str(level_el_attrib["devices"]).split(",")
        ],
        **target_args,
    )


def fencing_topology_el_to_dto(
    fencing_topology_el: _Element,
) -> CibFencingTopologyDto:
    level_el_list = _find_all_level_elements(fencing_topology_el)
    target_node_list = []
    target_regex_list = []
    target_attr_list = []
    for level_el in level_el_list:
        if "target" in level_el.attrib:
            target_node_list.append(
                _fencing_level_dto_factory(
                    CibFencingLevelNodeDto,
                    level_el.attrib,
                )
            )
        if "target-pattern" in level_el.attrib:
            target_regex_list.append(
                _fencing_level_dto_factory(
                    CibFencingLevelRegexDto,
                    level_el.attrib,
                )
            )
        if "target-attribute" in level_el.attrib:
            target_attr_list.append(
                _fencing_level_dto_factory(
                    CibFencingLevelAttributeDto,
                    level_el.attrib,
                )
            )

    return CibFencingTopologyDto(
        target_node=target_node_list,
        target_regex=target_regex_list,
        target_attribute=target_attr_list,
    )


def verify(
    cib: _Element,
    cluster_status_nodes: Sequence[StateElement],
) -> ReportItemList:
    """
    Check if all cluster nodes and stonith devices used in fencing levels exist.

    cib -- the whole cib
    cluster_status_nodes -- list of status of existing cluster nodes
    """
    report_list: ReportItemList = []
    used_nodes: set[str] = set()
    used_devices: set[str] = set()
    topology_el = get_fencing_topology(cib)

    for level_el in topology_el.iterfind(TAG_FENCING_LEVEL):
        used_devices.update(
            str(level_el.get(_DEVICES_ATTRIBUTE, "")).split(",")
        )
        if "target" in level_el.attrib:
            used_nodes.add(str(level_el.get("target", "")))

    if used_devices:
        report_list.extend(
            _validate_devices(cib, sorted(used_devices), allow_force=False)
        )

    for node in sorted(used_nodes):
        report_list.extend(
            _validate_target_valuewise(
                cluster_status_nodes, TARGET_TYPE_NODE, node, allow_force=False
            )
        )
    return report_list


def _validate_level(level: str) -> ReportItemList:
    report_list: ReportItemList = []
    if not is_integer(level, 1, 9):
        report_list.append(
            ReportItem.error(
                reports.messages.InvalidOptionValue("level", str(level), "1..9")
            )
        )
    return report_list


def _validate_target(
    cluster_status_nodes: Sequence[StateElement],
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
    force_node: bool = False,
) -> ReportItemList:
    return _validate_target_typewise(target_type) + _validate_target_valuewise(
        cluster_status_nodes, target_type, target_value, force_node
    )


def _validate_target_typewise(target_type: FencingTargetType) -> ReportItemList:
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
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
    force_node: bool = False,
    allow_force: bool = True,
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
                    message=reports.messages.NodeNotFound(
                        # This is a str based on target_type
                        str(target_value)
                    ),
                )
            )
    return report_list


def _validate_devices(
    cib: _Element,
    devices: StringSequence,
    force_device: bool = False,
    allow_force: bool = True,
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
        try:
            if not is_stonith(get_element_by_id(cib, dev)):
                invalid_devices.append(dev)
        except ElementNotFound:
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
    tree: _Element,
    level: str,
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
    devices: StringSequence,
) -> ReportItemList:
    report_list: ReportItemList = []
    if _find_level_elements(tree, level, target_type, target_value, devices):
        report_list.append(
            ReportItem.error(
                reports.messages.CibFencingLevelAlreadyExists(
                    level, target_type, target_value, list(devices)
                )
            )
        )
    return report_list


def _append_level_element(
    tree: _Element,
    level: str,
    target_type: FencingTargetType,
    target_value: FencingTargetValue,
    devices: StringSequence,
    level_id: str,
) -> _Element:
    level_el = etree.SubElement(
        tree,
        TAG_FENCING_LEVEL,
        index=level,
        devices=",".join(devices),
        id=level_id,
    )
    if target_type == TARGET_TYPE_NODE:
        level_el.set("target", str(target_value))
    elif target_type == TARGET_TYPE_REGEXP:
        level_el.set("target-pattern", str(target_value))
    elif target_type == TARGET_TYPE_ATTRIBUTE:
        level_el.set("target-attribute", target_value[0])
        level_el.set("target-value", target_value[1])
    return level_el


def _find_all_level_elements(tree: _Element) -> list[_Element]:
    return tree.findall(TAG_FENCING_LEVEL)


def _find_level_elements(
    tree: _Element,
    level: Optional[str] = None,
    target_type: Optional[FencingTargetType] = None,
    target_value: Optional[FencingTargetValue] = None,
    devices: Optional[StringSequence] = None,
) -> list[_Element]:
    xpath_vars: dict[str, str] = {}

    xpath_target = ""
    if target_type and target_value:
        if target_type == TARGET_TYPE_NODE:
            xpath_target = "@target=$var_target"
            # The value of xpath_target determines that this is a string
            xpath_vars["var_target"] = str(target_value)
        elif target_type == TARGET_TYPE_REGEXP:
            xpath_target = "@target-pattern=$var_target_pattern"
            # The value of xpath_target determines that this is a string
            xpath_vars["var_target_pattern"] = str(target_value)
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
            f"{TAG_FENCING_LEVEL}[{xpath_attrs}]",
            var_devices=(",".join(devices) if devices else ""),
            var_level=level or "",
            **xpath_vars,  # type: ignore
        )

    return _find_all_level_elements(tree)
