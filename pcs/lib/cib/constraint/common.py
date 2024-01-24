from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib.resource.bundle import TAG as TAG_BUNDLE
from pcs.lib.cib.resource.clone import ALL_TAGS as TAG_CLONE_ALL
from pcs.lib.cib.resource.group import TAG as TAG_GROUP
from pcs.lib.cib.resource.primitive import TAG as TAG_PRIMITIVE
from pcs.lib.cib.tag import TAG_TAG
from pcs.lib.cib.tools import (
    ElementNotFound,
    get_element_by_id,
)
from pcs.lib.xml_tools import find_parent


def validate_resource_id(
    cib: _Element, resource_id: str, in_clone_allowed: bool = False
) -> reports.ReportItemList:
    """
    Validate that an ID belongs to resource and may be added to a constraint

    cib -- cib element
    resource_id -- ID to be validated
    in_clone_allowed -- allow constraints for resources in clones / bundles
    """
    report_list: reports.ReportItemList = []
    parent_tags = TAG_CLONE_ALL + [TAG_BUNDLE]
    resource_tags = parent_tags + [TAG_GROUP, TAG_PRIMITIVE, TAG_TAG]

    try:
        resource_element = get_element_by_id(cib, resource_id)
    except ElementNotFound:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.IdNotFound(resource_id, [])
            )
        )
        return report_list
    if resource_element.tag not in resource_tags:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.IdBelongsToUnexpectedType(
                    resource_id,
                    resource_tags,
                    str(resource_element.attrib["id"]),
                )
            )
        )
        return report_list

    if resource_element.tag not in parent_tags:
        clone = find_parent(resource_element, parent_tags)
        if clone is not None:
            report_list.append(
                reports.ReportItem(
                    reports.item.get_severity(
                        reports.codes.FORCE, in_clone_allowed
                    ),
                    reports.messages.ResourceForConstraintIsMultiinstance(
                        resource_id,
                        "clone" if clone.tag == "master" else clone.tag,
                        str(clone.attrib["id"]),
                    ),
                )
            )

    return report_list
