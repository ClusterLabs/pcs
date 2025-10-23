from typing import Any, Optional, cast

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.alert import (
    CibAlertDto,
    CibAlertRecipientDto,
    CibAlertSelectAttributeDto,
    CibAlertSelectDto,
)
from pcs.lib.cib import nvpair_multi, rule
from pcs.lib.cib.const import TAG_ALERT, TAG_RECIPIENT
from pcs.lib.cib.nvpair import get_nvset
from pcs.lib.cib.tools import (
    ElementSearcher,
    IdProvider,
    create_subelement_id,
    get_alerts,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import validate_id_reports
from pcs.lib.xml_tools import (
    get_sub_element,
    remove_one_element,
    update_attribute_remove_empty,
)


def get_all_alert_elements(tree: _Element) -> list[_Element]:
    return tree.findall(TAG_ALERT)


def find_alert(context_el: _Element, alert_id: str) -> _Element:
    searcher = ElementSearcher(TAG_ALERT, alert_id, context_el)
    found_element = searcher.get_element()
    if found_element is not None:
        return found_element
    raise LibraryError(*searcher.get_errors())


def find_recipient(context_el: _Element, recipient_id: str) -> _Element:
    searcher = ElementSearcher(TAG_RECIPIENT, recipient_id, context_el)
    found_element = searcher.get_element()
    if found_element is not None:
        return found_element
    raise LibraryError(*searcher.get_errors())


def _update_optional_attribute(
    element: _Element, attribute: str, value: Optional[str]
) -> None:
    """
    Set value of an optional attribute, remove the attribute on empty value

    element -- element to be updated
    attribute -- attribute to be updated
    value -- new value of the attribute
    """
    if value is None:
        return
    update_attribute_remove_empty(element, attribute, value)


def _validate_recipient_value_is_unique(
    alert_el: _Element,
    recipient_value: str,
    recipient_id: Optional[str] = None,
    allow_duplicity: bool = False,
) -> reports.ReportItemList:
    """
    Validate that the recipient_value is unique in the specified alert

    alert_el -- alert
    recipient_value -- recipient value
    recipient_id -- id of the recipient to which the value belongs
    allow_duplicity -- if True, report a warning if the value already exists
    """
    report_list: reports.ReportItemList = []
    recipient_list = alert_el.xpath(
        "./recipient[@value=$value and @id!=$id]",
        value=recipient_value,
        id=recipient_id or "",
    )
    if recipient_list:
        report_list.append(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE,
                    allow_duplicity,
                ),
                message=reports.messages.CibAlertRecipientAlreadyExists(
                    str(alert_el.attrib["id"]),
                    recipient_value,
                ),
            )
        )
    return report_list


def validate_create_alert(
    id_provider: IdProvider,
    # should be str, see lib.commands.alert.create_alert
    path: Optional[str],
    alert_id: Optional[str] = None,
) -> reports.ReportItemList:
    """
    validate new alert creation

    id_provider -- elements' ids generator
    path -- path to script
    alert_id -- id of new alert or None
    """
    report_list: reports.ReportItemList = []
    if not path:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["path"])
            )
        )
    if alert_id:
        report_list.extend(
            validate_id_reports(alert_id, description="alert-id")
        )
        report_list.extend(id_provider.book_ids(alert_id))
    return report_list


def create_alert(
    tree: _Element,
    id_provider: IdProvider,
    path: str,
    alert_id: Optional[str] = None,
    description: Optional[str] = None,
) -> _Element:
    """
    Create new alert element and return it

    tree -- cib etree node
    id_provider -- elements' ids generator
    path -- path to script
    alert_id -- id of new alert, it will be generated if it is None
    description -- description
    """
    if not alert_id:
        alert_id = id_provider.allocate_id(TAG_ALERT)

    alert_el = etree.SubElement(
        get_alerts(tree), TAG_ALERT, id=alert_id, path=path
    )
    if description:
        alert_el.set("description", description)

    return alert_el


