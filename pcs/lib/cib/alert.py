from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.cib.nvpair import update_nvset, get_nvset
from pcs.lib.cib.tools import (
    check_new_id_applicable,
    get_sub_element,
    find_unique_id,
    get_alerts,
)


def update_instance_attributes(tree, element, attribute_dict):
    """
    Updates instance attributes of element. Returns updated instance
    attributes element.

    tree -- cib etree node
    element -- parent element of instance attributes
    attribute_dict -- dictionary of nvpairs
    """
    return update_nvset("instance_attributes", tree, element, attribute_dict)


def update_meta_attributes(tree, element, attribute_dict):
    """
    Updates meta attributes of element. Returns updated meta attributes element.

    tree -- cib etree node
    element -- parent element of meta attributes
    attribute_dict -- dictionary of nvpairs
    """
    return update_nvset("meta_attributes", tree, element, attribute_dict)


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
    Raises AlertNotFound if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert
    """
    alert = get_alerts(tree).find("./alert[@id='{0}']".format(alert_id))
    if alert is None:
        raise LibraryError(reports.cib_alert_not_found(alert_id))
    return alert


def get_recipient(alert, recipient_value):
    """
    Returns recipient element with value recipient_value which belong to
    specified alert.
    Raises RecipientNotFound if recipient doesn't exist.

    alert -- parent element of required recipient
    recipient_value -- value of recipient
    """
    recipient = alert.find(
        "./recipient[@value='{0}']".format(recipient_value)
    )
    if recipient is None:
        raise LibraryError(reports.cib_alert_recipient_not_found(
            alert.get("id"), recipient_value
        ))
    return recipient


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
    Raises AlertNotFound if alert with specified id doesn't exist.

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
    Raises AlertNotFound if alert with specified id doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert which should be removed
    """
    alert = get_alert_by_id(tree, alert_id)
    alert.getparent().remove(alert)


def add_recipient(
    tree,
    alert_id,
    recipient_value,
    description=""
):
    """
    Add recipient to alert with specified id. Returns added recipient element.
    Raises AlertNotFound if alert with specified id doesn't exist.
    Raises LibraryError if recipient already exists.

    tree -- cib etree node
    alert_id -- id of alert which should be parent of new recipient
    recipient_value -- value of recipient
    description -- description of recipient
    """
    alert = get_alert_by_id(tree, alert_id)

    recipient = alert.find(
        "./recipient[@value='{0}']".format(recipient_value)
    )
    if recipient is not None:
        raise LibraryError(reports.cib_alert_recipient_already_exists(
            alert_id, recipient_value
        ))

    recipient = etree.SubElement(
        alert,
        "recipient",
        id=find_unique_id(tree, "{0}-recipient".format(alert_id)),
        value=recipient_value
    )

    if description:
        recipient.set("description", description)

    return recipient


def update_recipient(tree, alert_id, recipient_value, description):
    """
    Update specified recipient. Returns updated recipient element.
    Raises AlertNotFound if alert with specified id doesn't exist.
    Raises RecipientNotFound if recipient doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert, parent element of recipient
    recipient_value -- recipient value
    description -- description, if empty it will be removed, stay unchanged
        if None
    """
    recipient = get_recipient(
        get_alert_by_id(tree, alert_id), recipient_value
    )
    _update_optional_attribute(recipient, "description", description)
    return recipient


def remove_recipient(tree, alert_id, recipient_value):
    """
    Remove specified recipient.
    Raises AlertNotFound if alert with specified id doesn't exist.
    Raises RecipientNotFound if recipient doesn't exist.

    tree -- cib etree node
    alert_id -- id of alert, parent element of recipient
    recipient_value -- recipient value
    """
    recipient = get_recipient(
        get_alert_by_id(tree, alert_id), recipient_value
    )
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
