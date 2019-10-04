from collections import defaultdict

def get_operations_from_transitions(transitions):
    """
    Extract resource operations from simulated transitions

    etree transitions -- simulated transitions from crm_simulate
    """
    operation_list = []
    watched_operations = {
        "start", "stop", "promote", "demote", "migrate_from", "migrate_to"
    }
    for rsc_op in transitions.iterfind("synapse/action_set/rsc_op"):
        operation = rsc_op.get("operation", "").lower()
        if operation not in watched_operations:
            continue
        for primitive in rsc_op.iterfind("primitive"):
            primitive_id = primitive.get("id")
            operation_list.append((
                int(rsc_op.get("id")),
                {
                    "primitive_id": primitive_id,
                    "primitive_long_id": (
                        primitive.get("long-id") or primitive_id
                    ),
                    "operation": operation,
                    "on_node": rsc_op.get("on_node"),
                }
            ))
    operation_list.sort(key=lambda x: x[0])
    op_list = [op[1] for op in operation_list]
    return op_list

def get_resources_from_operations(operation_list, exclude=None):
    """
    Get names of all resources from the provided operation list

    list operation_list -- result of get_operations_from_transitions
    iterable exclude -- resources to exclude from the result
    """
    exclude = exclude or set()
    return sorted({
        op["primitive_id"]
        for op in operation_list
        if op["primitive_id"] not in exclude
    })

def get_resources_left_stopped(operation_list, exclude=None):
    """
    Get names of resources which are left stopped by the provided operation list

    list operation_list -- result of get_operations_from_transitions
    iterable exclude -- resources to exclude from the result
    """
    return _resources_with_imbalanced_operations(
        operation_list, "stop", "start", exclude
    )

def get_resources_left_demoted(operation_list, exclude=None):
    """
    Get names of resources which are left demoted by the provided operation list

    list operation_list -- result of get_operations_from_transitions
    iterable exclude -- resources to exclude from the result
    """
    return _resources_with_imbalanced_operations(
        operation_list, "demote", "promote", exclude
    )

def _resources_with_imbalanced_operations(
    operation_list, increment_op, decrement_op, exclude
):
    exclude = exclude or set()
    counter = defaultdict(int)
    for res_op in operation_list:
        resource = res_op["primitive_id"]
        operation = res_op["operation"]
        if operation == increment_op:
            counter[resource] += 1
        elif operation == decrement_op:
            counter[resource] -= 1
    return sorted([
        resource
        for resource, count in counter.items()
        if count > 0 and resource not in exclude
    ])
