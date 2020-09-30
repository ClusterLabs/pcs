from enum import Enum
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Type,
    TYPE_CHECKING,
)

from pcs.common.interface.dto import (
    DataTransferObject,
    DtoPayload,
    DtoType,
    from_dict_unconfigured,
)

if TYPE_CHECKING:
    from pcs.daemon.scheduler.commands import Command
    from pcs.daemon.scheduler.task import (
        TaskFinishType,
        TaskState,
    )


def from_dict(cls: Type[DtoType], data: DtoPayload) -> DtoType:
    """Redefinition from common with module-specific enums"""
    cast_config: list = [Type["TaskState"], Type["TaskFinishType"]]
    return from_dict_unconfigured(cls, data, cast_config)


@dataclass(frozen=True)
class CommandDto(DataTransferObject):
    command_name: str
    params: Dict[str, Any]


@dataclass(frozen=True)
class TaskResultDto(DataTransferObject):
    task_ident: str
    command: "Command"
    reports: List[Any]
    state: "TaskState"
    task_finish_type: "TaskFinishType"
    result: Any
