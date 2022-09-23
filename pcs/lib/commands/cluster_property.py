from typing import (
    Container,
    Dict,
    List,
    Union,
)

from pcs.common import reports
from pcs.common.types import StringSequence
from pcs.lib import cluster_property
from pcs.lib.cib import nvpair_multi
from pcs.lib.cib.nvpair import get_nvset
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


def set_property(
    env: LibraryEnvironment,
    cluster_options: Dict[str, str],
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    cib = env.get_cib()
    service_manager = env.service_manager
    id_provider = IdProvider(cib)
    force = reports.codes.FORCE in force_flags
    property_facade_list = _get_property_facade_list(
        env.report_processor,
        ResourceAgentFacadeFactory(env.cmd_runner(), env.report_processor),
    )
    cluster_property_set_el = (
        cluster_property.get_default_cluster_property_set_element(
            cib, id_provider
        )
    )
    configured_options = [
        nvpair_dict["name"]
        for nvpair_dict in get_nvset(cluster_property_set_el)
    ]
    to_be_set_options = {
        option: value
        for option, value in cluster_options.items()
        if value != ""
    }
    to_be_removed_options = [
        option for option, value in cluster_options.items() if value == ""
    ]
    if env.report_processor.report_list(
        cluster_property.validate_set_cluster_options(
            property_facade_list,
            service_manager,
            to_be_set_options,
            force=force,
        )
        + cluster_property.validate_remove_cluster_option(
            configured_options,
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


def unset_property(
    env: LibraryEnvironment,
    cluster_options_list: StringSequence,
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    cib = env.get_cib()
    id_provider = IdProvider(cib)
    cluster_property_set_el = (
        cluster_property.get_default_cluster_property_set_element(
            cib, id_provider
        )
    )
    if env.report_processor.report_list(
        cluster_property.validate_remove_cluster_option(
            [
                nvpair_dict["name"]
                for nvpair_dict in get_nvset(cluster_property_set_el)
            ],
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
