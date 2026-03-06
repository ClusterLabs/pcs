from typing import Callable

from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib.const import (
    TAG_CONSTRAINT_LOCATION,
    TAG_FENCING_LEVEL,
    TAG_RESOURCE_PRIMITIVE,
    TAG_RULE,
)
from pcs.lib.xml_tools import find_parent


def rename_in_cib(
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


def _rename_node_in_locations(
    cib: _Element, old_name: str, new_name: str
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    for location in cib.findall(
        f".//{TAG_CONSTRAINT_LOCATION}[@node='{old_name}']"
    ):
        location.set("node", new_name)
        report_list.append(
            reports.ReportItem.info(
                reports.messages.CibNodeRenameElementUpdated(
                    element_type=TAG_CONSTRAINT_LOCATION,
                    element_id=str(location.get("id", "")),
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
    for expression in cib.findall(
        f".//{TAG_RULE}/expression[@attribute='#uname'][@value='{old_name}']"
    ):
        expression.set("value", new_name)
        rule = expression.getparent()
        # mypy would complain but: //{TAG_RULE}/expression
        assert rule is not None
        report_list.append(
            reports.ReportItem.info(
                reports.messages.CibNodeRenameElementUpdated(
                    element_type=TAG_RULE,
                    element_id=str(rule.get("id", "")),
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
    for level in cib.findall(f".//{TAG_FENCING_LEVEL}"):
        level_id = str(level.get("id", ""))
        if level.get("target") == old_name:
            level.set("target", new_name)
            report_list.append(
                reports.ReportItem.info(
                    reports.messages.CibNodeRenameElementUpdated(
                        element_type=TAG_FENCING_LEVEL,
                        element_id=level_id,
                        attribute_desc="target",
                        old_value=old_name,
                        new_value=new_name,
                    )
                )
            )
        elif (
            level.get("target-attribute") == "#uname"
            and level.get("target-value") == old_name
        ):
            level.set("target-value", new_name)
            report_list.append(
                reports.ReportItem.info(
                    reports.messages.CibNodeRenameElementUpdated(
                        element_type=TAG_FENCING_LEVEL,
                        element_id=level_id,
                        attribute_desc="target-value for target-attribute=#uname",
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
        if ":" not in entry:
            # It's broken but if it's an old domain name, it can be confused
            # with host_list. We cannot fix it but it makes sense to update
            # host name if it exactly match with the old name.
            new_entries.append(new_name if entry == old_name else entry)
            continue
        host, ports = entry.split(":", 1)
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
        f".//{TAG_RESOURCE_PRIMITIVE}[@class='stonith']/instance_attributes"
        f"/nvpair[@name='{attr_name}']"
    ):
        old_value = str(nvpair.get("value", ""))
        new_value = rename_func(old_value, old_name, new_name)
        if new_value != old_value:
            nvpair.set("value", new_value)
            fence_device = find_parent(nvpair, [TAG_RESOURCE_PRIMITIVE])
            # mypy would complain but:
            # //{TAG_RESOURCE_PRIMITIVE}/instance_attributes/nvpair
            assert fence_device is not None
            report_list.append(
                reports.ReportItem.info(
                    reports.messages.CibNodeRenameElementUpdated(
                        element_type=TAG_RESOURCE_PRIMITIVE,
                        element_id=fence_device.get("id", ""),
                        attribute_desc=attr_name,
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
