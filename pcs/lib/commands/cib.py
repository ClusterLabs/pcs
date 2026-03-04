from typing import (
    Callable,
    Iterable,
    Sequence,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import (
    StringCollection,
    StringSequence,
)
from pcs.lib.cib.const import TAG_FENCING_LEVEL
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
    stop_resources,
    warn_resource_unmanaged,
)
from pcs.lib.cib.resource.guest_node import (
    get_node_name_from_resource as get_node_name_from_guest_resource,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote_resource,
)
from pcs.lib.cib.resource.stonith import is_stonith
from pcs.lib.cib.tools import get_resources
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import remove_node
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
    remote_node_names = _get_remote_node_names(
        elements_to_remove.resources_to_remove
    )
    guest_node_names = _get_guest_node_names(
        elements_to_remove.resources_to_remove
    )

    if remote_node_names:
        report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.UseCommandNodeRemoveRemote()
            )
        )
    if guest_node_names:
        report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.UseCommandNodeRemoveGuest()
            )
        )

    if report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
        + _warn_remote_guest(remote_node_names, guest_node_names)
        + ensure_some_stonith_remains(
            env,
            get_resources(cib),
            stonith_resources_to_ignore=[
                str(res_el.attrib["id"])
                for res_el in elements_to_remove.resources_to_remove
                if is_stonith(res_el)
            ],
            sbd_being_disabled=False,
            force_flags=force_flags,
        )
    ).has_errors:
        raise LibraryError()

    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )

    cib = _stop_resources_wait(
        env, cib, elements_to_remove.resources_to_remove, force_flags
    )

    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()

    if env.is_cib_live:
        for node_name in remote_node_names + guest_node_names:
            remove_node(env.cmd_runner(), node_name)


def _stop_resources_wait(
    env: LibraryEnvironment,
    cib: _Element,
    resource_elements: Sequence[_Element],
    force_flags: reports.types.ForceFlags = (),
) -> _Element:
    """
    Stop all resources that are going to be removed. Push cib, wait for the
    cluster to settle down, and check if all resources were properly stopped.
    If not, report errors. Return cib with the applied changes.

    cib -- whole cib
    resource_elements -- resources that should be stopped
    force_flags -- list of flags codes
    """
    if not resource_elements:
        return cib
    if not env.is_cib_live:
        return cib
    if reports.codes.FORCE in force_flags:
        env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.StoppingResourcesBeforeDeletingSkipped()
            )
        )
        return cib

    resource_ids = [str(el.attrib["id"]) for el in resource_elements]

    env.report_processor.report(
        reports.ReportItem.info(
            reports.messages.StoppingResourcesBeforeDeleting(resource_ids)
        )
    )

    if env.report_processor.report_list(
        warn_resource_unmanaged(env.get_cluster_state(), resource_ids)
    ).has_errors:
        raise LibraryError()
    stop_resources(cib, resource_elements)
    env.push_cib()

    env.wait_for_idle()
    if env.report_processor.report_list(
        ensure_resources_stopped(env.get_cluster_state(), resource_ids)
    ).has_errors:
        raise LibraryError()

    return env.get_cib()


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


def _warn_remote_guest(
    remote_node_names: StringSequence, guest_node_names: StringSequence
) -> reports.ReportItemList:
    return [
        reports.ReportItem.warning(
            reports.messages.RemoteNodeRemovalIncomplete(node_name)
        )
        for node_name in remote_node_names
    ] + [
        reports.ReportItem.warning(
            reports.messages.GuestNodeRemovalIncomplete(node_name)
        )
        for node_name in guest_node_names
    ]


def _get_remote_node_names(resource_elements: Iterable[_Element]) -> list[str]:
    return [
        get_node_name_from_remote_resource(el)
        for el in resource_elements
        if get_node_name_from_remote_resource(el) is not None
    ]


def _get_guest_node_names(resource_elements: Iterable[_Element]) -> list[str]:
    return [
        get_node_name_from_guest_resource(el)
        for el in resource_elements
        if is_guest_node(el)
    ]


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
    report = env.report_processor.report

    if env.is_cib_live:
        corosync_node_names = {
            n.name for n in env.get_corosync_conf().get_nodes() if n.name
        }
        for report_item in _check_corosync_consistency(
            corosync_node_names, old_name, new_name, force_flags
        ):
            report(report_item)

    if env.report_processor.has_errors:
        raise LibraryError()

    cib = env.get_cib()

    cib_update_report_list = [
        *_rename_node_in_locations(cib, old_name, new_name),
        *_rename_node_in_rules(cib, old_name, new_name),
        *_rename_node_in_fencing_levels(cib, old_name, new_name),
        *_rename_node_in_fence_devices(cib, old_name, new_name),
    ]

    cib_updated = False
    for report_item in cib_update_report_list:
        report(report_item)
        cib_updated = True

    for report_item in _warn_about_fencing_level_patterns(cib):
        report(report_item)

    if _warn_about_acls(cib):
        report(
            reports.ReportItem.warning(
                reports.messages.CibNodeRenameAclsExist()
            )
        )

    if cib_updated:
        env.push_cib()
        return

    report(reports.ReportItem.info(reports.messages.CibNodeRenameNoChange()))
