from typing import (
    Iterable,
    Mapping,
    Optional,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.tools import timeout_to_seconds
from pcs.common.types import StringSequence
from pcs.lib import (
    sbd,
    validate,
)
from pcs.lib.cib import nvpair_multi
from pcs.lib.cib.tools import (
    IdProvider,
    get_crm_config,
    get_pacemaker_version_by_which_cib_was_validated,
)
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.values import is_false
from pcs.lib.resource_agent import ResourceAgentParameter

READONLY_CLUSTER_PROPERTY_LIST = [
    "cluster-infrastructure",
    "cluster-name",
    "dc-version",
    "have-watchdog",
    "last-lrm-refresh",
]
_DEFAULT_CLUSTER_PROPERTY_SET_ID = "cib-bootstrap-options"


def _validate_stonith_watchdog_timeout_property(
    service_manager: ServiceManagerInterface,
    value: str,
    force: bool = False,
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    original_value = value
    # if value is not empty, try to convert time interval string
    if value:
        seconds = timeout_to_seconds(value)
        if seconds is None:
            # returns empty list because this should be reported by
            # ValueTimeInterval validator
            return report_list
        value = str(seconds)
    if sbd.is_sbd_enabled(service_manager):
        report_list.extend(
            sbd.validate_stonith_watchdog_timeout(
                validate.ValuePair(original_value, value), force
            )
        )
    elif value not in ["", "0"]:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.StonithWatchdogTimeoutCannotBeSet(
                    reports.const.SBD_NOT_SET_UP
                ),
            )
        )
    return report_list


def _validate_not_disabling_fencing(
    to_be_set_properties: Mapping[str, str],
) -> Optional[reports.ReportItem]:
    problematic_properties_setting = {
        key: to_be_set_properties[key]
        for key in ["stonith-enabled", "fencing-enabled"]
        if key in to_be_set_properties and is_false(to_be_set_properties[key])
    }

    if problematic_properties_setting:
        return reports.ReportItem.warning(
            reports.messages.NoStonithMeansWouldBeLeftDueToProperties(
                problematic_properties_setting
            ),
        )

    return None


