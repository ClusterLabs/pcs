from typing import (
    Collection,
    Mapping,
    Union,
)

from pcs.common import reports
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import ListCibNvsetDto
from pcs.common.types import StringSequence
from pcs.lib import cluster_property
from pcs.lib.cib import (
    nvpair_multi,
    rule,
)
from pcs.lib.cib.rule.in_effect import get_rule_evaluator
from pcs.lib.cib.tools import (
    IdProvider,
    get_crm_config,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.resource_agent import (
    ResourceAgentError,
    ResourceAgentFacade,
    ResourceAgentMetadata,
)
from pcs.lib.resource_agent import const as ra_const
from pcs.lib.resource_agent import resource_agent_error_to_report_item
from pcs.lib.resource_agent.facade import ResourceAgentFacadeFactory


def _get_property_facade_list(
    report_processor: reports.ReportProcessor,
    factory: ResourceAgentFacadeFactory,
) -> list[ResourceAgentFacade]:
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
        except ResourceAgentError as e:
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
) -> dict[str, dict[str, Union[bool, str, StringSequence]]]:
    banned_props = ["dc-version", "cluster-infrastructure"]
    basic_props = {
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
        single_property_dict: dict[str, Union[bool, str, StringSequence]] = {
            "name": parameter.name,
            "shortdesc": parameter.shortdesc or "",
            "longdesc": parameter.longdesc or "",
            "type": parameter.type,
            "default": parameter.default or "",
            "advanced": parameter.name not in basic_props or parameter.advanced,
            "readable_name": basic_props.get(parameter.name, parameter.name),
            "source": metadata.name.type,
        }
        if parameter.enum_values is not None:
            single_property_dict["enum"] = parameter.enum_values
            single_property_dict["type"] = "enum"
        property_definition[parameter.name] = single_property_dict
    return property_definition


def get_cluster_properties_definition_legacy(
    env: LibraryEnvironment,
) -> dict[str, dict[str, Union[bool, str, StringSequence]]]:
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


def set_properties(
    env: LibraryEnvironment,
    cluster_properties: Mapping[str, str],
    force_flags: Collection[reports.types.ForceCode] = (),
) -> None:
    """
    Set specified pacemaker cluster properties, remove those with empty values.

    env -- provides communication with externals
    cluster_properties -- dictionary of cluster property names and values
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    id_provider = IdProvider(cib)
    force = reports.codes.FORCE in force_flags
    cluster_property_set_el = (
        cluster_property.get_cluster_property_set_element_legacy(
            cib, id_provider
        )
    )
    set_id = cluster_property_set_el.get("id", "")

    property_facade_list = _get_property_facade_list(
        env.report_processor,
        ResourceAgentFacadeFactory(env.cmd_runner(), env.report_processor),
    )

    configured_properties = [
        nvpair_dto.name
        for nvpair_dto in nvpair_multi.nvset_element_to_dto(
            cluster_property_set_el,
            rule.RuleInEffectEvalDummy(),
        ).nvpairs
    ]

    env.report_processor.report_list(
        cluster_property.validate_set_cluster_properties(
            property_facade_list,
            set_id,
            configured_properties,
            cluster_properties,
            env.service_manager,
            force=force,
        )
    )

    if env.report_processor.has_errors:
        raise LibraryError()

    nvpair_multi.nvset_update(
        cluster_property_set_el,
        id_provider,
        cluster_properties,
    )
    env.push_cib()


def get_properties(
    env: LibraryEnvironment, evaluate_expired: bool = False
) -> ListCibNvsetDto:
    """
    Get configured pacemaker cluster properties.

    env -- provides communication with externals
    evaluate_expired -- also evaluate whether rules are expired or in effect
    """
    cib = env.get_cib()
    rule_in_effect_eval = get_rule_evaluator(
        cib, env.cmd_runner(), env.report_processor, evaluate_expired
    )
    nvset_list = nvpair_multi.find_nvsets(
        get_crm_config(cib), nvpair_multi.NVSET_PROPERTY
    )
    return ListCibNvsetDto(
        nvsets=[
            nvpair_multi.nvset_element_to_dto(nvset_el, rule_in_effect_eval)
            for nvset_el in nvset_list
        ]
    )


def get_properties_metadata(
    env: LibraryEnvironment,
) -> ClusterPropertyMetadataDto:
    """
    Get pacemaker cluster properties metadata.

    Metadata is received in OCF 1.1 format from pacemaker daemons
    pacemaker-based, pacemaker-controld and pacemaker-schedulerd.

    env -- provides communication with externals
    """
    property_definition_list = []
    for facade in _get_property_facade_list(
        env.report_processor,
        ResourceAgentFacadeFactory(env.cmd_runner(), env.report_processor),
    ):
        property_definition_list.extend(facade.metadata.parameters)
    return ClusterPropertyMetadataDto(
        properties_metadata=[
            property_definition.to_dto()
            for property_definition in property_definition_list
        ],
        readonly_properties=cluster_property.READONLY_CLUSTER_PROPERTY_LIST,
    )
