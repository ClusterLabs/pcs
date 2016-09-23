from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree
from functools import partial

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity as Severities
from pcs.lib.cib.nvpair import arrange_first_nvset, get_nvset
from pcs.lib.cib.tools import (
    check_new_id_applicable,
    get_sub_element,
    find_unique_id,
    get_alerts,
    validate_id_does_not_exist,
)


update_instance_attributes = partial(
    arrange_first_nvset,
    "instance_attributes"
)
update_meta_attributes = partial(arrange_first_nvset, "meta_attributes")

def _update_optional_attribute(element, attribute, value):
    """
    Update optional attribute of element. Remove existing element if value
    is empty.

    element -- parent element of specified attribute
    attribute -- attribute to be updated
    value -- new value
    """
    if value is None:
        return
    if value:
        element.set(attribute, value)
    elif attribute in element.attrib:
        del element.attrib[attribute]


def get_alert_by_id(tree, alert_id):
    """
    Returns alert element with specified id.
    Raises LibraryError if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert
    """
    alert = get_alerts(tree).find("./alert[@id='{0}']".format(alert_id))
    if alert is None:
        raise LibraryError(reports.cib_alert_not_found(alert_id))
    return alert


def get_recipient_by_id(tree, recipient_id):
    """
    Returns recipient element with value recipient_value which belong to
    specified alert.
    Raises LibraryError if recipient doesn't exist.

    tree -- cib etree node
    recipient_id -- id of recipient
    """
    recipient = get_alerts(tree).find(
        "./alert/recipient[@id='{0}']".format(recipient_id)
    )
    if recipient is None:
        raise LibraryError(reports.id_not_found(recipient_id, "Recipient"))
    return recipient


def ensure_recipient_value_is_unique(
    reporter, alert, recipient_value, recipient_id="", allow_duplicity=False
):
    """
    Ensures that recipient_value is unique in alert.

    reporter -- report processor
    alert -- alert
    recipient_value -- recipient value
    recipient_id -- recipient id of to which value belongs to
    allow_duplicity -- if True only warning will be shown if value already
        exists
    """
    recipient_list = alert.xpath(
        "./recipient[@value='{value}' and @id!='{id}']".format(
            value=recipient_value, id=recipient_id
        )
    )
    if recipient_list:
        reporter.process(reports.cib_alert_recipient_already_exists(
            alert.get("id", None),
            recipient_value,
            Severities.WARNING if allow_duplicity else Severities.ERROR,
            forceable=(
                None if allow_duplicity
                else report_codes.FORCE_ALERT_RECIPIENT_VALUE_NOT_UNIQUE
            )
        ))


def create_alert(tree, alert_id, path, description=""):
    """
    Create new alert element. Returns newly created element.
    Raises LibraryError if element with specified id already exists.

    tree -- cib etree node
    alert_id -- id of new alert, it will be generated if it is None
    path -- path to script
    description -- description
    """
    if alert_id:
        check_new_id_applicable(tree, "alert-id", alert_id)
    else:
        alert_id = find_unique_id(tree, "alert")

    alert = etree.SubElement(get_alerts(tree), "alert", id=alert_id, path=path)
    if description:
        alert.set("description", description)

    return alert


def update_alert(tree, alert_id, path, description=None):
    """
    Update existing alert. Return updated alert element.
    Raises LibraryError if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert to be updated
    path -- new value of path, stay unchanged if None
    description -- new value of description, stay unchanged if None, remove
        if empty
    """
    alert = get_alert_by_id(tree, alert_id)
    if path:
        alert.set("path", path)
    _update_optional_attribute(alert, "description", description)
    return alert


def remove_alert(tree, alert_id):
    """
    Remove alert with specified id.
    Raises LibraryError if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert which should be removed
    """
    alert = get_alert_by_id(tree, alert_id)
    alert.getparent().remove(alert)


def add_recipient(
    reporter,
    tree,
    alert_id,
    recipient_value,
    recipient_id=None,
    description="",
    allow_same_value=False
):
    """
    Add recipient to alert with specified id. Returns added recipient element.
    Raises LibraryError if alert with specified recipient_id doesn't exist.
    Raises LibraryError if recipient already exists.

    reporter -- report processor
    tree -- cib etree node
    alert_id -- id of alert which should be parent of new recipient
    recipient_value -- value of recipient
    recipient_id -- id of new recipient, if None it will be generated
    description -- description of recipient
    allow_same_value -- if True unique recipient value is not required
    """
    if recipient_id is None:
        recipient_id = find_unique_id(tree, "{0}-recipient".format(alert_id))
    else:
        validate_id_does_not_exist(tree, recipient_id)

    alert = get_alert_by_id(tree, alert_id)
    ensure_recipient_value_is_unique(
        reporter, alert, recipient_value, allow_duplicity=allow_same_value
    )
    recipient = etree.SubElement(
        alert, "recipient", id=recipient_id, value=recipient_value
    )

    if description:
        recipient.set("description", description)

    return recipient


def update_recipient(
    reporter,
    tree,
    recipient_id,
    recipient_value=None,
    description=None,
    allow_same_value=False
):
    """
    Update specified recipient. Returns updated recipient element.
    Raises LibraryError if recipient doesn't exist.

    reporter -- report processor
    tree -- cib etree node
    recipient_id -- id of recipient to be updated
    recipient_value -- recipient value, stay unchanged if None
    description -- description, if empty it will be removed, stay unchanged
        if None
    allow_same_value -- if True unique recipient value is not required
    """
    recipient = get_recipient_by_id(tree, recipient_id)
    if recipient_value is not None:
        ensure_recipient_value_is_unique(
            reporter,
            recipient.getparent(),
            recipient_value,
            recipient_id=recipient_id,
            allow_duplicity=allow_same_value
        )
        recipient.set("value", recipient_value)
    _update_optional_attribute(recipient, "description", description)
    return recipient


def remove_recipient(tree, recipient_id):
    """
    Remove specified recipient.
    Raises LibraryError if recipient doesn't exist.

    tree -- cib etree node
    recipient_id -- id of recipient to be removed
    """
    recipient = get_recipient_by_id(tree, recipient_id)
    recipient.getparent().remove(recipient)


def get_all_recipients(alert):
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
    recipient_list = []
    for recipient in alert.findall("./recipient"):
        recipient_list.append({
            "id": recipient.get("id"),
            "value": recipient.get("value"),
            "description": recipient.get("description", ""),
            "instance_attributes": get_nvset(
                get_sub_element(recipient, "instance_attributes")
            ),
            "meta_attributes": get_nvset(
                get_sub_element(recipient, "meta_attributes")
            )
        })
    return recipient_list


def get_all_alerts(tree):
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
    alert_list = []
    for alert in get_alerts(tree).findall("./alert"):
        alert_list.append({
            "id": alert.get("id"),
            "path": alert.get("path"),
            "description": alert.get("description", ""),
            "instance_attributes": get_nvset(
                get_sub_element(alert, "instance_attributes")
            ),
            "meta_attributes": get_nvset(
                get_sub_element(alert, "meta_attributes")
            ),
            "recipient_list": get_all_recipients(alert)
        })
    return alert_list
