from dataclasses import dataclass
from typing import (
    Mapping,
    Optional,
    Sequence,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.types import (
    CorosyncNodeAddressType,
    CorosyncTransportType,
)


@dataclass(frozen=True)
class CorosyncNodeAddressDto(DataTransferObject):
    addr: str
    link: str
    type: CorosyncNodeAddressType


@dataclass(frozen=True)
class CorosyncNodeDto(DataTransferObject):
    name: str
    nodeid: str
    addrs: Sequence[CorosyncNodeAddressDto]


@dataclass(frozen=True)
class CorosyncQuorumDeviceSettingsDto(DataTransferObject):
    model: str
    model_options: Mapping[str, str]
    generic_options: Mapping[str, str]
    heuristics_options: Mapping[str, str]


@dataclass(frozen=True)
class CorosyncConfDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    cluster_name: str
    cluster_uuid: Optional[str]
    transport: CorosyncTransportType
    totem_options: Mapping[str, str]
    transport_options: Mapping[str, str]
    compression_options: Mapping[str, str]
    crypto_options: Mapping[str, str]
    nodes: Sequence[CorosyncNodeDto]
    links_options: Mapping[str, Mapping[str, str]]
    quorum_options: Mapping[str, str]
    quorum_device: Optional[CorosyncQuorumDeviceSettingsDto]
