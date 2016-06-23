from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports
from pcs.lib.cib import alert
from pcs.lib.errors import LibraryError


REQUIRED_CIB_VERSION = (2, 5, 0)


def create_alert(
    lib_env,
    alert_id,
    path,
    instance_attribute_dict,
    meta_attribute_dict,
    description=None
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
        raise LibraryError(reports.required_option_is_missing("path"))

    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)

    alert_el = alert.create_alert(cib, alert_id, path, description)
    alert.update_instance_attributes(cib, alert_el, instance_attribute_dict)
    alert.update_meta_attributes(cib, alert_el, meta_attribute_dict)

    lib_env.push_cib(cib)


def update_alert(
    lib_env,
    alert_id,
    path,
    instance_attribute_dict,
    meta_attribute_dict,
    description=None
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
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)

    alert_el = alert.update_alert(cib, alert_id, path, description)
    alert.update_instance_attributes(cib, alert_el, instance_attribute_dict)
    alert.update_meta_attributes(cib, alert_el, meta_attribute_dict)

    lib_env.push_cib(cib)


def remove_alert(lib_env, alert_id):
    """
    Remove alert with specified id.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert which should be removed
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    alert.remove_alert(cib, alert_id)
    lib_env.push_cib(cib)


def add_recipient(
    lib_env,
    alert_id,
    recipient_value,
    instance_attribute_dict,
    meta_attribute_dict,
    description=None
):
    """
    Add new recipient to alert witch id alert_id.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert to which new recipient should be added
    recipient_value -- value of new recipient
    instance_attribute_dict -- dictionary of instance attributes to update
    meta_attribute_dict -- dictionary of meta attributes to update
    description -- recipient description
    """
    if not recipient_value:
        raise LibraryError(
            reports.required_option_is_missing("value")
        )

    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    recipient = alert.add_recipient(
        cib, alert_id, recipient_value, description
    )
    alert.update_instance_attributes(cib, recipient, instance_attribute_dict)
    alert.update_meta_attributes(cib, recipient, meta_attribute_dict)

    lib_env.push_cib(cib)


def update_recipient(
    lib_env,
    alert_id,
    recipient_value,
    instance_attribute_dict,
    meta_attribute_dict,
    description=None
):
    """
    Update existing recipient.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert to which recipient belong
    recipient_value -- recipient to be updated
    instance_attribute_dict -- dictionary of instance attributes to update
    meta_attribute_dict -- dictionary of meta attributes to update
    description -- new description, if empty string, old description will be
        deleted, if None old value will stay unchanged
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    recipient = alert.update_recipient(
        cib, alert_id, recipient_value, description
    )
    alert.update_instance_attributes(cib, recipient, instance_attribute_dict)
    alert.update_meta_attributes(cib, recipient, meta_attribute_dict)

    lib_env.push_cib(cib)


def remove_recipient(lib_env, alert_id, recipient_value):
    """
    Remove existing recipient.

    lib_env -- LibraryEnvironment
    alert_id -- id of alert to which recipient belong
    recipient_value -- recipient to be removed
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    alert.remove_recipient(cib, alert_id, recipient_value)
    lib_env.push_cib(cib)


def get_all_alerts(lib_env):
    """
    Returns list of all alerts. See docs of pcs.lib.cib.alert.get_all_alerts for
    description of data format.

    lib_env -- LibraryEnvironment
    """
    return alert.get_all_alerts(lib_env.get_cib())
