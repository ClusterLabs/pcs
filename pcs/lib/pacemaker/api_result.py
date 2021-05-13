from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Status:
    code: int
    message: str
    errors: Sequence[str]
