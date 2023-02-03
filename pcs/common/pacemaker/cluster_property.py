from dataclasses import dataclass
from typing import Sequence

from pcs.common.interface.dto import DataTransferObject
from pcs.common.resource_agent.dto import ResourceAgentParameterDto


@dataclass(frozen=True)
class ClusterPropertyMetadataDto(DataTransferObject):
    properties_metadata: Sequence[ResourceAgentParameterDto]
