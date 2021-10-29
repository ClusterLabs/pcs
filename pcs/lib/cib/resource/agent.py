from typing import Iterable, List

from pcs.common.interface.dto import to_dict
from pcs.common.resource_agent_dto import ResourceAgentActionDto
from pcs.lib.resource_agent import ResourceAgentAction, ResourceAgentMetadata
from pcs.lib.cib.resource.const import OPERATION_ATTRIBUTES
from pcs.lib.cib.resource.types import ResourceOperationIn, ResourceOperationOut


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
    keep_extra_keys: bool = False,
) -> List[ResourceOperationOut]:
    """
    Return operations which should be put to a CIB resource on its creation
    """
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
    for op_name in _NECESSARY_OPERATIONS:
        if op_name not in defined_operation_names:
            action_list.append(
                ResourceAgentAction(
                    op_name, None, None, None, None, None, False, False
                )
            )

    # transform actions to operation definitions
    return [
        action_to_operation(action.to_dto(), keep_extra_keys=keep_extra_keys)
        for action in action_list
    ]


def action_to_operation(
    action: ResourceAgentActionDto, keep_extra_keys: bool = False
) -> ResourceOperationOut:
    """
    Transform agent action data to CIB operation data
    """
    # This function bridges new agent framework, which provides data in
    # dataclasses, to old resource create code and transforms new data
    # structures to a format expected by the old code. When resource create is
    # overhauled, this fuction is expected to be removed.
    operation = {}
    for key, value in to_dict(action).items():
        if key == "depth":
            # "None" values are not put to CIB, so this keeps the key in place
            # while making sure it's not put in CIB. I'm not sure why depth ==
            # 0 is treated like this, but I keep it in place so the behavior is
            # the same as it has been for a long time. If pcs starts using
            # depth / OCF_CHECK_LEVEL or there is other demand for it, consider
            # changing this so value of "0" is put in CIB.
            operation["OCF_CHECK_LEVEL"] = None if value == "0" else value
        elif key == "start_delay":
            operation["start-delay"] = value
        elif key in OPERATION_ATTRIBUTES or keep_extra_keys:
            operation[key] = value
    return operation


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
