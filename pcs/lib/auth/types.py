from dataclasses import dataclass
from typing import Optional

from pcs.common.tools import StringCollection

from . import const


@dataclass(frozen=True)
class AuthUser:
    username: str
    groups: StringCollection

    @property
    def is_superuser(self) -> bool:
        return self.username == const.SUPERUSER


@dataclass(frozen=True)
class DesiredUser:
    username: Optional[str]
    groups: Optional[StringCollection]
