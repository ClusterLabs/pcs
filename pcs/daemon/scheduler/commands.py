from dataclasses import dataclass
from typing import (
    Any,
    Dict,
)

@dataclass(frozen=True)
class Command:
    command_name: str
    params: Dict[str, Any]

@dataclass(frozen=True)
class WorkerCommand:
    task_ident: str
    command: Command
