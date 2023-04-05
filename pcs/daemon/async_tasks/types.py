from dataclasses import dataclass

from pcs.common.async_tasks.dto import CommandDto


@dataclass(frozen=True)
class Command:
    command_dto: CommandDto
    is_legacy_command: bool = False
