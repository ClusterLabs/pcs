from typing import (
    Any,
    Iterable,
    List,
    Mapping,
)

from pcs.common.const import PcmkRoleType
from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.resource.operations import (
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
    CibResourceOperationDto,
)
from pcs.lib.cib.resource.types import (
    ResourceOperationIn,
    ResourceOperationOut,
)
from pcs.lib.resource_agent import (
    ResourceAgentAction,
    ResourceAgentMetadata,
)

# Operation monitor is always required, even if creating default actions was
# not requested or a resource/stonith agent does not specify it. See
# https://clusterlabs.org/pacemaker/doc/2.1/Pacemaker_Explained/html/resources.html#monitoring-resources-for-failure
_NECESSARY_OPERATIONS = {"monitor"}

_DEFAULT_INTERVALS = {"monitor": "60s"}


def get_default_operation_interval(operation_name: str) -> str:
    """
    Return default interval for given operation_name

    operation_name -- name of the operation to get the default interval for
    """
    return _DEFAULT_INTERVALS.get(operation_name, "0s")


def complete_operations_options(
    raw_operation_list: Iterable[ResourceOperationIn],
) -> List[ResourceOperationOut]:
    """
    Return a new list of operations with all necessary keys defined

    raw_operation_list -- entered operations
    """
    operation_list = []
    for raw_operation in raw_operation_list:
        operation = dict(raw_operation)
        if operation.get("interval") is None:
            operation["interval"] = get_default_operation_interval(
                str(operation["name"])
            )
        operation_list.append(operation)
    return operation_list


def get_default_operations(
    agent_metadata: ResourceAgentMetadata,
    necessary_only: bool = False,
) -> List[CibResourceOperationDto]:
    is_default_operation = (
        _is_default_operation_stonith
        if agent_metadata.name.is_stonith
        else _is_default_operation_resource
    )

    # filter actions
    action_list = [
        action
        for action in agent_metadata.actions
        if (necessary_only and action.name in _NECESSARY_OPERATIONS)
        or (not necessary_only and is_default_operation(action))
    ]

    # add necessary actions if they are missing
    defined_operation_names = frozenset(op.name for op in action_list)
    action_list.extend(
        ResourceAgentAction(op_name, None, None, None, None, None, False, False)
        for op_name in _NECESSARY_OPERATIONS
        if op_name not in defined_operation_names
    )

    # transform actions to operation definitions
    return [action_to_operation_dto(action) for action in action_list]


def action_to_operation_dto(
    action: ResourceAgentAction,
) -> CibResourceOperationDto:
    """
    Transform agent action data to CIB operation data
    """
    instance_attributes = []
    if action.depth not in (None, "0"):
        instance_attributes = [
            CibNvsetDto(
                id="",
                options={},
                rule=None,
                nvpairs=[
                    CibNvpairDto(
                        id="",
                        name=OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
                        value=str(action.depth),
                    )
                ],
            )
        ]
    return CibResourceOperationDto(
        id="",
        name=action.name,
        interval=(
            action.interval
            if action.interval
            else get_default_operation_interval(action.name)
        ),
        description=None,
        start_delay=action.start_delay,
        interval_origin=None,
        timeout=action.timeout,
        enabled=None,
        record_pending=None,
        role=PcmkRoleType(action.role) if action.role else None,
        on_fail=None,
        meta_attributes=[],
        instance_attributes=instance_attributes,
    )


def operation_dto_to_legacy_dict(
    operation: CibResourceOperationDto,
    defaults: Mapping[str, Any],
) -> ResourceOperationOut:
    operation_dict = dict(defaults)
    operation_dict.update(
        {
            key: value
            for key, value in to_dict(operation).items()
            if key in ("name", "timeout", "interval", "role")
        }
    )
    operation_dict["start-delay"] = operation.start_delay
    operation_dict[OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME] = None
    for nvset in operation.instance_attributes:
        for nvpair in nvset.nvpairs:
            if nvpair.name == OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME:
                operation_dict[OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME] = (
                    nvpair.value
                )
    return operation_dict


def _is_default_operation_resource(action: ResourceAgentAction) -> bool:
    # Copy all actions to the CIB even those not defined in the OCF standard
    # or pacemaker. This way even custom actions defined in a resource agent
    # will be copied to the CIB and run by pacemaker if they specify
    # an interval. See https://github.com/ClusterLabs/pcs/issues/132
    return action.name not in {
        # one-time action, not meant to be processed by pacemaker
        "meta-data",
        # deprecated alias of monitor
        "status",
        # one-time action, not meant to be processed by pacemaker
        "validate-all",
    }


def _is_default_operation_stonith(action: ResourceAgentAction) -> bool:
    return action.name == "monitor"
