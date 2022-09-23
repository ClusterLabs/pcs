from typing import (
    Dict,
    List,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import ReportItemList
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.types import StringSequence
from pcs.lib import (
    sbd,
    validate,
)
from pcs.lib.cib import nvpair_multi
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    get_crm_config,
    get_element_by_id,
    get_pacemaker_version_by_which_cib_was_validated,
)
from pcs.lib.resource_agent import ResourceAgentFacade

DEFAULT_CLUSTER_PROPERTY_SET_ID = "cib-bootstrap-options"
TAG_CRM_CONFIG = "crm_config"


def _validate_stonith_watchdog_timeout_property(
    service_manager: ServiceManagerInterface,
    value: str,
    force: bool = False,
) -> ReportItemList:
    report_list: ReportItemList = []
    if sbd.is_sbd_enabled(service_manager):
        report_list.extend(sbd.validate_stonith_watchdog_timeout(value, force))
    else:
        if value not in ["", "0"]:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.StonithWatchdogTimeoutCannotBeSet(
                        reports.const.SBD_NOT_SET_UP
                    ),
                )
            )
    return report_list


def validate_set_cluster_options(
    cluster_property_facade_list: List[ResourceAgentFacade],
    service_manager: ServiceManagerInterface,
    to_be_set_options: Dict[str, str],
    force: bool = False,
) -> ReportItemList:
    """
    Validate that cluster options and theirs values can be set.

    cluster_property_facade_list -- facades for cluster properties metadata
    service_manager -- manager for system daemon services
    to_be_set_options -- list of to be set cluster options
    force -- if True, validators produce a warning instead of an error
    """
    report_list: ReportItemList = []
    validators: List[validate.ValidatorInterface] = []
    possible_options_dict = {
        parameter.name: parameter
        for facade in cluster_property_facade_list
        for parameter in facade.metadata.parameters
    }
    severity = reports.get_severity(reports.codes.FORCE, force)
    validators.append(
        validate.NamesIn(
            possible_options_dict.keys(),
            option_type="cluster property",
            severity=severity,
        )
    )
    for option_name in to_be_set_options:
        try:
            option_metadata = possible_options_dict[option_name]
        except KeyError:
            # unknow options will be reported by a validator
            continue
        if option_metadata.name == "stonith-watchdog-timeout":
            # needs extra validation
            continue
        if option_metadata.type == "boolean":
            validators.append(
                validate.ValuePcmkBoolean(
                    option_metadata.name, severity=severity
                )
            )
        elif option_metadata.type == "integer":
            validators.append(
                validate.ValueInteger(option_metadata.name, severity=severity)
            )
        elif option_metadata.type == "percentage":
            validators.append(
                validate.ValuePcmkPercentage(
                    option_metadata.name, severity=severity
                )
            )
        elif option_metadata.type == "select":
            validators.append(
                validate.ValueIn(
                    option_metadata.name,
                    option_metadata.enum_values or [],
                    severity=severity,
                )
            )
        elif option_metadata.type == "time":
            validators.append(
                validate.ValueTimeInterval(
                    option_metadata.name, severity=severity
                )
            )
    report_list.extend(
        validate.ValidatorAll(validators).validate(to_be_set_options)
    )
    # more complex validation which depends on other configuration
    if "stonith-watchdog-timeout" in to_be_set_options:
        report_list.extend(
            _validate_stonith_watchdog_timeout_property(
                service_manager,
                to_be_set_options["stonith-watchdog-timeout"],
                force=force,
            )
        )
    return report_list


def validate_remove_cluster_option(
    configured_options: StringSequence,
    service_manager: ServiceManagerInterface,
    to_be_removed_options: StringSequence,
    force: bool = False,
) -> ReportItemList:
    """
    Validate that options to be removed exist in the current configuration and
    can be removed.

    configured_options -- current list of configured cluster options
    service_manager -- manager for system daemon services
    to_be_removed_options -- list of to be removed cluster options
    force -- if True, validators produce a warning instead of an error
    """
    report_list = validate.NamesExist(
        configured_options,
        option_type="cluster property",
        severity=reports.get_severity(reports.codes.FORCE, force),
    ).validate({option: "" for option in to_be_removed_options})
    if (
        "stonith-watchdog-timeout" in to_be_removed_options
        and "stonith-watchdog-timeout" in configured_options
    ):
        report_list.extend(
            _validate_stonith_watchdog_timeout_property(
                service_manager, "", force=force
            )
        )
    return report_list


def get_default_cluster_property_set_element(
    cib: _Element, id_provider: IdProvider
) -> _Element:
    """
    Return default cluster_property_set element. Options set in this element
    have the highest priority and cannot be overridden by other
    cluster_property_set elements and rules.

    If default cluster_property_set does not exists, which is very unlikely,
    then set element is created with the default id. Even if the default id of
    this set is used somewhere in the cib, then use a first available id value
    of "id-<counter>". This is the exact behaviour as in old architecture code.

    cib -- cib tree
    id_provider -- checks id uniqueness and books ids if set
    """
    try:
        cluster_property_set_el = get_element_by_id(
            cib, DEFAULT_CLUSTER_PROPERTY_SET_ID
        )
        parent = cluster_property_set_el.getparent()
        if parent is not None and parent.tag == TAG_CRM_CONFIG:
            return cluster_property_set_el
    except ElementNotFound:
        pass
    return nvpair_multi.nvset_append_new(
        get_crm_config(cib),
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        nvpair_multi.NVSET_PROPERTY,
        {},
        {"id": id_provider.allocate_id(DEFAULT_CLUSTER_PROPERTY_SET_ID)},
        nvset_rule=None,
    )
