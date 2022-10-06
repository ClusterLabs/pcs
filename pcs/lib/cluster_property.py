from typing import (
    Dict,
    List,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
)
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.types import StringSequence
from pcs.lib import (
    sbd,
    validate,
)
from pcs.lib.cib import nvpair_multi
from pcs.lib.cib.const import DEFAULT_CLUSTER_PROPERTY_SET_ID
from pcs.lib.cib.tools import (
    IdProvider,
    get_crm_config,
    get_pacemaker_version_by_which_cib_was_validated,
)
from pcs.lib.errors import LibraryError
from pcs.lib.resource_agent import ResourceAgentFacade


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


def validate_set_cluster_properties(
    cluster_property_facade_list: List[ResourceAgentFacade],
    service_manager: ServiceManagerInterface,
    to_be_set_options: Dict[str, str],
    force: bool = False,
) -> ReportItemList:
    """
    Validate that cluster options and their values can be set.

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
        if option_name not in possible_options_dict:
            # unknow options will be reported by a validator
            continue
        option_metadata = possible_options_dict[option_name]
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
                validate.ValuePcmkInteger(
                    option_metadata.name, severity=severity
                )
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


def validate_remove_cluster_properties(
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


def get_cluster_property_set_element_legacy(
    cib: _Element, id_provider: IdProvider
) -> _Element:
    """
    Return the first cluster_property_set element. If the element does not
    exist, try to create cluster_property_set element with id of value
    'cib-bootstrap-options'. Raise error in case of the id is already used.

    cib -- cib tree
    id_provider -- checks id uniqueness and books ids if set
    """
    crm_config_el = get_crm_config(cib)
    property_el_list = nvpair_multi.find_nvsets(
        crm_config_el, nvpair_multi.NVSET_PROPERTY
    )
    if property_el_list:
        return property_el_list[0]
    if id_provider.book_ids(DEFAULT_CLUSTER_PROPERTY_SET_ID):
        raise LibraryError(
            ReportItem.error(
                reports.messages.CannotCreateDefaultClusterPropertySet()
            )
        )
    return nvpair_multi.nvset_append_new(
        crm_config_el,
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        nvpair_multi.NVSET_PROPERTY,
        {},
        {"id": DEFAULT_CLUSTER_PROPERTY_SET_ID},
        nvset_rule=None,
    )
