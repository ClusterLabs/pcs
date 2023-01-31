from dataclasses import dataclass

from pcs.common.types import StringSequence


@dataclass(frozen=True)
class Status:
    code: int
    message: str
    errors: StringSequence
