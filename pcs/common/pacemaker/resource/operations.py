from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.const import (
    PcmkOnFailAction,
    PcmkRoleType,
)
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto

OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME = "OCF_CHECK_LEVEL"


@dataclass(frozen=True)
class CibResourceOperationDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    id: str  # pylint: disable=invalid-name
    name: str
    interval: str
    description: str | None
    # exactly one of start_delay and interval_origin should be defined
    start_delay: str | None
    interval_origin: str | None
    timeout: str | None
    enabled: bool | None
    record_pending: bool | None
    role: PcmkRoleType | None
    on_fail: PcmkOnFailAction | None
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]


@dataclass(frozen=True)
class ListCibResourceOperationDto(DataTransferObject):
    operations: Sequence[CibResourceOperationDto]