def update_alert(
    tree: _Element,
    alert_id: str,
    path: Optional[str],
    description: Optional[str] = None,
) -> _Element:
    """
    Update existing alert. Return updated alert element.
    Raises LibraryError if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert to be updated
    path -- new value of path, stay unchanged if None
    description -- new value of description, stay unchanged if None, remove
        if empty
    """
    alert = find_alert(get_alerts(tree), alert_id)
    if path:
        alert.set("path", path)
    _update_optional_attribute(alert, "description", description)
    return alert


def remove_alert(tree: _Element, alert_id: str) -> None:
    """
    Remove alert with specified id.
    Raises LibraryError if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert which should be removed
    """
    remove_one_element(find_alert(get_alerts(tree), alert_id))


def validate_add_recipient(
    id_provider: IdProvider,
    alert_el: _Element,
    # should be str, see lib.commands.alert.add_recipient
    recipient_value: Optional[str],
    recipient_id: Optional[str] = None,
    allow_same_value: bool = False,
) -> reports.ReportItemList:
    """
    Validate adding a recipient to the specified alert

    id_provider -- elements' ids generator
    alert_el -- alert which should be the parent of the new recipient
    recipient_value -- value of the new recipient
    recipient_id -- id of the new recipient or None
    allow_same_value -- if True, unique recipient value is not required
    """
    report_list: reports.ReportItemList = []

    if not recipient_value:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["value"])
            )
        )
    else:
        report_list.extend(
            _validate_recipient_value_is_unique(
                alert_el,
                recipient_value,
                recipient_id,
                allow_duplicity=allow_same_value,
            )
        )

    if recipient_id:
        report_list.extend(
            validate_id_reports(recipient_id, description="recipient-id")
        )
        report_list.extend(id_provider.book_ids(recipient_id))

    return report_list


def add_recipient(
    id_provider: IdProvider,
    alert_el: _Element,
    recipient_value: str,
    recipient_id: Optional[str] = None,
    description: Optional[str] = None,
) -> _Element:
    """
    Add new recipient to the specified alert, return added recipient element

    id_provider -- elements' ids generator
    alert_el -- alert which should be the parent of the new recipient
    recipient_value -- value of the new recipient
    recipient_id -- id of the new recipient or None
    description -- description of the new recipient
    """
    if not recipient_id:
        recipient_id = create_subelement_id(
            alert_el, TAG_RECIPIENT, id_provider
        )
    recipient_el = etree.SubElement(
        alert_el, TAG_RECIPIENT, id=recipient_id, value=recipient_value
    )
    if description:
        recipient_el.attrib["description"] = description
    return recipient_el


def validate_update_recipient(
    recipient_el: _Element,
    recipient_value: Optional[str] = None,
    allow_same_value: bool = False,
) -> reports.ReportItemList:
    """
    validate updating specified recipient

    recipient_el -- the recipient to be updated
    recipient_value -- new recipient value, stay unchanged if None
    allow_same_value -- if True, unique recipient value is not required
    """
    report_list: reports.ReportItemList = []

    if recipient_value is not None:
        if not recipient_value:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.CibAlertRecipientValueInvalid(
                        recipient_value
                    )
                )
            )
        else:
            report_list.extend(
                _validate_recipient_value_is_unique(
                    cast(_Element, recipient_el.getparent()),
                    recipient_value,
                    str(recipient_el.attrib["id"]),
                    allow_duplicity=allow_same_value,
                )
            )

    return report_list


def update_recipient(
    recipient_el: _Element,
    recipient_value: Optional[str] = None,
    description: Optional[str] = None,
) -> _Element:
    """
    Update specified recipient. Returns updated recipient element.

    recipient_el -- the recipient to be updated
    recipient_value -- new recipient value, stay unchanged if None
    description -- description, if empty it will be removed, stay unchanged
        if None
    """
    if recipient_value is not None:
        recipient_el.set("value", recipient_value)
    _update_optional_attribute(recipient_el, "description", description)
    return recipient_el


def remove_recipient(tree: _Element, recipient_id: str) -> None:
    """
    Remove specified recipient.
    Raises LibraryError if recipient doesn't exist.

    tree -- cib etree node
    recipient_id -- id of recipient to be removed
    """
    remove_one_element(find_recipient(get_alerts(tree), recipient_id))


