from collections import Counter
from typing import (
    Container,
    Dict,
    List,
    Union,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringSequence
from pcs.lib import cluster_property
from pcs.lib.cib import (
    nvpair_multi,
    rule,
)
from pcs.lib.cib.tools import IdProvider
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.resource_agent import (
    ResourceAgentFacade,
    ResourceAgentMetadata,
    UnableToGetAgentMetadata,
    UnsupportedOcfVersion,
)
from pcs.lib.resource_agent import const as ra_const
from pcs.lib.resource_agent import resource_agent_error_to_report_item
from pcs.lib.resource_agent.facade import ResourceAgentFacadeFactory


def _get_property_facade_list(
    report_processor: reports.ReportProcessor,
    factory: ResourceAgentFacadeFactory,
) -> List[ResourceAgentFacade]:
    pacemaker_daemons = [
        ra_const.PACEMAKER_BASED,
        ra_const.PACEMAKER_CONTROLD,
        ra_const.PACEMAKER_SCHEDULERD,
    ]
    cluster_property_facade_list = []
    for daemon in pacemaker_daemons:
        try:
            cluster_property_facade_list.append(
                factory.facade_from_pacemaker_daemon_name(daemon)
            )
        except (UnableToGetAgentMetadata, UnsupportedOcfVersion) as e:
            report_processor.report_list(
                [
                    resource_agent_error_to_report_item(
                        e, reports.ReportItemSeverity.error()
                    )
                ]
            )
    if report_processor.has_errors:
        raise LibraryError()
    return cluster_property_facade_list


# backward compatibility layer - export cluster property metadata in the legacy
# format
def _cluster_property_metadata_to_dict(
    metadata: ResourceAgentMetadata,
) -> Dict[str, Dict[str, Union[bool, str, StringSequence]]]:
    banned_props = ["dc-version", "cluster-infrastructure"]
    basic_props = [
        "batch-limit",
        "no-quorum-policy",
        "symmetric-cluster",
        "enable-acl",
        "stonith-enabled",
        "stonith-action",
        "pe-input-series-max",
        "stop-orphan-resources",
        "stop-orphan-actions",
        "cluster-delay",
        "start-failure-is-fatal",
        "pe-error-series-max",
        "pe-warn-series-max",
    ]
    readable_names = {
        "batch-limit": "Batch Limit",
        "no-quorum-policy": "No Quorum Policy",
        "symmetric-cluster": "Symmetric",
        "stonith-enabled": "Stonith Enabled",
        "stonith-action": "Stonith Action",
        "cluster-delay": "Cluster Delay",
        "stop-orphan-resources": "Stop Orphan Resources",
        "stop-orphan-actions": "Stop Orphan Actions",
        "start-failure-is-fatal": "Start Failure is Fatal",
        "pe-error-series-max": "PE Error Storage",
        "pe-warn-series-max": "PE Warning Storage",
        "pe-input-series-max": "PE Input Storage",
        "enable-acl": "Enable ACLs",
    }
    property_definition = {}
    for parameter in metadata.parameters:
        if parameter.name in banned_props:
            continue
        single_property_dict: Dict[str, Union[bool, str, StringSequence]] = {
            "name": parameter.name,
            "shortdesc": parameter.shortdesc or "",
            "longdesc": parameter.longdesc or "",
            "type": parameter.type,
            "default": parameter.default or "",
            "advanced": parameter.name not in basic_props or parameter.advanced,
            "readable_name": readable_names.get(parameter.name, parameter.name),
            "source": metadata.name.type,
        }
        if parameter.enum_values is not None:
            single_property_dict["enum"] = parameter.enum_values
            single_property_dict["type"] = "enum"
        property_definition[parameter.name] = single_property_dict
    return property_definition


def get_cluster_properties_definition_legacy(
    env: LibraryEnvironment,
) -> Dict[str, Dict[str, Union[bool, str, StringSequence]]]:
    """
    Return cluster properties definition in the legacy dictionary format.

    env -- provides communication with externals
    """
    facade_factory = ResourceAgentFacadeFactory(
        env.cmd_runner(), env.report_processor
    )
    property_dict = {}
    for facade in _get_property_facade_list(
        env.report_processor, facade_factory
    ):
        property_dict.update(
            _cluster_property_metadata_to_dict(facade.metadata)
        )
    return property_dict


def _configured_options(cluster_property_set_el: _Element) -> List[str]:
    return [
        nvpair_dto.name
        for nvpair_dto in nvpair_multi.nvset_element_to_dto(
            cluster_property_set_el, rule.RuleInEffectEvalDummy()
        ).nvpairs
    ]


def _report_items_not_specified(container_id: str) -> reports.ReportItem:
    return reports.ReportItem.error(
        reports.messages.AddRemoveItemsNotSpecified(
            reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
            reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
            container_id,
        )
    )


def set_property(
    env: LibraryEnvironment,
    cluster_options: Dict[str, str],
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    """
    Set specific pacemaker cluster properties specified in the cluster_options
    dictionary. Properties with empty values are removed.

    env -- provides communication with externals
    cluster_options -- dictionary of cluster property names and values
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    service_manager = env.service_manager
    id_provider = IdProvider(cib)
    force = reports.codes.FORCE in force_flags
    property_facade_list = _get_property_facade_list(
        env.report_processor,
        ResourceAgentFacadeFactory(env.cmd_runner(), env.report_processor),
    )
    cluster_property_set_el = (
        cluster_property.get_cluster_property_set_element_legacy(
            cib, id_provider
        )
    )
    if not cluster_options:
        env.report_processor.report(
            _report_items_not_specified(cluster_property_set_el.get("id", ""))
        )
        raise LibraryError()

    to_be_set_options = {}
    to_be_removed_options = []
    for option, value in cluster_options.items():
        if value != "":
            to_be_set_options[option] = value
        else:
            to_be_removed_options.append(option)

    if env.report_processor.report_list(
        cluster_property.validate_set_cluster_properties(
            property_facade_list,
            service_manager,
            to_be_set_options,
            force=force,
        )
        + cluster_property.validate_remove_cluster_properties(
            _configured_options(cluster_property_set_el),
            service_manager,
            to_be_removed_options,
            force=force,
        )
    ).has_errors:
        raise LibraryError()
    nvpair_multi.nvset_update(
        cluster_property_set_el,
        id_provider,
        cluster_options,
    )
    env.push_cib()


def _report_duplicate_items(
    item_list: StringSequence, container_id: str, force: bool
) -> reports.ReportItemList:
    duplicates = {
        item for item, count in Counter(item_list).items() if count > 1
    }
    if duplicates:
        return [
            reports.ReportItem(
                severity=reports.get_severity(reports.codes.FORCE, force),
                message=reports.messages.AddRemoveItemsDuplication(
                    reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id,
                    sorted(duplicates),
                ),
            )
        ]
    return []


def unset_property(
    env: LibraryEnvironment,
    cluster_options_list: StringSequence,
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    """
    Remove cluster properties specified in the cluster_options_list.

    env -- provides communication with externals
    cluster_options_list -- list of cluster property names to be removed
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    id_provider = IdProvider(cib)
    cluster_property_set_el = (
        cluster_property.get_cluster_property_set_element_legacy(
            cib, id_provider
        )
    )
    set_id = cluster_property_set_el.get("id", "")
    if not cluster_options_list:
        env.report_processor.report(_report_items_not_specified(set_id))
        raise LibraryError()
    env.report_processor.report_list(
        _report_duplicate_items(
            cluster_options_list, set_id, reports.codes.FORCE in force_flags
        )
    )
    if env.report_processor.report_list(
        cluster_property.validate_remove_cluster_properties(
            _configured_options(cluster_property_set_el),
            env.service_manager,
            cluster_options_list,
            force=reports.codes.FORCE in force_flags,
        )
    ).has_errors:
        raise LibraryError()
    nvpair_multi.nvset_update(
        cluster_property_set_el,
        id_provider,
        {option: "" for option in cluster_options_list},
    )
    env.push_cib()
