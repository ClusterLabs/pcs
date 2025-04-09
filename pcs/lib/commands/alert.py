from typing import TYPE_CHECKING, Any, Mapping, Optional

from pcs.common.pacemaker.alert import CibAlertListDto
from pcs.common.types import StringIterable
from pcs.lib.cib import alert
from pcs.lib.cib.nvpair import (
    arrange_first_instance_attributes,
    arrange_first_meta_attributes,
)
from pcs.lib.cib.rule.in_effect import get_rule_evaluator
from pcs.lib.cib.tools import (
    IdProvider,
    get_alerts,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

if TYPE_CHECKING:
    from pcs.common.reports import ReportItemList


def create_alert(
    # Path is mandatory, so it should not be optional. However, the current
    # code calling this function does not prevent it being None. The idea behind
    # that was, that the validation would happen in the lib command. Since
    # then, however, the paradigma got changed as we found out that a client
    # should actually be responsible for providing all mandatory parameters.
    # The interface cannot be simply changed, as backward compatibility must be
    # maintained for lib.commands. We still want to change it, but it needs to
    # be done in the proper way.
    lib_env: LibraryEnvironment,
    alert_id: Optional[str],
    path: Optional[str],
    instance_attribute_dict: Mapping[str, str],
    meta_attribute_dict: Mapping[str, str],
    description: Optional[str] = None,
) -> None:
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
    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)

    lib_env.report_processor.report_list(
        alert.validate_create_alert(id_provider, path, alert_id)
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()

    alert_el = alert.create_alert(
        cib,
        id_provider,
        str(path),  # if path were None, validation above would raise
        alert_id,
        description,
    )
    arrange_first_instance_attributes(
        alert_el, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(alert_el, meta_attribute_dict, id_provider)

    lib_env.push_cib()


def update_alert(
    lib_env: LibraryEnvironment,
    alert_id: str,
    path: Optional[str],
    instance_attribute_dict: Mapping[str, str],
    meta_attribute_dict: Mapping[str, str],
    description: Optional[str] = None,
) -> None:
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


def remove_alert(
    lib_env: LibraryEnvironment, alert_id_list: StringIterable
) -> None:
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
    # Recipient value is mandatory, so it should not be optional. However, the
    # current code calling this function does not prevent it being None. The
    # idea behind that was, that the validation would happen in the lib
    # command. Since then, however, the paradigma got changed as we found out
    # that a client should actually be responsible for providing all mandatory
    # parameters.
    # The interface cannot be simply changed, as backward compatibility must be
    # maintained for lib.commands. We still want to change it, but it needs to
    # be done in the proper way.
    lib_env: LibraryEnvironment,
    alert_id: str,
    recipient_value: Optional[str],
    instance_attribute_dict: Mapping[str, str],
    meta_attribute_dict: Mapping[str, str],
    recipient_id: Optional[str] = None,
    description: Optional[str] = None,
    allow_same_value: bool = False,
) -> None:
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
    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)
    alert_el = alert.find_alert(get_alerts(cib), alert_id)

    lib_env.report_processor.report_list(
        alert.validate_add_recipient(
            id_provider,
            alert_el,
            recipient_value,
            recipient_id,
            allow_same_value=allow_same_value,
        )
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()

    recipient_el = alert.add_recipient(
        id_provider,
        alert_el,
        # if recipient_value were None, validation above would raise
        str(recipient_value),
        recipient_id,
        description=description,
    )
    arrange_first_instance_attributes(
        recipient_el, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(
        recipient_el, meta_attribute_dict, id_provider
    )

    lib_env.push_cib()


def update_recipient(
    lib_env: LibraryEnvironment,
    recipient_id: str,
    instance_attribute_dict: Mapping[str, str],
    meta_attribute_dict: Mapping[str, str],
    recipient_value: Optional[str] = None,
    description: Optional[str] = None,
    allow_same_value: bool = False,
) -> None:
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
    cib = lib_env.get_cib()
    id_provider = IdProvider(cib)
    recipient_el = alert.find_recipient(get_alerts(cib), recipient_id)

    lib_env.report_processor.report_list(
        alert.validate_update_recipient(
            recipient_el,
            recipient_value,
            allow_same_value=allow_same_value,
        )
    )
    if lib_env.report_processor.has_errors:
        raise LibraryError()

    recipient = alert.update_recipient(
        recipient_el,
        recipient_value=recipient_value,
        description=description,
    )
    arrange_first_instance_attributes(
        recipient, instance_attribute_dict, id_provider
    )
    arrange_first_meta_attributes(recipient, meta_attribute_dict, id_provider)

    lib_env.push_cib()


def remove_recipient(
    lib_env: LibraryEnvironment, recipient_id_list: StringIterable
) -> None:
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


def get_config_dto(
    lib_env: LibraryEnvironment, evaluate_expired: bool = False
) -> CibAlertListDto:
    cib = lib_env.get_cib()
    rule_in_effect_eval = get_rule_evaluator(
        cib, lib_env.cmd_runner(), lib_env.report_processor, evaluate_expired
    )
    return CibAlertListDto(
        [
            alert.alert_el_to_dto(alert_el, rule_eval=rule_in_effect_eval)
            for alert_el in alert.get_all_alert_elements(get_alerts(cib))
        ]
    )


# DEPRECATED, use get_config_dto
def get_all_alerts(lib_env: LibraryEnvironment) -> list[dict[str, Any]]:
    """
    Returns list of all alerts. See docs of pcs.lib.cib.alert.get_all_alerts for
    description of data format.

    lib_env -- LibraryEnvironment
    """
    return alert.get_all_alerts_dict(lib_env.get_cib())
