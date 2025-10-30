from dataclasses import replace
from typing import (
    List,
    Optional,
    Tuple,
)

from pcs.common.const import PcmkRoleType
from pcs.common.pacemaker import role

from . import const
from .types import (
    ResourceAgentAction,
    ResourceAgentMetadata,
    ResourceAgentParameter,
)


def get_additional_trace_parameters(
    existing_parameters: List[ResourceAgentParameter],
) -> List[ResourceAgentParameter]:
    """
    Return trace parameters which need to be added based on existing parameters

    existing_parameters -- parameters defined by an agent
    """
    trace_ra_found = trace_file_found = False
    for param in existing_parameters:
        param_name = param.name.lower()
        if param_name == "trace_ra":
            trace_ra_found = True
        elif param_name == "trace_file":
            trace_file_found = True
        if trace_file_found and trace_ra_found:
            break

    result = []
    if not trace_ra_found:
        shortdesc = (
            "Set to 1 to turn on resource agent tracing (expect large output)"
        )
        result.append(
            ResourceAgentParameter(
                name="trace_ra",
                shortdesc=shortdesc,
                longdesc=(
                    shortdesc + " The trace output will be saved to "
                    "trace_file, if set, or by default to "
                    "$HA_VARRUN/ra_trace/<type>/<id>.<action>.<timestamp> e.g. "
                    "$HA_VARRUN/ra_trace/oracle/db.start.2012-11-27.08:37:08"
                ),
                type="integer",
                default="0",
                enum_values=None,
                required=False,
                advanced=True,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            )
        )
    if not trace_file_found:
        shortdesc = "Path to a file to store resource agent tracing log"
        result.append(
            ResourceAgentParameter(
                name="trace_file",
                shortdesc=shortdesc,
                longdesc=shortdesc,
                type="string",
                default="",
                enum_values=None,
                required=False,
                advanced=True,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            )
        )
    return result


