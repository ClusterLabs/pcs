from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.resource_agent.dto import ResourceAgentNameDto

from .operations import CibResourceOperationDto


@dataclass(frozen=True)
class CibResourcePrimitiveDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    agent_name: ResourceAgentNameDto
    description: Optional[str]
    operations: Sequence[CibResourceOperationDto]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]
    utilization: Sequence[CibNvsetDto]
