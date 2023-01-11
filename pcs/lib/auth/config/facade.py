import time
from typing import (
    Iterable,
    Optional,
    Sequence,
    cast,
)

from pcs.common.tools import get_unique_uuid
from pcs.lib.interface.config import FacadeInterface

from .types import (
    TOKEN_ENTRY_DATETIME_FORMAT,
    TokenEntry,
)


class Facade(FacadeInterface):
    def __init__(self, parsed_config: Iterable[TokenEntry]) -> None:
        super().__init__(parsed_config)

    def _set_config(self, config: Iterable[TokenEntry]) -> None:
        super()._set_config(list(config))

    @property
    def config(self) -> Sequence[TokenEntry]:
        return tuple(cast(Iterable[TokenEntry], super().config))

    def _get_entry_by_token(self, token: str) -> Optional[TokenEntry]:
        return {entry.token: entry for entry in self.config}.get(token)

    def get_user(self, token: str) -> Optional[str]:
        entry = self._get_entry_by_token(token)
        if entry is None:
            return None
        return entry.username

    def add_entry(self, username: str, token: str) -> None:
        self._set_config(
            list(self.config)
            + [
                TokenEntry(
                    username=username,
                    token=token,
                    creation_date=time.strftime(TOKEN_ENTRY_DATETIME_FORMAT),
                )
            ]
        )

    def add_user(self, username: str) -> str:
        token = get_unique_uuid(tuple(entry.token for entry in self.config))
        self.add_entry(username, token)
        return token
