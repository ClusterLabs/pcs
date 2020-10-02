from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    TYPE_CHECKING,
)

from pcs.common.interface.dto import ImplementsFromDto

if TYPE_CHECKING:
    from pcs.daemon.async_tasks.dto import CommandDto


@dataclass(frozen=True)
class Command(ImplementsFromDto):
    command_name: str
    params: Dict[str, Any]

    @classmethod
    def from_dto(cls, dto_obj: "CommandDto") -> "Command":
        return cls(dto_obj.command_name, dto_obj.params)


@dataclass(frozen=True)
class WorkerCommand:
    task_ident: str
    command: Command
