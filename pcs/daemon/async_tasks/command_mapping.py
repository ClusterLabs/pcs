from pcs.lib.commands import (
    resource,
    status,
)

command_map = {
    "cluster_status": status.full_cluster_status_plaintext,
    "resource_enable": resource.enable,
}
