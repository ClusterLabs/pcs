from dataclasses import dataclass

TOKEN_ENTRY_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"


@dataclass(frozen=True)
class TokenEntry:
    token: str
    username: str
    creation_date: str
