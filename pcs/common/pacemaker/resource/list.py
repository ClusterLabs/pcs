from dataclasses import dataclass
from typing import Sequence

from pcs.common.interface.dto import DataTransferObject

from .bundle import CibResourceBundleDto
from .clone import CibResourceCloneDto
from .group import CibResourceGroupDto
from .primitive import CibResourcePrimitiveDto


@dataclass(frozen=True)
class CibResourcesDto(DataTransferObject):
    primitives: Sequence[CibResourcePrimitiveDto]
    clones: Sequence[CibResourceCloneDto]
    groups: Sequence[CibResourceGroupDto]
    bundles: Sequence[CibResourceBundleDto]
