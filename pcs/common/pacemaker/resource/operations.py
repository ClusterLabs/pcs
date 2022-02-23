from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common.const import (
    PcmkOnFailAction,
    PcmkRoleType,
)
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto


@dataclass(frozen=True)
class CibResourceOperationDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    id: str  # pylint: disable=invalid-name
    name: str
    interval: str
    description: Optional[str]
    # exactly one of start_delay and interval_origin should be defined
    start_delay: Optional[str]
    interval_origin: Optional[str]
    timeout: Optional[str]
    enabled: Optional[bool]
    record_pending: Optional[bool]
    role: Optional[PcmkRoleType]
    on_fail: Optional[PcmkOnFailAction]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]


@dataclass(frozen=True)
class ListCibResourceOperationDto(DataTransferObject):
    operations: Sequence[CibResourceOperationDto]
