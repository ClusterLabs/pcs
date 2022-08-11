from dataclasses import dataclass


@dataclass(frozen=True)
class TokenEntry:
    token: str
    username: str
    creation_date: str
