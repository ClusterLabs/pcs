from dataclasses import dataclass
from typing import (
    NewType,
    Optional,
    Sequence,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto

ContainerType = NewType("ContainerType", str)

CONTAINER_TYPE_DOCKER = ContainerType("docker")
CONTAINER_TYPE_PODMAN = ContainerType("podman")


@dataclass(frozen=True)
class CibResourceBundleContainerRuntimeOptionsDto(DataTransferObject):
    image: str
    replicas: Optional[int]
    replicas_per_host: Optional[int]
    promoted_max: Optional[int]
    run_command: Optional[str]
    network: Optional[str]
    options: Optional[str]


@dataclass(frozen=True)
class CibResourceBundlePortMappingDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    port: Optional[int]
    internal_port: Optional[int]
    range: Optional[str]


@dataclass(frozen=True)
class CibResourceBundleNetworkOptionsDto(DataTransferObject):
    ip_range_start: Optional[str]
    control_port: Optional[int]
    host_interface: Optional[str]
    host_netmask: Optional[int]
    add_host: Optional[bool]


@dataclass(frozen=True)
class CibResourceBundleStorageMappingDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    source_dir: Optional[str]
    source_dir_root: Optional[str]
    target_dir: str
    options: Optional[str]


@dataclass(frozen=True)
class CibResourceBundleDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    id: str  # pylint: disable=invalid-name
    description: Optional[str]
    member_id: Optional[str]
    container_type: Optional[ContainerType]
    container_options: Optional[CibResourceBundleContainerRuntimeOptionsDto]
    network: Optional[CibResourceBundleNetworkOptionsDto]
    port_mappings: Sequence[CibResourceBundlePortMappingDto]
    storage_mappings: Sequence[CibResourceBundleStorageMappingDto]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]
