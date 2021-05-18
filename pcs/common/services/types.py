from dataclasses import dataclass

from .common import join_multilines


@dataclass(frozen=True)
class ExecutorResult:
    retval: int
    stdout: str
    stderr: str

    @property
    def joined_output(self) -> str:
        return join_multilines([self.stderr, self.stdout])
