import re
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    cast,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
)
from pcs.common.tools import timeout_to_seconds
from pcs.common.types import StringIterable
from pcs.lib.cib.const import TAG_RESOURCE_PRIMITIVE
from pcs.lib.cib.nvpair import (
    INSTANCE_ATTRIBUTES_TAG,
    arrange_first_instance_attributes,
    get_value,
)
from pcs.lib.cib.tools import IdProvider
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.live import get_resource_digests
from pcs.lib.pacemaker.state import get_resource_state
from pcs.lib.pacemaker.values import is_false
from pcs.lib.xml_tools import get_root

from . import (
    common,
    operations,
)


def is_stonith(resource_el: _Element):
    return (
        resource_el.tag == TAG_RESOURCE_PRIMITIVE
        and resource_el.get("class") == "stonith"
    )


def is_stonith_enabled(crm_config_el: _Element) -> bool:
    # We should read the default value from pacemaker. However, that may slow
    # pcs down as we need to run 'pacemaker-schedulerd metadata' to get it.
    stonith_enabled = True
    # TODO properly support multiple cluster_property_set with rules
    for nvpair in crm_config_el.iterfind(
        "cluster_property_set/nvpair[@name='stonith-enabled']"
    ):
        if is_false(nvpair.get("value", "true")):
            stonith_enabled = False
            break
    return stonith_enabled


def get_misconfigured_resources(
    resources_el: _Element,
) -> Tuple[List[_Element], List[_Element], List[_Element]]:
    """
    Return stonith: all, 'action' option set, 'method' option set to 'cycle'
    """
    stonith_all = cast(
        List[_Element], resources_el.xpath("//primitive[@class='stonith']")
    )
    stonith_with_action = []
    stonith_with_method_cycle = []
    for stonith in stonith_all:
        for nvpair in stonith.iterfind("instance_attributes/nvpair"):
            if nvpair.get("name") == "action" and nvpair.get("value"):
                stonith_with_action.append(stonith)
            if (
                stonith.get("type") != "fence_sbd"
                and nvpair.get("name") == "method"
                and nvpair.get("value") == "cycle"
            ):
                stonith_with_method_cycle.append(stonith)
    return stonith_all, stonith_with_action, stonith_with_method_cycle


SUPPORTED_RESOURCE_TYPES_FOR_RESTARTLESS_UPDATE = ["fence_scsi", "fence_mpath"]


def validate_stonith_restartless_update(
    cib: _Element,
    stonith_id: str,
) -> Tuple[Optional[_Element], ReportItemList]:
    """
    Validate that stonith device exists and its type is supported for
    restartless update of scsi devices and has defined option 'devices'.

    cib -- cib element
    stonith_id -- id of a stonith resource
    """
    stonith_el, report_list = common.find_one_resource(
        cib, stonith_id, resource_tags=[TAG_RESOURCE_PRIMITIVE]
    )
    if stonith_el is None:
        return stonith_el, report_list

    stonith_type = stonith_el.get("type", "")
    if (
        stonith_el.get("class", "") != "stonith"
        or stonith_el.get("provider", "") != ""
        or stonith_type not in SUPPORTED_RESOURCE_TYPES_FOR_RESTARTLESS_UPDATE
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnsupportedAgent(
                    stonith_id,
                    stonith_type,
                    SUPPORTED_RESOURCE_TYPES_FOR_RESTARTLESS_UPDATE,
                )
            )
        )
        return stonith_el, report_list

    if not get_value(INSTANCE_ATTRIBUTES_TAG, stonith_el, "devices"):
        report_list.append(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    "no devices option configured for stonith device "
                    f"'{stonith_id}'"
                )
            )
        )
    return stonith_el, report_list


