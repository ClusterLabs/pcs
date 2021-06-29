from pcs.common import reports
from pcs.common.reports import ReportItemList
from pcs.common.reports.item import ReportItem
from pcs.lib.cib import alert
from pcs.lib.cib.nvpair import (
    arrange_first_instance_attributes,
    arrange_first_meta_attributes,
)
from pcs.lib.cib.tools import IdProvider
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def create_alert(
    lib_env: LibraryEnvironment,
    alert_id,
    path,
    instance_attribute_dict,
    meta_attribute_dict,
    description=None,
):
    """
    Create new alert.
    Raises LibraryError if path is not specified, or any other failure.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert to be created, if None it will be generated
    path -- path to script for alert
    instance_attribute_dict -- dictionary of instance attributes
    meta_attribute_dict -- dictionary of meta attributes
    description -- alert description description
    """
    if not path:
        raise LibraryError(
            ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["path"])
            )
        )

    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)
    alert_el = alert.create_alert(cib, alert_id, path, description)
    arrange_first_instance_attributes(
        alert_el, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(alert_el, meta_attribute_dict, id_provider)

    lib_env.push_cib()


def update_alert(
    lib_env: LibraryEnvironment,
    alert_id,
    path,
    instance_attribute_dict,
    meta_attribute_dict,
    description=None,
):
    """
    Update existing alert with specified id.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert to be updated
    path -- new path, if None old value will stay unchanged
    instance_attribute_dict -- dictionary of instance attributes to update
    meta_attribute_dict -- dictionary of meta attributes to update
    description -- new description, if empty string, old description will be
        deleted, if None old value will stay unchanged
    """

    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)
    alert_el = alert.update_alert(cib, alert_id, path, description)
    arrange_first_instance_attributes(
        alert_el, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(alert_el, meta_attribute_dict, id_provider)

    lib_env.push_cib()


def remove_alert(lib_env: LibraryEnvironment, alert_id_list):
    """
    Remove alerts with specified ids.

    lib_env -- LibraryEnvironment
    alert_id_list -- list of alerts ids which should be removed
    """
    cib = lib_env.get_cib()
    report_list: ReportItemList = []
    for alert_id in alert_id_list:
        try:
            alert.remove_alert(cib, alert_id)
        except LibraryError as e:
            report_list += e.args

    if lib_env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    lib_env.push_cib()


def add_recipient(
    lib_env: LibraryEnvironment,
    alert_id,
    recipient_value,
    instance_attribute_dict,
    meta_attribute_dict,
    recipient_id=None,
    description=None,
    allow_same_value=False,
):
    """
    Add new recipient to alert witch id alert_id.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert to which new recipient should be added
    recipient_value -- value of new recipient
    instance_attribute_dict -- dictionary of instance attributes to update
    meta_attribute_dict -- dictionary of meta attributes to update
    recipient_id -- id of new recipient, if None it will be generated
    description -- recipient description
    allow_same_value -- if True unique recipient value is not required
    """
    if not recipient_value:
        raise LibraryError(
            ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["value"])
            )
        )

    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)
    recipient = alert.add_recipient(
        lib_env.report_processor,
        cib,
        alert_id,
        recipient_value,
        recipient_id=recipient_id,
        description=description,
        allow_same_value=allow_same_value,
    )
    arrange_first_instance_attributes(
        recipient, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(recipient, meta_attribute_dict, id_provider)

    lib_env.push_cib()


def update_recipient(
    lib_env: LibraryEnvironment,
    recipient_id,
    instance_attribute_dict,
    meta_attribute_dict,
    recipient_value=None,
    description=None,
    allow_same_value=False,
):
    """
    Update existing recipient.

    lib_env -- LibraryEnvironment
    recipient_id -- id of recipient to be updated
    instance_attribute_dict -- dictionary of instance attributes to update
    meta_attribute_dict -- dictionary of meta attributes to update
    recipient_value -- new recipient value, if None old value will stay
        unchanged
    description -- new description, if empty string, old description will be
        deleted, if None old value will stay unchanged
    allow_same_value -- if True unique recipient value is not required
    """
    if not recipient_value and recipient_value is not None:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibAlertRecipientValueInvalid(recipient_value)
            )
        )
    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)
    recipient = alert.update_recipient(
        lib_env.report_processor,
        cib,
        recipient_id,
        recipient_value=recipient_value,
        description=description,
        allow_same_value=allow_same_value,
    )
    arrange_first_instance_attributes(
        recipient, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(recipient, meta_attribute_dict, id_provider)

    lib_env.push_cib()


def remove_recipient(lib_env: LibraryEnvironment, recipient_id_list):
    """
    Remove specified recipients.

    lib_env -- LibraryEnvironment
    recipient_id_list -- list of recipients ids to be removed
    """
    cib = lib_env.get_cib()
    report_list: ReportItemList = []
    for recipient_id in recipient_id_list:
        try:
            alert.remove_recipient(cib, recipient_id)
        except LibraryError as e:
            report_list += e.args
    if lib_env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    lib_env.push_cib()


def get_all_alerts(lib_env: LibraryEnvironment):
    """
    Returns list of all alerts. See docs of pcs.lib.cib.alert.get_all_alerts for
    description of data format.

    lib_env -- LibraryEnvironment
    """
    return alert.get_all_alerts(lib_env.get_cib())
