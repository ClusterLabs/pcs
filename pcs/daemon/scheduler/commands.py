from typing import (
    Any,
    Dict,
    List,
)

class Command:
    def __init__(self, command_name, params):
        self.command_name: str = command_name
        self.params: Dict[str, Any] = params

class WorkerCommand:
    def __init__(self, task_ident, command):
        self.command: Command = command
        self.task_ident: str = task_ident
