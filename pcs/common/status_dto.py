from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.const import PcmkRoleType, PcmkStatusRoleType
from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class PrimitiveStatusDto(DataTransferObject):
    resource_id: str
    instance_id: str | None
    resource_agent: str
    role: PcmkStatusRoleType
    target_role: PcmkRoleType | None
    active: bool
    orphaned: bool
    blocked: bool
    maintenance: bool
    description: str | None
    failed: bool
    managed: bool
    failure_ignored: bool
    node_names: list[str]
    pending: str | None
    locked_to: str | None


@dataclass(frozen=True)
class GroupStatusDto(DataTransferObject):
    resource_id: str
    instance_id: str | None
    maintenance: bool
    description: str | None
    managed: bool
    disabled: bool
    members: Sequence[PrimitiveStatusDto]


@dataclass(frozen=True)
class CloneStatusDto(DataTransferObject):
    resource_id: str
    multi_state: bool
    unique: bool
    maintenance: bool
    description: str | None
    managed: bool
    disabled: bool
    failed: bool
    failure_ignored: bool
    target_role: PcmkRoleType | None
    instances: Sequence[PrimitiveStatusDto] | Sequence[GroupStatusDto]


@dataclass(frozen=True)
class BundleReplicaStatusDto(DataTransferObject):
    replica_id: str
    member: PrimitiveStatusDto | None
    remote: PrimitiveStatusDto | None
    container: PrimitiveStatusDto
    ip_address: PrimitiveStatusDto | None


@dataclass(frozen=True)
class BundleStatusDto(DataTransferObject):
    resource_id: str
    type: str
    image: str
    unique: bool
    maintenance: bool
    description: str | None
    managed: bool
    failed: bool
    replicas: Sequence[BundleReplicaStatusDto]


AnyResourceStatusDto = (
    PrimitiveStatusDto | GroupStatusDto | CloneStatusDto | BundleStatusDto
)


@dataclass(frozen=True)
class ResourcesStatusDto(DataTransferObject):
    resources: Sequence[AnyResourceStatusDto]
