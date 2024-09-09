from collections.abc import Sequence
from dataclasses import dataclass
from typing import Union

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class CibFencingLevelNodeDto(DataTransferObject):
    id: str
    target: str
    index: int
    devices: list[str]


@dataclass(frozen=True)
class CibFencingLevelRegexDto(DataTransferObject):
    id: str
    target_pattern: str
    index: int
    devices: list[str]


@dataclass(frozen=True)
class CibFencingLevelAttributeDto(DataTransferObject):
    id: str
    target_attribute: str
    target_value: str
    index: int
    devices: list[str]


CibFencingLevel = Union[
    CibFencingLevelNodeDto, CibFencingLevelRegexDto, CibFencingLevelAttributeDto
]


@dataclass(frozen=True)
class CibFencingTopologyDto(DataTransferObject):
    target_node: Sequence[CibFencingLevelNodeDto]
    target_regex: Sequence[CibFencingLevelRegexDto]
    target_attribute: Sequence[CibFencingLevelAttributeDto]
