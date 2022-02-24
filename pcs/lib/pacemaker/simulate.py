from collections import defaultdict
from typing import (
    Container,
    Dict,
    Iterable,
    List,
    NewType,
    Optional,
)

from dataclasses import dataclass
from lxml.etree import _Element

SimulationOperationType = NewType("SimulationOperationType", str)

OPERATION_START = SimulationOperationType("start")
OPERATION_STOP = SimulationOperationType("stop")
OPERATION_PROMOTE = SimulationOperationType("promote")
OPERATION_DEMOTE = SimulationOperationType("demote")
OPERATION_MIGRATE_FROM = SimulationOperationType("migrate_from")
OPERATION_MIGRATE_TO = SimulationOperationType("migrate_to")

KNOWN_OPERATIONS = {
    OPERATION_START,
    OPERATION_STOP,
    OPERATION_PROMOTE,
    OPERATION_DEMOTE,
    OPERATION_MIGRATE_FROM,
    OPERATION_MIGRATE_TO,
}


@dataclass(frozen=True)
class SimulationOperation:
    operation_id: int
    primitive_id: str
    primitive_long_id: str
    operation_type: SimulationOperationType
    on_node: str


def get_operations_from_transitions(
    transitions: _Element,
) -> List[SimulationOperation]:
    """
    Extract resource operations from simulated transitions

    transitions -- simulated transitions from crm_simulate
    """
    operation_list: List[SimulationOperation] = []
    for rsc_op in transitions.iterfind("synapse/action_set/rsc_op"):
        operation = SimulationOperationType(rsc_op.get("operation", "").lower())
        if operation not in KNOWN_OPERATIONS:
            continue
        for primitive in rsc_op.iterfind("primitive"):
            primitive_id = str(primitive.attrib["id"])
            operation_list.append(
                SimulationOperation(
                    operation_id=int(rsc_op.attrib["id"]),
                    primitive_id=primitive_id,
                    primitive_long_id=primitive.get("long-id") or primitive_id,
                    operation_type=operation,
                    on_node=str(rsc_op.attrib["on_node"]),
                )
            )
    operation_list.sort(key=lambda op: op.operation_id)
    return operation_list


def get_resources_from_operations(
    operation_list: Iterable[SimulationOperation],
    exclude_resources: Optional[Container[str]] = None,
) -> List[str]:
    """
    Get names of all resources from the provided operation list

    operation_list -- result of get_operations_from_transitions
    exclude_resources -- resources to exclude from the result
    """
    exclude_resources = exclude_resources or tuple()
    return sorted(
        {
            op.primitive_id
            for op in operation_list
            if op.primitive_id not in exclude_resources
        }
    )


def get_resources_left_stopped(
    operation_list: Iterable[SimulationOperation],
    exclude_resources: Optional[Container[str]] = None,
) -> List[str]:
    """
    Get names of resources which are left stopped by the provided operation list

    operation_list -- result of get_operations_from_transitions
    exclude_resources -- resources to exclude from the result
    """
    return _resources_with_imbalanced_operations(
        operation_list, OPERATION_STOP, OPERATION_START, exclude_resources
    )


def get_resources_left_demoted(
    operation_list: Iterable[SimulationOperation],
    exclude_resources: Optional[Container[str]] = None,
) -> List[str]:
    """
    Get names of resources which are left demoted by the provided operation list

    operation_list -- result of get_operations_from_transitions
    exclude_resources -- resources to exclude from the result
    """
    return _resources_with_imbalanced_operations(
        operation_list, OPERATION_DEMOTE, OPERATION_PROMOTE, exclude_resources
    )


def _resources_with_imbalanced_operations(
    operation_list: Iterable[SimulationOperation],
    increment_op: SimulationOperationType,
    decrement_op: SimulationOperationType,
    exclude_resources: Optional[Container[str]] = None,
) -> List[str]:
    exclude_resources = exclude_resources or tuple()
    counter: Dict[str, int] = defaultdict(int)
    for res_op in operation_list:
        resource = res_op.primitive_id
        operation = res_op.operation_type
        if operation == increment_op:
            counter[resource] += 1
        elif operation == decrement_op:
            counter[resource] -= 1
    return sorted(
        [
            resource
            for resource, count in counter.items()
            if count > 0 and resource not in exclude_resources
        ]
    )
