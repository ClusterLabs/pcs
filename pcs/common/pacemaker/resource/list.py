from dataclasses import dataclass
from itertools import chain
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


def get_all_resources_ids(resources_dto: CibResourcesDto) -> set[str]:
    return set(
        chain(
            (primitive.id for primitive in resources_dto.primitives),
            (group.id for group in resources_dto.groups),
            (clone.id for clone in resources_dto.clones),
            (bundle.id for bundle in resources_dto.bundles),
        )
    )


def get_stonith_resources_ids(resources_dto: CibResourcesDto) -> set[str]:
    return set(
        primitive.id
        for primitive in resources_dto.primitives
        if primitive.agent_name.standard == "stonith"
    )
