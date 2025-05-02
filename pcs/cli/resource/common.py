from collections import defaultdict
from typing import (
    Any,
    Optional,
    Sequence,
    Union,
)

from pcs.cli.reports.output import (
    deprecation_warning,
)
from pcs.common import (
    const,
    reports,
)
from pcs.common.status_dto import (
    AnyResourceStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
)
from pcs.common.str_tools import (
    format_list,
    format_optional,
    format_plural,
)

RESOURCE_NOT_RUNNING = "Resource '{resource_id}' is not running on any nodes"


def check_is_not_stonith(
    lib: Any, resource_id_list: list[str], cmd_to_use: Optional[str] = None
) -> None:
    if lib.resource.is_any_stonith(resource_id_list):
        deprecation_warning(
            reports.messages.ResourceStonithCommandsMismatch(
                "stonith resources"
            ).message
            + format_optional(cmd_to_use, " Please use '{}' instead.")
        )


def _get_primitive_instance_list_dto(
    resource_dto: Union[AnyResourceStatusDto],
) -> Sequence[PrimitiveStatusDto]:
    """
    Return a list of primitive instances from any resource status DTO.
    """
    if isinstance(resource_dto, GroupStatusDto):
        return resource_dto.members
    if isinstance(resource_dto, CloneStatusDto):
        if isinstance(resource_dto.instances[0], GroupStatusDto):
            instance_list: list[PrimitiveStatusDto] = []
            for group_dto in resource_dto.instances:
                # There is a check for the type in the if above
                instance_list.extend(group_dto.members)  # type: ignore
            return instance_list
        # There is a check for the type in the if above
        return resource_dto.instances  # type: ignore
    if isinstance(resource_dto, BundleStatusDto):
        return [replica_dto.container for replica_dto in resource_dto.replicas]
    return [resource_dto]


def get_resource_status_msg(lib: Any, resource_id: str) -> str:
    """
    Get where resources are running, typically used after waiting for cluster
    is finished. Returns a text string similar to utils.resource_running_on.
    Examples:
        Resource 'r1' is not running on any nodes
        Resource 'r2-clone' is promoted on node 'n1'; unpromoted on nodes 'n2',
        'n3'
    """
    resource_dto = None
    for resource in lib.status.resources_status().resources:
        if resource.resource_id == resource_id:
            resource_dto = resource
    if resource_dto is None:
        # Resource is configured but Pacemaker is ignoring it
        return RESOURCE_NOT_RUNNING.format(resource_id=resource_id)

    # Using set in case more instances are running on the same node
    role_and_location: dict[const.PcmkStatusRoleType, set[str]] = defaultdict(
        set
    )
    instance_list_dto = _get_primitive_instance_list_dto(resource_dto)
    for instance_dto in instance_list_dto:
        role_and_location[instance_dto.role].update(instance_dto.node_names)

    # The old function (utils.resource_running_on) this is replicating only
    # supported states Started, Promoted and Unpromoted. Therefore we have to
    # filter out only these states since others were ignored previously.
    role_and_location = {
        role: loc
        for role, loc in role_and_location.items()
        if role
        in [
            const.PCMK_STATUS_ROLE_STARTED,
            const.PCMK_STATUS_ROLE_PROMOTED,
            const.PCMK_STATUS_ROLE_UNPROMOTED,
        ]
    }

    if not role_and_location:
        return RESOURCE_NOT_RUNNING.format(resource_id=resource_id)

    state_parts = []
    for state_name, node_list in role_and_location.items():
        state_parts.append(
            "{state_name} on {node_pl} {node_list}".format(
                state_name=(
                    state_name.lower()
                    if state_name != const.PCMK_STATUS_ROLE_STARTED
                    else "running"
                ),
                node_pl=format_plural(depends_on=node_list, singular="node"),
                node_list=format_list(node_list),
            )
        )
    state_info = "; ".join(state_parts)
    return f"Resource '{resource_id}' is {state_info}"
