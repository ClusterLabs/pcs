from typing import Sequence

from dataclasses import dataclass


@dataclass(frozen=True)
class Status:
    code: int
    message: str
    errors: Sequence[str]
