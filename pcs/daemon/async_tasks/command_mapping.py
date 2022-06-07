from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Mapping,
)

from pcs.lib.commands import (  # services,
    acl,
    alert,
    cluster,
    constraint,
    fencing_topology,
    node,
    qdevice,
    resource,
    resource_agent,
    sbd,
    scsi,
    status,
    stonith,
    stonith_agent,
)
from pcs.lib.permissions.config.types import PermissionAccessType as p


@dataclass(frozen=True)
class Cmd:
    cmd: Callable[..., Any]
    required_permission: p


COMMAND_MAP: Mapping[str, Cmd] = {
    "acl.add_permission": Cmd(
        cmd=acl.add_permission,
        required_permission=p.GRANT,
    ),
    "acl.assign_role_to_group": Cmd(
        cmd=acl.assign_role_to_group,
        required_permission=p.GRANT,
    ),
    "acl.assign_role_to_target": Cmd(
        cmd=acl.assign_role_to_target,
        required_permission=p.GRANT,
    ),
    "acl.create_group": Cmd(
        cmd=acl.create_group,
        required_permission=p.GRANT,
    ),
    "acl.create_role": Cmd(
        cmd=acl.create_role,
        required_permission=p.GRANT,
    ),
    "acl.create_target": Cmd(
        cmd=acl.create_target,
        required_permission=p.GRANT,
    ),
    "acl.remove_group": Cmd(
        cmd=acl.remove_group,
        required_permission=p.GRANT,
    ),
    "acl.remove_permission": Cmd(
        cmd=acl.remove_permission,
        required_permission=p.GRANT,
    ),
    "acl.remove_role": Cmd(
        cmd=acl.remove_role,
        required_permission=p.GRANT,
    ),
    "acl.remove_target": Cmd(
        cmd=acl.remove_target,
        required_permission=p.GRANT,
    ),
    "acl.unassign_role_from_group": Cmd(
        cmd=acl.unassign_role_from_group,
        required_permission=p.GRANT,
    ),
    "acl.unassign_role_from_target": Cmd(
        cmd=acl.unassign_role_from_target,
        required_permission=p.GRANT,
    ),
    "alert.add_recipient": Cmd(
        cmd=alert.add_recipient,
        required_permission=p.WRITE,
    ),
    "alert.create_alert": Cmd(
        cmd=alert.create_alert,
        required_permission=p.WRITE,
    ),
    "alert.remove_alert": Cmd(
        cmd=alert.remove_alert,
        required_permission=p.WRITE,
    ),
    "alert.remove_recipient": Cmd(
        cmd=alert.remove_recipient,
        required_permission=p.WRITE,
    ),
    "alert.update_alert": Cmd(
        cmd=alert.update_alert,
        required_permission=p.WRITE,
    ),
    "alert.update_recipient": Cmd(
        cmd=alert.update_recipient,
        required_permission=p.WRITE,
    ),
    "cluster.add_nodes": Cmd(
        cmd=cluster.add_nodes,
        required_permission=p.FULL,
    ),
    "cluster.generate_cluster_uuid": Cmd(
        cmd=cluster.generate_cluster_uuid,
        required_permission=p.SUPERUSER,
    ),
    "cluster.node_clear": Cmd(
        cmd=cluster.node_clear,
        required_permission=p.WRITE,
    ),
    "cluster.remove_nodes": Cmd(
        cmd=cluster.remove_nodes,
        required_permission=p.FULL,
    ),
    "cluster.setup": Cmd(
        cmd=cluster.setup,
        required_permission=p.SUPERUSER,
    ),
    "constraint.colocation.create_with_set": Cmd(
        cmd=constraint.colocation.create_with_set,
        required_permission=p.WRITE,
    ),
    "constraint.order.create_with_set": Cmd(
        cmd=constraint.order.create_with_set,
        required_permission=p.WRITE,
    ),
    "constraint.ticket.create": Cmd(
        cmd=constraint.ticket.create,
        required_permission=p.WRITE,
    ),
    "constraint.ticket.create_with_set": Cmd(
        cmd=constraint.ticket.create_with_set,
        required_permission=p.WRITE,
    ),
    "constraint.ticket.remove": Cmd(
        cmd=constraint.ticket.remove,
        required_permission=p.WRITE,
    ),
    "fencing_topology.add_level": Cmd(
        cmd=fencing_topology.add_level,
        required_permission=p.WRITE,
    ),
    "fencing_topology.remove_all_levels": Cmd(
        cmd=fencing_topology.remove_all_levels,
        required_permission=p.WRITE,
    ),
    "fencing_topology.remove_levels_by_params": Cmd(
        cmd=fencing_topology.remove_levels_by_params,
        required_permission=p.WRITE,
    ),
    "fencing_topology.verify": Cmd(
        cmd=fencing_topology.verify,
        required_permission=p.WRITE,
    ),
    "node.maintenance_unmaintenance_all": Cmd(
        cmd=node.maintenance_unmaintenance_all,
        required_permission=p.WRITE,
    ),
    "node.maintenance_unmaintenance_list": Cmd(
        cmd=node.maintenance_unmaintenance_list,
        required_permission=p.WRITE,
    ),
    "node.standby_unstandby_all": Cmd(
        cmd=node.standby_unstandby_all,
        required_permission=p.WRITE,
    ),
    "node.standby_unstandby_list": Cmd(
        cmd=node.standby_unstandby_list,
        required_permission=p.WRITE,
    ),
    "qdevice.client_net_import_certificate": Cmd(
        cmd=qdevice.client_net_import_certificate,
        required_permission=p.FULL,
    ),
    # TODO: make sure WRITE is right permission
    "qdevice.qdevice_net_sign_certificate_request": Cmd(
        cmd=qdevice.qdevice_net_sign_certificate_request,
        required_permission=p.WRITE,
    ),
    # deprecated, use resource-agent-get-agent-metadata/v1 instead
    "resource_agent.describe_agent": Cmd(
        cmd=resource_agent.describe_agent,
        required_permission=p.READ,
    ),
    "resource_agent.get_agents_list": Cmd(
        cmd=resource_agent.get_agents_list,
        required_permission=p.READ,
    ),
    "resource_agent.get_agent_metadata": Cmd(
        cmd=resource_agent.get_agent_metadata,
        required_permission=p.READ,
    ),
    # deprecated, use resource-agent-get-agents-list/v1 instead
    "resource_agent.list_agents": Cmd(
        cmd=resource_agent.list_agents,
        required_permission=p.READ,
    ),
    "resource_agent.list_agents_for_standard_and_provider": Cmd(
        cmd=resource_agent.list_agents_for_standard_and_provider,
        required_permission=p.READ,
    ),
    "resource_agent.list_ocf_providers": Cmd(
        cmd=resource_agent.list_ocf_providers,
        required_permission=p.READ,
    ),
    "resource_agent.list_standards": Cmd(
        cmd=resource_agent.list_standards,
        required_permission=p.READ,
    ),
    "resource.ban": Cmd(
        cmd=resource.ban,
        required_permission=p.WRITE,
    ),
    "resource.create": Cmd(
        cmd=resource.create,
        required_permission=p.WRITE,
    ),
    "resource.create_as_clone": Cmd(
        cmd=resource.create_as_clone,
        required_permission=p.WRITE,
    ),
    "resource.create_in_group": Cmd(
        cmd=resource.create_in_group,
        required_permission=p.WRITE,
    ),
    "resource.disable": Cmd(
        cmd=resource.disable,
        required_permission=p.WRITE,
    ),
    "resource.disable_safe": Cmd(
        cmd=resource.disable_safe,
        required_permission=p.WRITE,
    ),
    "resource.disable_simulate": Cmd(
        cmd=resource.disable_simulate,
        required_permission=p.READ,
    ),
    "resource.enable": Cmd(
        cmd=resource.enable,
        required_permission=p.WRITE,
    ),
    "resource.group_add": Cmd(
        cmd=resource.group_add,
        required_permission=p.WRITE,
    ),
    "resource.manage": Cmd(
        cmd=resource.manage,
        required_permission=p.WRITE,
    ),
    "resource.move": Cmd(
        cmd=resource.move,
        required_permission=p.WRITE,
    ),
    "resource.move_autoclean": Cmd(
        cmd=resource.move_autoclean,
        required_permission=p.WRITE,
    ),
    "resource.unmanage": Cmd(
        cmd=resource.unmanage,
        required_permission=p.WRITE,
    ),
    "resource.unmove_unban": Cmd(
        cmd=resource.unmove_unban,
        required_permission=p.WRITE,
    ),
    "sbd.disable_sbd": Cmd(
        cmd=sbd.disable_sbd,
        required_permission=p.WRITE,
    ),
    "sbd.enable_sbd": Cmd(
        cmd=sbd.enable_sbd,
        required_permission=p.WRITE,
    ),
    "scsi.unfence_node": Cmd(
        cmd=scsi.unfence_node,
        required_permission=p.WRITE,
    ),
    "scsi.unfence_node_mpath": Cmd(
        cmd=scsi.unfence_node_mpath,
        required_permission=p.WRITE,
    ),
    "status.full_cluster_status_plaintext": Cmd(
        cmd=status.full_cluster_status_plaintext,
        required_permission=p.READ,
    ),
    # deprecated, use resource-agent-get-agent-metadata/v1 instead
    "stonith_agent.describe_agent": Cmd(
        cmd=stonith_agent.describe_agent,
        required_permission=p.READ,
    ),
    # deprecated, use resource-agent-get-agents-list/v1 instead
    "stonith_agent.list_agents": Cmd(
        cmd=stonith_agent.list_agents,
        required_permission=p.READ,
    ),
    "stonith.create": Cmd(
        cmd=stonith.create,
        required_permission=p.WRITE,
    ),
    "stonith.create_in_group": Cmd(
        cmd=stonith.create_in_group,
        required_permission=p.WRITE,
    ),
    # CMDs allowed in pcs_internal but not exposed via REST API:
    # "services.disable_service": Cmd(services.disable_service,
    # "services.enable_service": Cmd(services.enable_service,
    # "services.get_services_info": Cmd(services.get_services_info,
    # "services.start_service": Cmd(services.start_service,
    # "services.stop_service": Cmd(services.stop_service,
}

