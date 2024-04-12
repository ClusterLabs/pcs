from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
    Union,
)

from pcs.common.const import (
    PcmkRoleType,
    PcmkStatusRoleType,
)
from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class PrimitiveStatusDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    resource_id: str
    instance_id: Optional[str]
    resource_agent: str
    role: PcmkStatusRoleType
    target_role: Optional[PcmkRoleType]
    active: bool
    orphaned: bool
    blocked: bool
    maintenance: bool
    description: Optional[str]
    failed: bool
    managed: bool
    failure_ignored: bool
    node_names: list[str]
    pending: Optional[str]
    locked_to: Optional[str]


@dataclass(frozen=True)
class GroupStatusDto(DataTransferObject):
    resource_id: str
    instance_id: Optional[str]
    maintenance: bool
    description: Optional[str]
    managed: bool
    disabled: bool
    members: Sequence[PrimitiveStatusDto]


@dataclass(frozen=True)
class CloneStatusDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    resource_id: str
    multi_state: bool
    unique: bool
    maintenance: bool
    description: Optional[str]
    managed: bool
    disabled: bool
    failed: bool
    failure_ignored: bool
    target_role: Optional[PcmkRoleType]
    instances: Union[Sequence[PrimitiveStatusDto], Sequence[GroupStatusDto]]


@dataclass(frozen=True)
class BundleReplicaStatusDto(DataTransferObject):
    replica_id: str
    member: Optional[PrimitiveStatusDto]
    remote: Optional[PrimitiveStatusDto]
    container: PrimitiveStatusDto
    ip_address: Optional[PrimitiveStatusDto]


@dataclass(frozen=True)
class BundleStatusDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    resource_id: str
    type: str
    image: str
    unique: bool
    maintenance: bool
    description: Optional[str]
    managed: bool
    failed: bool
    replicas: Sequence[BundleReplicaStatusDto]


AnyResourceStatusDto = Union[
    PrimitiveStatusDto, GroupStatusDto, CloneStatusDto, BundleStatusDto
]


@dataclass(frozen=True)
class ResourcesStatusDto(DataTransferObject):
    resources: Sequence[AnyResourceStatusDto]
