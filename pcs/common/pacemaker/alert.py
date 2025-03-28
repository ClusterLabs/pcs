from dataclasses import dataclass
from typing import Optional, Sequence

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto


@dataclass(frozen=True)
class CibAlertRecipientDto(DataTransferObject):
    id: str
    value: str
    description: Optional[str]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]


@dataclass(frozen=True)
class CibAlertSelectAttributeDto(DataTransferObject):
    id: str
    name: str


@dataclass(frozen=True)
class CibAlertSelectDto(DataTransferObject):
    nodes: bool
    fencing: bool
    resources: bool
    attributes: bool
    attributes_select: Sequence[CibAlertSelectAttributeDto]


@dataclass(frozen=True)
class CibAlertDto(DataTransferObject):
    id: str
    path: str
    description: Optional[str]
    recipients: Sequence[CibAlertRecipientDto]
    select: Optional[CibAlertSelectDto]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]


@dataclass(frozen=True)
class CibAlertListDto(DataTransferObject):
    alerts: Sequence[CibAlertDto]