API_V1_MAP: Mapping[str, str] = {
    "acl-create-role/v1": "acl.create_role",
    "acl-remove-role/v1": "acl.remove_role",
    "acl-assign-role-to-target/v1": "acl.assign_role_to_target",
    "acl-assign-role-to-group/v1": "acl.assign_role_to_group",
    "acl-unassign-role-from-target/v1": "acl.unassign_role_from_target",
    "acl-unassign-role-from-group/v1": "acl.unassign_role_from_group",
    "acl-create-target/v1": "acl.create_target",
    "acl-create-group/v1": "acl.create_group",
    "acl-remove-target/v1": "acl.remove_target",
    "acl-remove-group/v1": "acl.remove_group",
    "acl-add-permission/v1": "acl.add_permission",
    "acl-remove-permission/v1": "acl.remove_permission",
    "alert-create-alert/v1": "alert.create_alert",
    "alert-update-alert/v1": "alert.update_alert",
    "alert-remove-alert/v1": "alert.remove_alert",
    "alert-add-recipient/v1": "alert.add_recipient",
    "alert-update-recipient/v1": "alert.update_recipient",
    "alert-remove-recipient/v1": "alert.remove_recipient",
    "cluster-add-nodes/v1": "cluster.add_nodes",
    "cluster-node-clear/v1": "cluster.node_clear",
    "cluster-remove-nodes/v1": "cluster.remove_nodes",
    "cluster-setup/v1": "cluster.setup",
    "cluster-generate-cluster-uuid/v1": "cluster.generate_cluster_uuid",
    "constraint-colocation-create-with-set/v1": "constraint.colocation.create_with_set",
    "constraint-order-create-with-set/v1": "constraint.order.create_with_set",
    "constraint-ticket-create-with-set/v1": "constraint.ticket.create_with_set",
    "constraint-ticket-create/v1": "constraint.ticket.create",
    "constraint-ticket-remove/v1": "constraint.ticket.remove",
    "fencing-topology-add-level/v1": "fencing_topology.add_level",
    "fencing-topology-remove-all-levels/v1": "fencing_topology.remove_all_levels",
    "fencing-topology-remove-levels-by-params/v1": "fencing_topology.remove_levels_by_params",
    "fencing-topology-verify/v1": "fencing_topology.verify",
    "node-maintenance-unmaintenance/v1": "node.maintenance_unmaintenance_list",
    "node-maintenance-unmaintenance-all/v1": "node.maintenance_unmaintenance_all",
    "node-standby-unstandby/v1": "node.standby_unstandby_list",
    "node-standby-unstandby-all/v1": "node.standby_unstandby_all",
    "qdevice-client-net-import-certificate/v1": "qdevice.client_net_import_certificate",
    "qdevice-qdevice-net-sign-certificate-request/v1": "qdevice.qdevice_net_sign_certificate_request",
    # deprecated, use resource-agent-get-agent-metadata/v1 instead
    "resource-agent-describe-agent/v1": "resource_agent.describe_agent",
    "resource-agent-get-agents-list/v1": "resource_agent.get_agents_list",
    "resource-agent-get-agent-metadata/v1": "resource_agent.get_agent_metadata",
    # deprecated, use resource-agent-get-agents-list/v1 instead
    "resource-agent-list-agents/v1": "resource_agent.list_agents",
    "resource-agent-list-agents-for-standard-and-provider/v1": "resource_agent.list_agents_for_standard_and_provider",
    "resource-agent-list-ocf-providers/v1": "resource_agent.list_ocf_providers",
    "resource-agent-list-standards/v1": "resource_agent.list_standards",
    "resource-ban/v1": "resource.ban",
    "resource-create/v1": "resource.create",
    "resource-create-as-clone/v1": "resource.create_as_clone",
    "resource-create-in-group/v1": "resource.create_in_group",
    "resource-disable/v1": "resource.disable",
    "resource-disable-safe/v1": "resource.disable_safe",
    "resource-disable-simulate/v1": "resource.disable_simulate",
    "resource-enable/v1": "resource.enable",
    "resource-group-add/v1": "resource.group_add",
    "resource-manage/v1": "resource.manage",
    "resource-move/v1": "resource.move",
    "resource-move-autoclean/v1": "resource.move_autoclean",
    "resource-unmanage/v1": "resource.unmanage",
    "resource-unmove-unban/v1": "resource.unmove_unban",
    "sbd-disable-sbd/v1": "sbd.disable_sbd",
    "sbd-enable-sbd/v1": "sbd.enable_sbd",
    "scsi-unfence-node/v2": "scsi.unfence_node",
    "scsi-unfence-node-mpath/v1": "scsi.unfence_node_mpath",
    # deprecated, use resource-agent-get-agent-metadata/v1 instead
    "stonith-agent-describe-agent/v1": "stonith_agent.describe_agent",
    # deprecated, use resource-agent-get-agents-list/v1 instead
    "stonith-agent-list-agents/v1": "stonith_agent.list_agents",
    "stonith-create/v1": "stonith.create",
    "stonith-create-in-group/v1": "stonith.create_in_group",
}
