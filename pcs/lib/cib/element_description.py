from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib.const import (
    TAG_ACL_PERMISSION,
    TAG_ACL_ROLE,
    TAG_ALERT,
    TAG_LIST_RESOURCE,
    TAG_NODE,
    TAG_RECIPIENT,
)
from pcs.lib.xml_tools import update_attribute_remove_empty

TAG_LIST_SUPPORTS_DESCRIPTION = frozenset.union(
    TAG_LIST_RESOURCE,
    {
        TAG_ACL_PERMISSION,
        TAG_ACL_ROLE,
        TAG_ALERT,
        TAG_NODE,
        TAG_RECIPIENT,
    },
)

DESCRIPTION_ATTRIBUTE = "description"


def validate_description_support(element: _Element) -> reports.ReportItemList:
    """
    Validate that element supports the description attribute

    element -- specified element
    """
    if element.tag not in TAG_LIST_SUPPORTS_DESCRIPTION:
        return [
            reports.ReportItem.error(
                reports.messages.IdDoesNotSupportElementDescriptions(
                    str(element.attrib["id"]),
                    element.tag,
                    sorted(TAG_LIST_SUPPORTS_DESCRIPTION),
                )
            )
        ]
    return []


def set_description(element: _Element, description: str) -> None:
    """
    Set the description of element to specified value or remove the description
    attribute if the new value is empty

    element -- specified element
    description -- new description for the element
    """
    update_attribute_remove_empty(element, DESCRIPTION_ATTRIBUTE, description)


def get_description(element: _Element) -> str:
    """
    Get the description of an element

    element -- specified element
    """
    return element.get(DESCRIPTION_ATTRIBUTE, "")