def get_node_key_map_for_mpath(
    stonith_el: _Element, node_labels: StringIterable
) -> Dict[str, str]:
    def library_error(
        host_map: Optional[str], missing_nodes: StringIterable
    ) -> LibraryError:
        return LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateMissingMpathKeys(
                    host_map, sorted(missing_nodes)
                )
            )
        )

    pcmk_host_map_value = get_value(
        INSTANCE_ATTRIBUTES_TAG, stonith_el, "pcmk_host_map"
    )
    missing_nodes = set(node_labels)
    if not pcmk_host_map_value:
        raise library_error(pcmk_host_map_value, missing_nodes)
    node_key_map = {}
    pattern = re.compile(r"(?P<node>[^=:; \t]+)[=:](?P<key>[^=:; \t]+)[; \t]?")
    for match in pattern.finditer(pcmk_host_map_value):
        if match:
            group_dict = match.groupdict()
            node_key_map[group_dict["node"]] = group_dict["key"]
    missing_nodes -= set(node_key_map.keys())
    if missing_nodes:
        raise library_error(pcmk_host_map_value, missing_nodes)
    return node_key_map


DIGEST_ATTR_TO_DIGEST_TYPE_MAP = {
    "op-digest": "all",
    "op-secure-digest": "nonprivate",
    "op-restart-digest": "nonreloadable",
}
TRANSIENT_DIGEST_ATTR_TO_DIGEST_TYPE_MAP = {
    "#digests-all": "all",
    "#digests-secure": "nonprivate",
}
DIGEST_ATTRS = frozenset(DIGEST_ATTR_TO_DIGEST_TYPE_MAP.keys())
TRANSIENT_DIGEST_ATTRS = frozenset(
    TRANSIENT_DIGEST_ATTR_TO_DIGEST_TYPE_MAP.keys()
)


def _get_digest(
    attr: str,
    attr_to_type_map: Dict[str, str],
    calculated_digests: Dict[str, Optional[str]],
) -> str:
    """
    Return digest of right type for the specified attribute. If missing, raise
    an error.

    attr -- name of digest attribute
    atttr_to_type_map -- map for attribute name to digest type conversion
    calculated_digests -- digests calculated by pacemaker
    """
    if attr not in attr_to_type_map:
        raise AssertionError(
            f"Key '{attr}' is missing in the attribute name to digest type map"
        )
    digest = calculated_digests.get(attr_to_type_map[attr])
    if digest is None:
        # this should not happen and when it does it is pacemaker fault
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    f"necessary digest for '{attr}' attribute is missing"
                )
            )
        )
    return digest


def _get_transient_instance_attributes(cib: _Element) -> List[_Element]:
    """
    Return list of instance_attributes elements which could contain digest
    attributes.

    cib -- CIB root element
    """
    return cast(
        List[_Element],
        cib.xpath(
            "./status/node_state/transient_attributes/instance_attributes"
        ),
    )


def _get_lrm_rsc_op_elements(
    cib: _Element,
    resource_id: str,
    node_name: str,
    op_name: str,
    interval: Optional[str] = None,
) -> List[_Element]:
    """
    Get a lrm_rsc_op element from cib status.

    resource_id -- resource id whose belonging element we want to find
    node_name -- name of the node where resource is running
    op_name -- operation name (start or monitor)
    interval -- operation interval using for monitor operation selection
    """
    return cast(
        List[_Element],
        cib.xpath(
            """
            ./status/node_state[@uname=$node_name]
            /lrm/lrm_resources/lrm_resource[@id=$resource_id]
            /lrm_rsc_op[@operation=$op_name{interval}]
            """.format(interval=" and @interval=$interval" if interval else ""),
            node_name=node_name,
            resource_id=resource_id,
            op_name=op_name,
            interval=interval if interval else "",
        ),
    )