def _recipient_el_to_dto(
    recipient_el: _Element,
    rule_eval: Optional[rule.RuleInEffectEval] = None,
) -> CibAlertRecipientDto:
    if rule_eval is None:
        rule_eval = rule.RuleInEffectEvalDummy()
    return CibAlertRecipientDto(
        id=str(recipient_el.attrib["id"]),
        value=str(recipient_el.attrib["value"]),
        description=recipient_el.get("description"),
        meta_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                recipient_el, nvpair_multi.NVSET_META
            )
        ],
        instance_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                recipient_el, nvpair_multi.NVSET_INSTANCE
            )
        ],
    )


def _select_el_to_dto(select_el: _Element) -> CibAlertSelectDto:
    return CibAlertSelectDto(
        nodes=(select_el.find("select_nodes") is not None),
        fencing=(select_el.find("select_fencing") is not None),
        resources=(select_el.find("select_resources") is not None),
        attributes=(select_el.find("select_attributes") is not None),
        attributes_select=[
            CibAlertSelectAttributeDto(
                str(attr_el.attrib["id"]), str(attr_el.attrib["name"])
            )
            for attr_el in select_el.iterfind("select_attributes/attribute")
        ],
    )


def alert_el_to_dto(
    alert_el: _Element,
    rule_eval: Optional[rule.RuleInEffectEval] = None,
) -> CibAlertDto:
    if rule_eval is None:
        rule_eval = rule.RuleInEffectEvalDummy()
    select_el = alert_el.find("select")
    return CibAlertDto(
        id=str(alert_el.attrib["id"]),
        path=str(alert_el.attrib["path"]),
        description=alert_el.get("description"),
        recipients=[
            _recipient_el_to_dto(recipient_el, rule_eval)
            for recipient_el in alert_el.iterfind(TAG_RECIPIENT)
        ],
        select=_select_el_to_dto(select_el) if select_el is not None else None,
        meta_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                alert_el, nvpair_multi.NVSET_META
            )
        ],
        instance_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                alert_el, nvpair_multi.NVSET_INSTANCE
            )
        ],
    )


# DEPRECATED, used only in get_all_alerts_dict
def get_all_recipients_dict(alert: _Element) -> list[dict[str, Any]]:
    """
    Returns list of all recipient of specified alert. Format:
    [
        {
            "id": <id of recipient>,
            "value": <value of recipient>,
            "description": <recipient description>,
            "instance_attributes": <list of nvpairs>,
            "meta_attributes": <list of nvpairs>
        }
    ]

    alert -- parent element of recipients to return
    """
    return [
        {
            "id": recipient.get("id"),
            "value": recipient.get("value"),
            "description": recipient.get("description", ""),
            "instance_attributes": get_nvset(
                get_sub_element(recipient, "instance_attributes")
            ),
            "meta_attributes": get_nvset(
                get_sub_element(recipient, "meta_attributes")
            ),
        }
        for recipient in alert.findall("./recipient")
    ]


# DEPRECATED, use alert_el_to_dto + get_all_alert_elements
def get_all_alerts_dict(tree: _Element) -> list[dict[str, Any]]:
    """
    Returns list of all alerts specified in tree. Format:
    [
        {
            "id": <id of alert>,
            "path": <path to script>,
            "description": <alert description>,
            "instance_attributes": <list of nvpairs>,
            "meta_attributes": <list of nvpairs>,
            "recipients_list": <list of alert's recipients>
        }
    ]

    tree -- cib etree node
    """
    return [
        {
            "id": alert.get("id"),
            "path": alert.get("path"),
            "description": alert.get("description", ""),
            "instance_attributes": get_nvset(
                get_sub_element(alert, "instance_attributes")
            ),
            "meta_attributes": get_nvset(
                get_sub_element(alert, "meta_attributes")
            ),
            "recipient_list": get_all_recipients_dict(alert),
        }
        for alert in get_alerts(tree).findall("./alert")
    ]
