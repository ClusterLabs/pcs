from typing import Iterable

from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib.const import (
    TAG_LIST_CONSTRAINABLE,
    TAG_LIST_RESOURCE_MULTIINSTANCE,
)
from pcs.lib.xml_tools import find_parent


def validate_constrainable_elements(
    element_list: Iterable[_Element], in_multiinstance_allowed: bool = False
) -> reports.ReportItemList:
    """
    Validate that a constraint can be created for each of the specified elements

    element_list -- the elements to be validated
    in_multiinstance_allowed -- allow constraints for resources in clones/bundles
    """
    report_list: reports.ReportItemList = []

    for element in element_list:
        if element.tag not in TAG_LIST_CONSTRAINABLE:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        str(element.attrib["id"]),
                        sorted(TAG_LIST_CONSTRAINABLE),
                        element.tag,
                    )
                )
            )
            continue

        if element.tag not in TAG_LIST_RESOURCE_MULTIINSTANCE:
            multiinstance_parent = find_parent(
                element, TAG_LIST_RESOURCE_MULTIINSTANCE
            )
            if multiinstance_parent is not None:
                report_list.append(
                    reports.ReportItem(
                        reports.item.get_severity(
                            reports.codes.FORCE, in_multiinstance_allowed
                        ),
                        reports.messages.ResourceForConstraintIsMultiinstance(
                            str(element.attrib["id"]),
                            multiinstance_parent.tag,
                            str(multiinstance_parent.attrib["id"]),
                        ),
                    )
                )

    return report_list