def validate_set_cluster_properties(  # noqa: PLR0912
    runner: CommandRunner,
    params_spec: Iterable[ResourceAgentParameter],
    properties_set_id: str,
    configured_properties: StringSequence,
    new_properties: Mapping[str, str],
    service_manager: ServiceManagerInterface,
    force: bool = False,
) -> reports.ReportItemList:
    """
    Validate that cluster properties and their values can be set.

    params_spec -- params specified by agent "cluster-options"
    properties_set_id -- id of the properties set to be updated
    configured_properties -- names of currently configured cluster properties
    new_properties -- dictionary of properties and their values to be set
    service_manager -- manager for system daemon services
    force -- if True, produce warnings instead of errors
    """
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    possible_properties_dict = {
        parameter.name: parameter
        for parameter in params_spec
        if parameter.name not in READONLY_CLUSTER_PROPERTY_LIST
    }
    severity = reports.get_severity(reports.codes.FORCE, force)

    to_be_set_properties = {}
    to_be_removed_properties = []
    for name, value in new_properties.items():
        if value != "":
            to_be_set_properties[name] = value
        else:
            to_be_removed_properties.append(name)

    report_list = validate.validate_set_unset_items(
        to_be_set_properties.keys(),
        to_be_removed_properties,
        configured_properties,
        reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
        reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
        properties_set_id,
        severity=severity,
    )

    report_list.extend(
        validate.NamesIn(
            possible_properties_dict.keys(),
            option_type="cluster property",
            banned_name_list=READONLY_CLUSTER_PROPERTY_LIST,
            severity=severity,
        ).validate(
            # Allow removing properties unknown to pacemaker while preventing
            # setting them. Prevent removing read-only properties.
            {
                name: value
                for name, value in new_properties.items()
                if not (
                    value == ""
                    and name not in READONLY_CLUSTER_PROPERTY_LIST
                    and name not in possible_properties_dict
                )
            }
        )
    )

    # Validators are based on pacemaker validation:
    #   * https://github.com/ClusterLabs/pacemaker/blob/main/lib/common/options.c
    # There are no pacemaker validators for these types:
    #   * string - just arbitrary strings
    #   * version - used only by pacemaker generated option 'dc-version'
    #   * epoch_time - type is not used at all
    validators: list[validate.ValidatorInterface] = []
    for property_name in to_be_set_properties:
        if property_name not in possible_properties_dict:
            # unknown properties are reported by NamesIn validator
            continue
        property_metadata = possible_properties_dict[property_name]
        if property_metadata.type == "boolean":
            validators.append(
                validate.ValuePcmkBoolean(
                    property_metadata.name, severity=severity
                )
            )
        elif property_metadata.type == "duration":
            validators.append(
                validate.ValueTimeIntervalOrDuration(
                    runner, property_metadata.name, severity=severity
                )
            )
        elif property_metadata.type in ["integer", "score"]:
            validators.append(
                validate.ValuePcmkInteger(
                    property_metadata.name, severity=severity
                )
            )
        elif property_metadata.type == "nonnegative_integer":
            validators.append(
                validate.ValuePcmkPositiveInteger(
                    property_metadata.name, severity=severity
                )
            )
        elif property_metadata.type == "percentage":
            validators.append(
                validate.ValuePcmkPercentage(
                    property_metadata.name, severity=severity
                )
            )
        elif property_metadata.type == "port":
            validators.append(
                validate.ValuePortNumber(
                    property_metadata.name, severity=severity
                )
            )
        elif property_metadata.type == "select":
            validators.append(
                validate.ValueIn(
                    property_metadata.name,
                    property_metadata.enum_values or [],
                    severity=severity,
                )
            )
        elif property_metadata.type in ["time", "timeout"]:
            # make stonith-watchdog-timeout value not forcable
            if property_metadata.name == "stonith-watchdog-timeout":
                validators.append(
                    validate.ValueTimeInterval(
                        property_metadata.name,
                        severity=reports.ReportItemSeverity.error(),
                    )
                )
            elif property_metadata.type == "timeout":
                validators.append(
                    validate.ValueTimeInterval(
                        property_metadata.name, severity=severity
                    )
                )
            else:  # time
                validators.append(
                    validate.ValueTimeIntervalOrDuration(
                        runner, property_metadata.name, severity=severity
                    )
                )

    report_list.extend(
        validate.ValidatorAll(validators).validate(to_be_set_properties)
    )

    # Only validate SWT if it is being set, or if it is being removed and it
    # actually exists in the current configuration.
    if "stonith-watchdog-timeout" in new_properties and (
        new_properties["stonith-watchdog-timeout"]
        or "stonith-watchdog-timeout" in configured_properties
    ):
        report_list.extend(
            _validate_stonith_watchdog_timeout_property(
                service_manager,
                new_properties["stonith-watchdog-timeout"],
                force=force,
            )
        )

    no_fencing_report = _validate_not_disabling_fencing(to_be_set_properties)
    if no_fencing_report:
        report_list.append(no_fencing_report)

    return report_list


def get_cluster_property_set_element_legacy(
    cib: _Element, id_provider: IdProvider
) -> _Element:
    """
    Return the first cluster_property_set element. If the element does not
    exist, try to create cluster_property_set element with id of value
    'cib-bootstrap-options'. Raise an error in case the id is already used.

    cib -- cib tree
    id_provider -- checks id uniqueness and books ids if set
    """
    crm_config_el = get_crm_config(cib)
    property_el_list = nvpair_multi.find_nvsets(
        crm_config_el, nvpair_multi.NVSET_PROPERTY
    )
    if property_el_list:
        return property_el_list[0]
    if id_provider.book_ids(_DEFAULT_CLUSTER_PROPERTY_SET_ID):
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.CannotCreateDefaultClusterPropertySet(
                    _DEFAULT_CLUSTER_PROPERTY_SET_ID
                )
            )
        )
    return nvpair_multi.nvset_append_new(
        crm_config_el,
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        nvpair_multi.NVSET_PROPERTY,
        {},
        {"id": _DEFAULT_CLUSTER_PROPERTY_SET_ID},
        nvset_rule=None,
    )
