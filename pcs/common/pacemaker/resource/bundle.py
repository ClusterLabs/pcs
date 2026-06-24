from collections.abc import Sequence
from dataclasses import dataclass
from typing import NewType

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto

ContainerType = NewType("ContainerType", str)

CONTAINER_TYPE_DOCKER = ContainerType("docker")
CONTAINER_TYPE_PODMAN = ContainerType("podman")


@dataclass(frozen=True)
class CibResourceBundleContainerRuntimeOptionsDto(DataTransferObject):
    image: str
    replicas: int | None
    replicas_per_host: int | None
    promoted_max: int | None
    run_command: str | None
    network: str | None
    options: str | None


@dataclass(frozen=True)
class CibResourceBundlePortMappingDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    port: int | None
    internal_port: int | None
    range: str | None


@dataclass(frozen=True)
class CibResourceBundleNetworkOptionsDto(DataTransferObject):
    ip_range_start: str | None
    control_port: int | None
    host_interface: str | None
    host_netmask: int | None
    add_host: bool | None


@dataclass(frozen=True)
class CibResourceBundleStorageMappingDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    source_dir: str | None
    source_dir_root: str | None
    target_dir: str
    options: str | None


@dataclass(frozen=True)
class CibResourceBundleDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    id: str  # pylint: disable=invalid-name
    description: str | None
    member_id: str | None
    container_type: ContainerType | None
    container_options: CibResourceBundleContainerRuntimeOptionsDto | None
    network: CibResourceBundleNetworkOptionsDto | None
    port_mappings: Sequence[CibResourceBundlePortMappingDto]
    storage_mappings: Sequence[CibResourceBundleStorageMappingDto]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]
