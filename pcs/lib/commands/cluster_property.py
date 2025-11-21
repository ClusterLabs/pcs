from typing import Mapping, Union

from pcs import settings
from pcs.common import reports
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import ListCibNvsetDto
from pcs.common.str_tools import join_multilines
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
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.live import (
    get_cib_file_runner_env,
    has_cib_xml,
    is_crm_attribute_list_options_supported,
)
from pcs.lib.resource_agent import (
    ResourceAgentError,
    ResourceAgentMetadata,
    resource_agent_error_to_report_item,
)
from pcs.lib.resource_agent import const as ra_const
from pcs.lib.resource_agent.facade import ResourceAgentFacadeFactory


def _get_properties_metadata(
    report_processor: reports.ReportProcessor,
    runner: CommandRunner,
) -> ResourceAgentMetadata:
    if not is_crm_attribute_list_options_supported(runner):
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.ClusterOptionsMetadataNotSupported()
            )
        )
        raise LibraryError()

    try:
        factory = ResourceAgentFacadeFactory(runner, report_processor)
        return factory.facade_from_crm_attribute(
            ra_const.CLUSTER_OPTIONS
        ).metadata
    except ResourceAgentError as e:
        report_processor.report_list(
            [
                resource_agent_error_to_report_item(
                    e, reports.ReportItemSeverity.error()
                )
            ]
        )
        raise LibraryError() from e


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
        "fencing-enabled": "Fencing Enabled",
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
    return _cluster_property_metadata_to_dict(
        _get_properties_metadata(env.report_processor, env.cmd_runner())
    )


def set_properties(
    env: LibraryEnvironment,
    cluster_properties: Mapping[str, str],
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Set specified pacemaker cluster properties, remove those with empty values.

    env -- provides communication with externals
    cluster_properties -- dictionary of cluster property names and values
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    runner = env.cmd_runner()
    id_provider = IdProvider(cib)
    force = reports.codes.FORCE in force_flags
    cluster_property_set_el = (
        cluster_property.get_cluster_property_set_element_legacy(
            cib, id_provider
        )
    )
    set_id = cluster_property_set_el.get("id", "")

    configured_properties = [
        nvpair_dto.name
        for nvpair_dto in nvpair_multi.nvset_element_to_dto(
            cluster_property_set_el,
            rule.RuleInEffectEvalDummy(),
        ).nvpairs
    ]

    env.report_processor.report_list(
        cluster_property.validate_set_cluster_properties(
            runner,
            _get_properties_metadata(env.report_processor, runner).parameters,
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
    metadata = _get_properties_metadata(env.report_processor, env.cmd_runner())
    return ClusterPropertyMetadataDto(
        properties_metadata=[
            property_definition.to_dto()
            for property_definition in metadata.parameters
        ],
        readonly_properties=cluster_property.READONLY_CLUSTER_PROPERTY_LIST,
    )


def remove_cluster_name(env: LibraryEnvironment) -> None:
    """
    Remove cluster-name property from CIB on local node. The cluster has to be
    stopped and the property is removed directly from the CIB file.
    """
    if env.service_manager.is_running("pacemaker"):
        env.report_processor.report(
            reports.ReportItem.error(reports.messages.PacemakerRunning())
        )
        raise LibraryError()

    if not has_cib_xml():
        env.report_processor.report(
            reports.ReportItem.error(reports.messages.CibXmlMissing())
        )
        raise LibraryError()

    xpath = "/cib/configuration/crm_config/cluster_property_set/nvpair[@name='cluster-name']"
    stdout, stderr, retval = env.cmd_runner().run(
        [settings.cibadmin_exec, "--delete-all", "--force", f"--xpath={xpath}"],
        env_extend=get_cib_file_runner_env(),
    )
    if retval != 0:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.CibClusterNameRemovalFailed(
                    reason=join_multilines([stderr, stdout])
                )
            )
        )
        raise LibraryError()
