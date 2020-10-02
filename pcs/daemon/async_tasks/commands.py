from dataclasses import dataclass

from pcs.daemon.async_tasks.dto import CommandDto


@dataclass(frozen=True)
class WorkerCommand:
    task_ident: str
    command: CommandDto