def ocf_unified_to_pcs(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    """
    Return a cleaned up agent metadata suitable for further pcs processing

    metadata -- parsed OCF agent metadata to be cleaned
    """
    result = metadata
    result = _metadata_action_translate_role(result)
    if metadata.name.is_pcmk_fake_agent:
        result = _metadata_parameter_extract_enum_values_from_desc(result)
        result = _metadata_parameter_remove_select_enum_values_from_desc(result)
        result = _metadata_parameter_deduplicate_desc(result)
        result = _metadata_parameter_extract_advanced_from_desc(result)
        result = _metadata_parameter_join_short_long_desc(result)
    if metadata.name.is_stonith:
        result = _metadata_remove_unwanted_stonith_parameters(result)
        result = _metadata_make_stonith_action_parameter_deprecated(result)
        result = _metadata_make_stonith_port_parameter_not_required(result)
    return result


def _metadata_action_translate_role(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    return replace(
        metadata,
        actions=[_action_translate_role(action) for action in metadata.actions],
    )


def _action_translate_role(action: ResourceAgentAction) -> ResourceAgentAction:
    if action.role is None:
        return action
    return replace(
        action, role=role.get_value_primary(PcmkRoleType(action.role))
    )


def _metadata_parameter_extract_advanced_from_desc(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    return replace(
        metadata,
        parameters=[
            _parameter_extract_advanced_from_desc(parameter)
            for parameter in metadata.parameters
        ],
    )


def _parameter_extract_advanced_from_desc(
    parameter: ResourceAgentParameter,
) -> ResourceAgentParameter:
    # If the parameter had xml attribute advanced="1", it is already marked as
    # advanced. Shortdesc is parsed regardless, to remove "advanced use only"
    # strings. If either the strings are present OR the xml attribute is 1, the
    # parameter is advanced and the behavior is the same in both cases: remove
    # plaintext representation of structured data.
    advanced_str_beginings = ["Advanced use only:", "*** Advanced Use Only ***"]
    shortdesc = parameter.shortdesc
    if shortdesc:
        for advanced_str in advanced_str_beginings:
            if shortdesc.startswith(advanced_str):
                new_shortdesc = shortdesc.removeprefix(advanced_str).lstrip()
                return replace(
                    parameter,
                    advanced=True,
                    shortdesc=new_shortdesc if new_shortdesc else None,
                )
    return parameter


def _metadata_parameter_join_short_long_desc(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    return replace(
        metadata,
        parameters=[
            _parameter_join_short_long_desc(parameter)
            for parameter in metadata.parameters
        ],
    )


def _parameter_join_short_long_desc(
    parameter: ResourceAgentParameter,
) -> ResourceAgentParameter:
    shortdesc = parameter.shortdesc
    longdesc = parameter.longdesc
    if shortdesc is None or longdesc is None:
        return parameter
    if shortdesc and not shortdesc.endswith("."):
        shortdesc = f"{shortdesc}."
    if longdesc.startswith(shortdesc):
        return parameter
    return replace(parameter, longdesc=f"{shortdesc}\n{longdesc}".strip())


def _metadata_remove_unwanted_stonith_parameters(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    # We don't allow the user to change these options which are only intended
    # to be used interactively on command line.
    return replace(
        metadata,
        parameters=[
            parameter
            for parameter in metadata.parameters
            if parameter.name not in {"help", "version"}
        ],
    )


def _metadata_make_stonith_action_parameter_deprecated(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    # Action parameter is intended to be used interactively on command line
    # only. However, we still need the user to be able to set it due to
    # backward compatibility reasons. So we just mark it as not required. We
    # also move it to advanced params to indicate that users should not set it
    # in most cases.
    new_parameters = []
    for param in metadata.parameters:
        if param.name == "action":
            new_parameters.append(
                replace(
                    param,
                    required=False,
                    advanced=True,
                    deprecated=True,
                    deprecated_by=(
                        const.STONITH_ACTION_REPLACED_BY + param.deprecated_by
                    ),
                )
            )
        else:
            new_parameters.append(param)
    return replace(metadata, parameters=new_parameters)


def _metadata_make_stonith_port_parameter_not_required(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    # 'port' parameter is required by a fence agent, but it is filled
    # automatically by pacemaker based on 'pcmk_host_map' or 'pcmk_host_list'
    # parameter (defined in fenced metadata). Therefore, we must mark 'port'
    # and all parameters replacing it as not required.
    port_related_params = set()
    next_iteration_params = {"port"}
    while next_iteration_params:
        current_params = next_iteration_params
        next_iteration_params = set()
        for param in metadata.parameters:
            if (
                param.name in current_params
                and param.name not in port_related_params
            ):
                port_related_params.add(param.name)
                next_iteration_params.update(param.deprecated_by)

    new_parameters = []
    for param in metadata.parameters:
        if param.name in port_related_params:
            new_parameters.append(replace(param, required=False))
        else:
            new_parameters.append(param)
    return replace(metadata, parameters=new_parameters)


def _metadata_parameter_extract_enum_values_from_desc(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    return replace(
        metadata,
        parameters=[
            _parameter_extract_enum_values_from_desc(parameter)
            for parameter in metadata.parameters
        ],
    )


def _parameter_extract_enum_values_from_desc(
    parameter: ResourceAgentParameter,
) -> ResourceAgentParameter:
    if parameter.type != "enum":
        return parameter
    enum_values, longdesc = _get_enum_values_and_new_longdesc(parameter)
    if parameter.default is not None and parameter.default not in enum_values:
        enum_values.append(parameter.default)
    parameter = replace(parameter, type="select")
    parameter = replace(parameter, longdesc=longdesc)
    return replace(parameter, enum_values=enum_values)


def _metadata_parameter_remove_select_enum_values_from_desc(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    return replace(
        metadata,
        parameters=[
            _parameter_remove_select_enum_values_from_desc(parameter)
            for parameter in metadata.parameters
        ],
    )


def _parameter_remove_select_enum_values_from_desc(
    parameter: ResourceAgentParameter,
) -> ResourceAgentParameter:
    # If the parameter had xml attribute type="enum", it was changed to
    # type="select" by _parameter_extract_enum_values_from_desc. No matter
    # that, the enum / select values are removed from longdesc to make the
    # behavior the same in both cases: remove plaintext representation of
    # structured data.
    if parameter.type != "select":
        return parameter
    _, longdesc = _get_enum_values_and_new_longdesc(parameter)
    return replace(parameter, longdesc=longdesc)


def _metadata_parameter_deduplicate_desc(
    metadata: ResourceAgentMetadata,
) -> ResourceAgentMetadata:
    return replace(
        metadata,
        parameters=[
            _parameter_deduplicate_desc(parameter)
            for parameter in metadata.parameters
        ],
    )


def _parameter_deduplicate_desc(
    parameter: ResourceAgentParameter,
) -> ResourceAgentParameter:
    if parameter.shortdesc == parameter.longdesc:
        return replace(parameter, longdesc=None)
    return parameter


def _get_enum_values_and_new_longdesc(
    parameter: ResourceAgentParameter,
) -> Tuple[List[str], Optional[str]]:
    enum_values = []
    longdesc = parameter.longdesc
    if parameter.longdesc:
        parts = parameter.longdesc.split("  Allowed values: ")
        if len(parts) == 2:
            enum_values = parts[1].split(", ")
            longdesc = parts[0]
    return enum_values, longdesc
