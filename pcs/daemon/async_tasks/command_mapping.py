from pcs.lib.commands import (
    resource,
    status,
)

command_map = {
    "cluster status": status.full_cluster_status_plaintext,
    "resource enable": resource.enable,
}
