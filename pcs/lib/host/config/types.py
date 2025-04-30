from dataclasses import dataclass
from typing import Mapping

from pcs.common.host import PcsKnownHost


@dataclass(frozen=True)
class KnownHosts:
    format_version: int
    data_version: int
    known_hosts: Mapping[str, PcsKnownHost]
