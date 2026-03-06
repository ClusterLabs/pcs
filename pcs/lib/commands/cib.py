from typing import Callable, Iterable

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringCollection
from pcs.lib.cib import element_description as cib_element_description
from pcs.lib.cib.const import TAG_FENCING_LEVEL
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote_resource,
)
from pcs.lib.cib.resource.stonith import is_stonith
from pcs.lib.cib.tools import ElementNotFound, get_element_by_id, get_resources
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.sbd_stonith import ensure_some_stonith_remains


def remove_elements(
    env: LibraryEnvironment,
    ids: StringCollection,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Remove elements with specified ids from CIB. This function is aware of
    relations and references between elements and will also remove all elements
    that are somehow referencing elements with specified ids.

    ids -- ids of configuration elements to remove
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    report_processor = env.report_processor

    elements_to_remove = ElementsToRemove(cib, ids)

    stonith_ids = []
    non_stonith_ids = []
    for res_el in elements_to_remove.resources_to_remove:
        if is_stonith(res_el):
            stonith_ids.append(str(res_el.attrib["id"]))
        else:
            non_stonith_ids.append(str(res_el.attrib["id"]))

    report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
        + _ensure_not_guest_remote(elements_to_remove.resources_to_remove)
        + ensure_some_stonith_remains(
            env,
            get_resources(cib),
            stonith_resources_to_ignore=stonith_ids,
            sbd_being_disabled=False,
            force_flags=force_flags,
        )
    )

    # stonith resources do not need to be stopped, because they do not left
    # orphaned resources behind, so we check only the state of non-stonith
    # resources
    if non_stonith_ids:
        if env.is_cib_live:
            report_processor.report_list(
                ensure_resources_stopped(
                    env.get_cluster_state(), non_stonith_ids, force_flags
                )
            )
        else:
            report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.StoppedResourcesBeforeDeleteCheckSkipped(
                        non_stonith_ids, reports.const.REASON_NOT_LIVE_CIB
                    )
                )
            )
    if report_processor.has_errors:
        raise LibraryError()

    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )
    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()


def element_description_set(
    env: LibraryEnvironment, element_id: str, description: str
) -> None:
    """
    Set, update, or delete the description of specified element.

    env -- LibraryEnvironment
    element_id -- id of the element
    description -- new description, if empty, delete existing description
    """
    try:
        element = get_element_by_id(env.get_cib(), element_id)
        env.report_processor.report_list(
            cib_element_description.validate_description_support(element)
        )
    except ElementNotFound:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(element_id, [])
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    cib_element_description.set_description(element, description)
    env.push_cib()


def element_description_get(env: LibraryEnvironment, element_id: str) -> str:
    """
    Get description of specified element.

    env -- LibraryEnvironment
    element_id -- id of the element
    """
    try:
        element = get_element_by_id(env.get_cib(), element_id)
        env.report_processor.report_list(
            cib_element_description.validate_description_support(element)
        )
    except ElementNotFound:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(element_id, [])
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    return cib_element_description.get_description(element)


def _validate_elements_to_remove(
    element_to_remove: ElementsToRemove,
) -> reports.ReportItemList:
    report_list = [
        reports.ReportItem.error(reports.messages.IdNotFound(missing_id, []))
        for missing_id in sorted(element_to_remove.missing_ids)
    ]
    unsupported_elements = element_to_remove.unsupported_elements
    report_list.extend(
        reports.ReportItem.error(
            reports.messages.IdBelongsToUnexpectedType(
                unsupported_id,
                list(unsupported_elements.supported_element_types),
                unsupported_elements.id_tag_map[unsupported_id],
            )
        )
        for unsupported_id in sorted(unsupported_elements.id_tag_map)
    )
    return report_list


def _ensure_not_guest_remote(
    resource_elements: Iterable[_Element],
) -> reports.ReportItemList:
    report_list = []
    for element in resource_elements:
        if is_guest_node(element):
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.UseCommandNodeRemoveGuest(
                        str(element.attrib["id"])
                    )
                )
            )
        if get_node_name_from_remote_resource(element) is not None:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.UseCommandNodeRemoveRemote(
                        str(element.attrib["id"])
                    )
                )
            )
    return report_list