def _get_monitor_attrs(
    resource_el: _Element,
) -> List[Dict[str, Optional[str]]]:
    """
    Get list of interval/timeout attributes of all monitor oparations of
    the resource which is being updated.

    Only interval and timeout attributes are needed for digests
    calculations. Interval attribute is mandatory attribute and timeout
    attribute is optional and it must be converted to milliseconds when
    passing to crm_resource utility. Operation with missing
    interval attribute or with attributes unable to convert to
    milliseconds will be skipped. Misconfigured operations do not have to
    necessarily prevent restartless update because pacemaker can ignore such
    misconfigured operations. If there is some mismatch between op elements
    from the resource definition and lrm_rsc_op elements from the cluster
    status, it will be found later.
    """
    monitor_attrs_list: List[Dict[str, Optional[str]]] = []
    for operation_el in operations.get_resource_operations(
        resource_el, names=["monitor"]
    ):
        sec = timeout_to_seconds(operation_el.get("interval", ""))
        interval = (
            None if sec is None or isinstance(sec, str) else str(sec * 1000)
        )
        if interval is None:
            continue
        timeout = operation_el.get("timeout")
        if timeout is None:
            monitor_attrs_list.append(dict(interval=interval, timeout=timeout))
            continue
        sec = timeout_to_seconds(timeout)
        timeout = (
            None if sec is None or isinstance(sec, str) else str(sec * 1000)
        )
        if timeout is None:
            continue
        monitor_attrs_list.append(dict(interval=interval, timeout=timeout))
    return monitor_attrs_list


def _update_digest_attrs_in_lrm_rsc_op(
    lrm_rsc_op: _Element, calculated_digests: Dict[str, Optional[str]]
):
    """
    Update digest attributes in lrm_rsc_op elements. If there are missing
    digests values from pacemaker or missing digests attributes in lrm_rsc_op
    element then report an error.

    lrm_rsc_op -- element whose digests attributes needs to be updated in order
        to do restartless update of resource
    calculated_digests -- digests calculated by pacemaker for this lrm_rsc_op
        element
    """
    common_digests_attrs = set(DIGEST_ATTRS).intersection(
        lrm_rsc_op.attrib.keys()
    )
    if not common_digests_attrs:
        # this should not happen and when it does it is pacemaker fault
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    "no digests attributes in lrm_rsc_op element",
                )
            )
        )
    for attr in common_digests_attrs:
        # update digest in cib
        lrm_rsc_op.attrib[attr] = _get_digest(
            attr, DIGEST_ATTR_TO_DIGEST_TYPE_MAP, calculated_digests
        )


def _get_transient_digest_value(
    old_value: str, stonith_id: str, stonith_type: str, digest: str
) -> str:
    """
    Return transient digest value with replaced digest.

    Value has comma separated format:
    <stonith_id>:<stonith_type>:<digest>,...

    and we need to replace only digest for our currently updated stonith device.

    old_value -- value to be replaced
    stonith_id -- id of stonith resource
    stonith_type -- stonith resource type
    digest -- digest for new value
    """
    new_comma_values_list = []
    for comma_value in old_value.split(","):
        new_comma_value = comma_value
        if comma_value:
            try:
                _id, _type, _ = comma_value.split(":")
            except ValueError as e:
                raise LibraryError(
                    ReportItem.error(
                        reports.messages.StonithRestartlessUpdateUnableToPerform(
                            f"invalid digest attribute value: '{old_value}'"
                        )
                    )
                ) from e
            if _id == stonith_id and _type == stonith_type:
                new_comma_value = ":".join([stonith_id, stonith_type, digest])
        new_comma_values_list.append(new_comma_value)
    return ",".join(new_comma_values_list)


def _update_digest_attrs_in_transient_instance_attributes(
    nvset_el: _Element,
    stonith_id: str,
    stonith_type: str,
    calculated_digests: Dict[str, Optional[str]],
) -> None:
    """
    Update digests attributes in transient instance attributes element.

    nvset_el -- instance_attributes element containing nvpairs with digests
        attributes
    stonith_id -- id of stonith resource being updated
    stonith_type -- type of stonith resource being updated
    calculated_digests -- digests calculated by pacemaker
    """
    for attr in TRANSIENT_DIGEST_ATTRS:
        nvpair_list = cast(
            List[_Element],
            nvset_el.xpath("./nvpair[@name=$name]", name=attr),
        )
        if not nvpair_list:
            continue
        if len(nvpair_list) > 1:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.StonithRestartlessUpdateUnableToPerform(
                        f"multiple digests attributes: '{attr}'"
                    )
                )
            )
        old_value = nvpair_list[0].attrib["value"]
        if old_value:
            nvpair_list[0].attrib["value"] = _get_transient_digest_value(
                str(old_value),
                stonith_id,
                stonith_type,
                _get_digest(
                    attr,
                    TRANSIENT_DIGEST_ATTR_TO_DIGEST_TYPE_MAP,
                    calculated_digests,
                ),
            )


