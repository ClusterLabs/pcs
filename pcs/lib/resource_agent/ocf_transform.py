from collections import defaultdict
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Union,
)

from . import const
from .types import (
    ResourceAgentAction,
    ResourceAgentActionOcf1_0,
    ResourceAgentActionOcf1_1,
    ResourceAgentMetadata,
    ResourceAgentMetadataOcf1_0,
    ResourceAgentMetadataOcf1_1,
    ResourceAgentParameter,
    ResourceAgentParameterOcf1_0,
    ResourceAgentParameterOcf1_1,
)


def ocf_version_to_ocf_unified(
    metadata: Union[ResourceAgentMetadataOcf1_0, ResourceAgentMetadataOcf1_1]
) -> ResourceAgentMetadata:
    """
    Transform specific version OCF metadata to a universal format

    metadata -- metadata according to a specific OCF version
    """
    if isinstance(metadata, ResourceAgentMetadataOcf1_0):
        return _ocf_1_0_to_ocf_unified(metadata)
    if isinstance(metadata, ResourceAgentMetadataOcf1_1):
        return _ocf_1_1_to_ocf_unified(metadata)
    raise AssertionError(
        f"Unexpected resource agent metadata class: {metadata.__class__.__name__}"
    )


def _ocf_1_0_to_ocf_unified(
    metadata: ResourceAgentMetadataOcf1_0,
) -> ResourceAgentMetadata:
    """
    Transform OCF 1.0 metadata to a universal format

    metadata -- metadata according OCF 1.0
    """
    return ResourceAgentMetadata(
        name=metadata.name,
        agent_exists=True,
        ocf_version=const.OCF_1_0,
        shortdesc=metadata.shortdesc,
        longdesc=metadata.longdesc,
        parameters=_ocf_1_0_parameter_list_to_ocf_unified(metadata.parameters),
        actions=_ocf_1_0_action_list_to_ocf_unified(metadata.actions),
    )


def _ocf_1_1_to_ocf_unified(
    metadata: ResourceAgentMetadataOcf1_1,
) -> ResourceAgentMetadata:
    """
    Transform OCF 1.1 metadata to a universal format

    metadata -- metadata according OCF 1.1
    """
    return ResourceAgentMetadata(
        name=metadata.name,
        agent_exists=True,
        ocf_version=const.OCF_1_1,
        shortdesc=metadata.shortdesc,
        longdesc=metadata.longdesc,
        parameters=_ocf_1_1_parameter_list_to_ocf_unified(metadata.parameters),
        # OCF 1.1 actions are the same as in OCF 1.0
        actions=_ocf_1_0_action_list_to_ocf_unified(metadata.actions),
    )


def _ocf_1_0_action_list_to_ocf_unified(
    action_list: Iterable[
        Union[ResourceAgentActionOcf1_0, ResourceAgentActionOcf1_1]
    ],
) -> List[ResourceAgentAction]:
    """
    Transform OCF 1.0 actions to a universal format

    action_list -- actions according OCF 1.0
    """
    return [
        ResourceAgentAction(
            name=action.name,
            timeout=action.timeout,
            interval=action.interval,
            role=action.role,
            start_delay=action.start_delay,
            depth=action.depth,
            automatic=_bool_value(action.automatic),
            on_target=_bool_value(action.on_target),
        )
        for action in action_list
    ]


def _ocf_1_0_parameter_list_to_ocf_unified(
    parameter_list: Iterable[ResourceAgentParameterOcf1_0],
) -> List[ResourceAgentParameter]:
    """
    Transform OCF 1.0 parameters to a universal format

    parameter_list -- parameters according OCF 1.0
    """
    deprecated_by_dict: Dict[str, Set[str]] = defaultdict(set)
    for parameter in parameter_list:
        if parameter.obsoletes:
            deprecated_by_dict[parameter.obsoletes].add(parameter.name)

    result = []
    for parameter in parameter_list:
        result.append(
            ResourceAgentParameter(
                name=parameter.name,
                shortdesc=parameter.shortdesc,
                longdesc=parameter.longdesc,
                type=parameter.type,
                default=parameter.default,
                enum_values=parameter.enum_values,
                required=_bool_value(parameter.required),
                advanced=False,
                deprecated=_bool_value(parameter.deprecated),
                deprecated_by=sorted(deprecated_by_dict[parameter.name]),
                deprecated_desc=None,
                unique_group=(
                    f"{const.DEFAULT_UNIQUE_GROUP_PREFIX}{parameter.name}"
                    if _bool_value(parameter.unique)
                    else None
                ),
                reloadable=_bool_value(parameter.unique),
            )
        )
    return result


def _ocf_1_1_parameter_list_to_ocf_unified(
    parameter_list: Iterable[ResourceAgentParameterOcf1_1],
) -> List[ResourceAgentParameter]:
    """
    Transform OCF 1.1 parameters to a universal format

    parameter_list -- parameters according OCF 1.1
    """
    return [
        ResourceAgentParameter(
            name=parameter.name,
            shortdesc=parameter.shortdesc,
            longdesc=parameter.longdesc,
            type=parameter.type,
            default=parameter.default,
            enum_values=parameter.enum_values,
            required=_bool_value(parameter.required),
            advanced=_bool_value(parameter.advanced),
            deprecated=parameter.deprecated,
            deprecated_by=parameter.deprecated_by,
            deprecated_desc=parameter.deprecated_desc,
            unique_group=parameter.unique_group,
            reloadable=_bool_value(parameter.reloadable),
        )
        for parameter in parameter_list
    ]


def _bool_value(value: Optional[str]) -> bool:
    """
    Transform raw bool value from metadata to bool type

    value -- raw bool value
    """
    return value == "1"