def _check_corosync_consistency(
    corosync_node_names: StringCollection,
    old_name: str,
    new_name: str,
    force_flags: reports.types.ForceFlags,
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    force_severity = reports.item.get_severity(
        reports.codes.FORCE,
        reports.codes.FORCE in force_flags,
    )
    if new_name not in corosync_node_names:
        report_list.append(
            reports.ReportItem(
                severity=force_severity,
                message=reports.messages.CibNodeRenameNewNodeNotInCorosync(
                    new_name=new_name,
                ),
            )
        )
    if old_name in corosync_node_names:
        report_list.append(
            reports.ReportItem(
                severity=force_severity,
                message=reports.messages.CibNodeRenameOldNodeInCorosync(
                    old_name=old_name,
                ),
            )
        )
    return report_list


def _rename_node_in_locations(
    cib: _Element, old_name: str, new_name: str
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    for element in cib.findall(f".//rsc_location[@node='{old_name}']"):
        element.set("node", new_name)
        report_list.append(
            reports.ReportItem.info(
                reports.messages.CibNodeRenameElementUpdated(
                    element_type="Location constraint",
                    element_id=str(element.get("id", "")),
                    attribute_desc="node",
                    old_value=old_name,
                    new_value=new_name,
                )
            )
        )
    return report_list


def _rename_node_in_rules(
    cib: _Element, old_name: str, new_name: str
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    for element in cib.findall(
        f".//expression[@attribute='#uname'][@value='{old_name}']"
    ):
        element.set("value", new_name)
        # expression -> rule
        rule_element = element.getparent()
        assert rule_element is not None
        report_list.append(
            reports.ReportItem.info(
                reports.messages.CibNodeRenameElementUpdated(
                    element_type="Rule",
                    element_id=str(rule_element.get("id", "")),
                    attribute_desc="#uname expression",
                    old_value=old_name,
                    new_value=new_name,
                )
            )
        )
    return report_list


def _rename_node_in_fencing_levels(
    cib: _Element, old_name: str, new_name: str
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    for element in cib.findall(f".//{TAG_FENCING_LEVEL}"):
        level_id = str(element.get("id", ""))
        if element.get("target") == old_name:
            element.set("target", new_name)
            report_list.append(
                reports.ReportItem.info(
                    reports.messages.CibNodeRenameElementUpdated(
                        element_type="Fencing level",
                        element_id=level_id,
                        attribute_desc="target",
                        old_value=old_name,
                        new_value=new_name,
                    )
                )
            )
        elif (
            element.get("target-attribute") == "#uname"
            and element.get("target-value") == old_name
        ):
            element.set("target-value", new_name)
            report_list.append(
                reports.ReportItem.info(
                    reports.messages.CibNodeRenameElementUpdated(
                        element_type="Fencing level",
                        element_id=level_id,
                        attribute_desc="target",
                        old_value=old_name,
                        new_value=new_name,
                    )
                )
            )
    return report_list


def _rename_in_host_list(value: str, old_name: str, new_name: str) -> str:
    return ",".join(
        [new_name if host == old_name else host for host in value.split(",")]
    )


def _rename_in_host_map(value: str, old_name: str, new_name: str) -> str:
    # Format: node:port[,port];node:port
    new_entries = []
    for entry in value.split(";"):
        host, ports = entry.split(":")
        if host == old_name:
            host = new_name
        new_entries.append(f"{host}:{ports}")
    return ";".join(new_entries)


def _rename_node_in_fence_devices_attribute(
    cib: _Element,
    attr_name: str,
    rename_func: Callable[[str, str, str], str],
    old_name: str,
    new_name: str,
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    for nvpair in cib.findall(
        ".//primitive[@class='stonith']/instance_attributes/nvpair"
        f"[@name='{attr_name}']"
    ):
        old_value = str(nvpair.get("value", ""))
        new_value = rename_func(old_value, old_name, new_name)
        if new_value != old_value:
            nvpair.set("value", new_value)
            # nvpair -> instance_attributes -> primitive
            instance_attrs = nvpair.getparent()
            assert instance_attrs is not None
            fence_device = instance_attrs.getparent()
            assert fence_device is not None
            report_list.append(
                reports.ReportItem.info(
                    reports.messages.CibNodeRenameElementUpdated(
                        element_type="Fence device",
                        element_id=fence_device.get("id", ""),
                        attribute_desc=f"attribute '{attr_name}'",
                        old_value=old_value,
                        new_value=new_value,
                    )
                )
            )
    return report_list


def _rename_node_in_fence_devices(
    cib: _Element, old_name: str, new_name: str
) -> reports.ReportItemList:
    return [
        *_rename_node_in_fence_devices_attribute(
            cib, "pcmk_host_list", _rename_in_host_list, old_name, new_name
        ),
        *_rename_node_in_fence_devices_attribute(
            cib, "pcmk_host_map", _rename_in_host_map, old_name, new_name
        ),
    ]


def _warn_about_fencing_level_patterns(
    cib: _Element,
) -> reports.ReportItemList:
    # This can be reported multiple times. It makes sense since the pattern is
    # reported and the user can immediately consider a manual intervention
    # necessity.
    return [
        reports.ReportItem.warning(
            reports.messages.CibNodeRenameFencingLevelPatternExists(
                level_id=str(element.get("id", "")),
                pattern=str(element.get("target-pattern", "")),
            )
        )
        for element in cib.findall(f".//{TAG_FENCING_LEVEL}[@target-pattern]")
    ]


def _warn_about_acls(cib: _Element) -> bool:
    acl_section = cib.find(".//acls")
    return acl_section is not None and len(acl_section) > 0


def _rename_in_cib(
    cib: _Element, old_name: str, new_name: str
) -> tuple[bool, reports.ReportItemList]:
    report_list: reports.ReportItemList = [
        *_rename_node_in_locations(cib, old_name, new_name),
        *_rename_node_in_rules(cib, old_name, new_name),
        *_rename_node_in_fencing_levels(cib, old_name, new_name),
        *_rename_node_in_fence_devices(cib, old_name, new_name),
    ]

    cib_updated = len(report_list) > 0

    report_list.extend(_warn_about_fencing_level_patterns(cib))

    if _warn_about_acls(cib):
        report_list.append(
            reports.ReportItem.warning(
                reports.messages.CibNodeRenameAclsExist()
            )
        )

    return cib_updated, report_list


def rename_node(
    env: LibraryEnvironment,
    old_name: str,
    new_name: str,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Rename a cluster node in CIB configuration elements.

    old_name -- current node name
    new_name -- new node name
    """

    if env.is_cib_live:
        corosync_node_names = {
            n.name for n in env.get_corosync_conf().get_nodes() if n.name
        }
        for report_item in _check_corosync_consistency(
            corosync_node_names, old_name, new_name, force_flags
        ):
            env.report_processor.report(report_item)

    if env.report_processor.has_errors:
        raise LibraryError()

    cib = env.get_cib()
    cib_updated, report_list = _rename_in_cib(cib, old_name, new_name)
    env.report_processor.report_list(report_list)

    if cib_updated:
        env.push_cib()
        return

    env.report_processor.report(
        reports.ReportItem.info(reports.messages.CibNodeRenameNoChange())
    )
