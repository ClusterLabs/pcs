from typing import Sequence

from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.resource_agent.dto import ResourceAgentParameterDto
from pcs.common.types import StringCollection


@dataclass(frozen=True)
class ClusterPropertyMetadataDto(DataTransferObject):
    properties_metadata: Sequence[ResourceAgentParameterDto]
    readonly_properties: StringCollection