def update_scsi_devices_without_restart(
    runner: CommandRunner,
    cluster_state: _Element,
    resource_el: _Element,
    id_provider: IdProvider,
    devices_list: StringIterable,
) -> None:
    """
    Update scsi devices without restart of stonith resource or other resources.

    runner -- command runner instance
    cluster_state -- status of the cluster
    resource_el -- resource element being updated
    id_provider -- elements' ids generator
    device_list -- list of updated scsi devices
    """
    # pylint: disable=too-many-locals
    cib = get_root(resource_el)
    resource_id = resource_el.get("id", "")
    roles_with_nodes = get_resource_state(cluster_state, resource_id)
    if "Started" not in roles_with_nodes:
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    f"resource '{resource_id}' is not running on any node",
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_NOT_RUNNING,
                )
            )
        )
    if len(roles_with_nodes["Started"]) != 1:
        # TODO: do we want to be able update cloned fence_scsi? Or just case
        # when it's running on more than 1 node? It is possible but we need to
        # update more lrm_rsc_op elements
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    f"resource '{resource_id}' is running on more than 1 node"
                )
            )
        )
    node_name = roles_with_nodes["Started"][0]

    new_instance_attrs = {"devices": ",".join(sorted(devices_list))}
    arrange_first_instance_attributes(
        resource_el, new_instance_attrs, id_provider
    )

    lrm_rsc_op_start_list = _get_lrm_rsc_op_elements(
        cib, resource_id, node_name, "start"
    )
    new_instance_attrs_digests = get_resource_digests(
        runner, resource_id, node_name, new_instance_attrs
    )
    if len(lrm_rsc_op_start_list) == 1:
        _update_digest_attrs_in_lrm_rsc_op(
            lrm_rsc_op_start_list[0], new_instance_attrs_digests
        )
    else:
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    "lrm_rsc_op element for start operation was not found"
                )
            )
        )

    monitor_attrs_list = _get_monitor_attrs(resource_el)
    lrm_rsc_op_monitor_list = _get_lrm_rsc_op_elements(
        cib, resource_id, node_name, "monitor"
    )
    if len(lrm_rsc_op_monitor_list) != len(monitor_attrs_list):
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateUnableToPerform(
                    (
                        "number of lrm_rsc_op and op elements for monitor "
                        "operation differs"
                    )
                )
            )
        )

    for monitor_attrs in monitor_attrs_list:
        lrm_rsc_op_list = _get_lrm_rsc_op_elements(
            cib,
            resource_id,
            node_name,
            "monitor",
            monitor_attrs["interval"],
        )
        if len(lrm_rsc_op_list) == 1:
            _update_digest_attrs_in_lrm_rsc_op(
                lrm_rsc_op_list[0],
                get_resource_digests(
                    runner,
                    resource_id,
                    node_name,
                    new_instance_attrs,
                    crm_meta_attributes=monitor_attrs,
                ),
            )
        else:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.StonithRestartlessUpdateUnableToPerform(
                        (
                            "monitor lrm_rsc_op element for resource "
                            f"'{resource_id}', node '{node_name}' and interval "
                            f"'{monitor_attrs['interval']}' not found"
                        )
                    )
                )
            )
    for nvset_el in _get_transient_instance_attributes(cib):
        _update_digest_attrs_in_transient_instance_attributes(
            nvset_el,
            resource_id,
            resource_el.get("type", ""),
            new_instance_attrs_digests,
        )
