from typing import (
    Any,
    Callable,
    Mapping,
)

from pcs.lib.commands import (
    resource,
    status,
)

command_map: Mapping[str, Callable[..., Any]] = {
    "cluster_status": status.full_cluster_status_plaintext,
    "resource_enable": resource.enable,
}
