from dataclasses import dataclass

from pcs.common.async_tasks.dto import CommandDto


@dataclass(frozen=True)
class Command:
    command_dto: CommandDto
    api_v1_compatible: bool = False
    api_v0_compatible: bool = False
