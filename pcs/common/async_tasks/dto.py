from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
)

from pcs.common.async_tasks.types import TaskFinishType, TaskState
from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class CommandDto(DataTransferObject):
    command_name: str
    params: Dict[str, Any]


@dataclass(frozen=True)
class TaskIdentDto(DataTransferObject):
    task_ident: str


@dataclass(frozen=True)
class TaskResultDto(DataTransferObject):
    task_ident: str
    command: CommandDto
    reports: List[Any]
    state: TaskState
    task_finish_type: TaskFinishType
    result: Any
