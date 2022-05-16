import time
from typing import (
    Iterable,
    List,
    Optional,
)

from pcs.common.tools import get_unique_uuid
from pcs.lib.interface.config import FacadeInterface

from .types import TokenEntry


class Facade(FacadeInterface):
    def __init__(self, parsed_config: Iterable[TokenEntry]) -> None:
        _parsed_config: List[TokenEntry] = list(parsed_config)
        super().__init__(_parsed_config)
        self._token_list = _parsed_config
        self._token_map = {entry.token: entry for entry in _parsed_config}

    def get_user(self, token: str) -> Optional[str]:
        entry = self._token_map.get(token)
        if entry is None:
            return None
        return entry.username

    def add_user(self, username: str) -> str:
        entry = TokenEntry(
            username=username,
            token=get_unique_uuid(self._token_map),
            creation_date=time.strftime("%Y-%m-%d %H:%M:%S %z"),
        )
        self._token_list.append(entry)
        self._token_map[entry.token] = entry
        return entry.token
