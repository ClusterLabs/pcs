from typing import Dict, Iterable, List, Mapping, Optional

from pcs.common.interface.dto import to_dict
from pcs.lib.resource_agent import AgentMetadataDto, AgentActionDto


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
    raw_operation_list: Iterable[Mapping[str, Optional[str]]]
) -> List[Dict[str, Optional[str]]]:
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
    agent_metadata: AgentMetadataDto, necessary_only: bool = False
) -> List[Dict[str, Optional[str]]]:
    """
    Return operations which should be put to a CIB resource on its creation
    """
    is_default_operation = (
        _is_default_operation_stonith
        if agent_metadata.standard == "stonith"
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
    for op_name in _NECESSARY_OPERATIONS:
        if op_name not in defined_operation_names:
            action_list.append(
                AgentActionDto(
                    op_name, None, None, None, None, None, None, None
                )
            )

    # transform actions to operation definitions
    return [action_to_operation(to_dict(action)) for action in action_list]


def action_to_operation(
    action: Mapping[str, Optional[str]]
) -> Dict[str, Optional[str]]:
    """
    Transform agent action data to CIB operation data
    """
    operation = {}
    for key, value in action.items():
        if key == "depth":
            operation["OCF_CHECK_LEVEL"] = None if value == "0" else value
        else:
            operation[key] = value
    return operation


def _is_default_operation_resource(action: AgentActionDto) -> bool:
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


def _is_default_operation_stonith(action: AgentActionDto) -> bool:
    return action.name == "monitor"
