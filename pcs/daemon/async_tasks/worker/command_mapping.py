from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Mapping,
)

from pcs.lib.commands import (  # services,
    acl,
    alert,
    booth,
    cfgsync,
    cib,
    cib_options,
    cluster,
    cluster_property,
    constraint,
    fencing_topology,
    node,
    qdevice,
    quorum,
    resource,
    resource_agent,
    sbd,
    scsi,
    status,
    stonith,
    stonith_agent,
    tag,
)
from pcs.lib.permissions.config.types import PermissionAccessType as p


@dataclass(frozen=True)
class _Cmd:
    cmd: Callable[..., Any]
    required_permission: p


COMMAND_MAP: Mapping[str, _Cmd] = {
    "acl.add_permission": _Cmd(
        cmd=acl.add_permission,
        required_permission=p.GRANT,
    ),
    "acl.assign_role_to_group": _Cmd(
        cmd=acl.assign_role_to_group,
        required_permission=p.GRANT,
    ),
    "acl.assign_role_to_target": _Cmd(
        cmd=acl.assign_role_to_target,
        required_permission=p.GRANT,
    ),
    "acl.create_group": _Cmd(
        cmd=acl.create_group,
        required_permission=p.GRANT,
    ),
    "acl.create_role": _Cmd(
        cmd=acl.create_role,
        required_permission=p.GRANT,
    ),
    "acl.create_target": _Cmd(
        cmd=acl.create_target,
        required_permission=p.GRANT,
    ),
    "acl.remove_group": _Cmd(
        cmd=acl.remove_group,
        required_permission=p.GRANT,
    ),
    "acl.remove_permission": _Cmd(
        cmd=acl.remove_permission,
        required_permission=p.GRANT,
    ),
    "acl.remove_role": _Cmd(
        cmd=acl.remove_role,
        required_permission=p.GRANT,
    ),
    "acl.remove_target": _Cmd(
        cmd=acl.remove_target,
        required_permission=p.GRANT,
    ),
    "acl.unassign_role_from_group": _Cmd(
        cmd=acl.unassign_role_from_group,
        required_permission=p.GRANT,
    ),
    "acl.unassign_role_from_target": _Cmd(
        cmd=acl.unassign_role_from_target,
        required_permission=p.GRANT,
    ),
    "alert.add_recipient": _Cmd(
        cmd=alert.add_recipient,
        required_permission=p.WRITE,
    ),
    "alert.create_alert": _Cmd(
        cmd=alert.create_alert,
        required_permission=p.WRITE,
    ),
    "alert.get_config_dto": _Cmd(
        cmd=alert.get_config_dto,
        required_permission=p.READ,
    ),
    "alert.remove_alert": _Cmd(
        cmd=alert.remove_alert,
        required_permission=p.WRITE,
    ),
    "alert.remove_recipient": _Cmd(
        cmd=alert.remove_recipient,
        required_permission=p.WRITE,
    ),
    "alert.update_alert": _Cmd(
        cmd=alert.update_alert,
        required_permission=p.WRITE,
    ),
    "alert.update_recipient": _Cmd(
        cmd=alert.update_recipient,
        required_permission=p.WRITE,
    ),
    "booth.ticket_cleanup": _Cmd(
        cmd=booth.ticket_cleanup,
        required_permission=p.WRITE,
    ),
    "booth.ticket_cleanup_auto": _Cmd(
        cmd=booth.ticket_cleanup_auto,
        required_permission=p.WRITE,
    ),
    "booth.ticket_standby": _Cmd(
        cmd=booth.ticket_standby,
        required_permission=p.WRITE,
    ),
    "booth.ticket_unstandby": _Cmd(
        cmd=booth.ticket_unstandby,
        required_permission=p.WRITE,
    ),
    "cfgsync.get_configs": _Cmd(
        cmd=cfgsync.get_configs,
        required_permission=p.FULL,
    ),
    "cluster.add_nodes": _Cmd(
        cmd=cluster.add_nodes,
        required_permission=p.FULL,
    ),
    "cluster.generate_cluster_uuid": _Cmd(
        cmd=cluster.generate_cluster_uuid,
        required_permission=p.SUPERUSER,
    ),
    "cluster.get_corosync_conf_struct": _Cmd(
        cmd=cluster.get_corosync_conf_struct,
        required_permission=p.READ,
    ),
    "cluster.node_clear": _Cmd(
        cmd=cluster.node_clear,
        required_permission=p.WRITE,
    ),
    "cluster.remove_nodes": _Cmd(
        cmd=cluster.remove_nodes,
        required_permission=p.FULL,
    ),
    "cluster.rename": _Cmd(
        cmd=cluster.rename,
        required_permission=p.FULL,
    ),
    "cluster.setup": _Cmd(
        cmd=cluster.setup,
        required_permission=p.SUPERUSER,
    ),
    "cluster_property.get_properties": _Cmd(
        cmd=cluster_property.get_properties,
        required_permission=p.READ,
    ),
    "cluster_property.get_properties_metadata": _Cmd(
        cmd=cluster_property.get_properties_metadata,
        required_permission=p.READ,
    ),
    "cluster_property.set_properties": _Cmd(
        cmd=cluster_property.set_properties,
        required_permission=p.WRITE,
    ),
    "cluster_property.remove_cluster_name": _Cmd(
        cmd=cluster_property.remove_cluster_name,
        required_permission=p.WRITE,
    ),
    "cluster.wait_for_pcmk_idle": _Cmd(
        cmd=cluster.wait_for_pcmk_idle,
        required_permission=p.READ,
    ),
    "cib.remove_elements": _Cmd(
        cmd=cib.remove_elements,
        required_permission=p.WRITE,
    ),
    "cib_options.operation_defaults_config": _Cmd(
        cmd=cib_options.operation_defaults_config,
        required_permission=p.READ,
    ),
    "cib_options.resource_defaults_config": _Cmd(
        cmd=cib_options.resource_defaults_config,
        required_permission=p.READ,
    ),
    "constraint.colocation.create_with_set": _Cmd(
        cmd=constraint.colocation.create_with_set,
        required_permission=p.WRITE,
    ),
    "constraint.location.create_with_rule": _Cmd(
        cmd=constraint.location.create_plain_with_rule,
        required_permission=p.WRITE,
    ),
    "constraint.order.create_with_set": _Cmd(
        cmd=constraint.order.create_with_set,
        required_permission=p.WRITE,
    ),
    "constraint.ticket.create": _Cmd(
        cmd=constraint.ticket.create,
        required_permission=p.WRITE,
    ),
    "constraint.ticket.create_with_set": _Cmd(
        cmd=constraint.ticket.create_with_set,
        required_permission=p.WRITE,
    ),
    "constraint.ticket.remove": _Cmd(
        cmd=constraint.ticket.remove,
        required_permission=p.WRITE,
    ),
    "constraint.get_config": _Cmd(
        cmd=constraint.common.get_config,
        required_permission=p.READ,
    ),
    "fencing_topology.add_level": _Cmd(
        cmd=fencing_topology.add_level,
        required_permission=p.WRITE,
    ),
    "fencing_topology.get_config_dto": _Cmd(
        cmd=fencing_topology.get_config_dto,
        required_permission=p.READ,
    ),
    "fencing_topology.remove_all_levels": _Cmd(
        cmd=fencing_topology.remove_all_levels,
        required_permission=p.WRITE,
    ),
    "fencing_topology.remove_levels_by_params": _Cmd(
        cmd=fencing_topology.remove_levels_by_params,
        required_permission=p.WRITE,
    ),
    "fencing_topology.verify": _Cmd(
        cmd=fencing_topology.verify,
        required_permission=p.WRITE,
    ),
    "node.maintenance_unmaintenance_all": _Cmd(
        cmd=node.maintenance_unmaintenance_all,
        required_permission=p.WRITE,
    ),
    "node.maintenance_unmaintenance_list": _Cmd(
        cmd=node.maintenance_unmaintenance_list,
        required_permission=p.WRITE,
    ),
    "node.standby_unstandby_all": _Cmd(
        cmd=node.standby_unstandby_all,
        required_permission=p.WRITE,
    ),
    "node.standby_unstandby_list": _Cmd(
        cmd=node.standby_unstandby_list,
        required_permission=p.WRITE,
    ),
    "qdevice.client_net_destroy": _Cmd(
        cmd=qdevice.client_net_destroy,
        # Last step of adding qdevice into a cluster is distribution of
        # corosync.conf file with qdevice settings. This requires FULL
        # permissions currently. If that gets relaxed, we can require lower
        # permissions in here as well.
        required_permission=p.FULL,
    ),
    "qdevice.client_net_import_certificate": _Cmd(
        cmd=qdevice.client_net_import_certificate,
        # Last step of adding qdevice into a cluster is distribution of
        # corosync.conf file with qdevice settings. This requires FULL
        # permissions currently. If that gets relaxed, we can require lower
        # permissions in here as well.
        required_permission=p.FULL,
    ),
    "qdevice.client_net_setup": _Cmd(
        cmd=qdevice.client_net_setup,
        # Last step of adding qdevice into a cluster is distribution of
        # corosync.conf file with qdevice settings. This requires FULL
        # permissions currently. If that gets relaxed, we can require lower
        # permissions in here as well.
        required_permission=p.FULL,
    ),
    "quorum.device_net_certificate_check_local": _Cmd(
        cmd=quorum.device_net_certificate_check_local,
        required_permission=p.READ,
    ),
    "quorum.device_net_certificate_setup_local": _Cmd(
        cmd=quorum.device_net_certificate_setup_local,
        required_permission=p.WRITE,
    ),
    # deprecated, API v0 compatibility
    "qdevice.qdevice_net_get_ca_certificate": _Cmd(
        cmd=qdevice.qdevice_net_get_ca_certificate,
        required_permission=p.READ,
    ),
    "qdevice.qdevice_net_sign_certificate_request": _Cmd(
        cmd=qdevice.qdevice_net_sign_certificate_request,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "resource_agent.describe_agent": _Cmd(
        cmd=resource_agent.describe_agent,
        required_permission=p.READ,
    ),
    "resource_agent.get_agents_list": _Cmd(
        cmd=resource_agent.get_agents_list,
        required_permission=p.READ,
    ),
    "resource_agent.get_agent_metadata": _Cmd(
        cmd=resource_agent.get_agent_metadata,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "resource_agent.list_agents": _Cmd(
        cmd=resource_agent.list_agents,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "resource_agent.list_agents_for_standard_and_provider": _Cmd(
        cmd=resource_agent.list_agents_for_standard_and_provider,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "resource_agent.list_ocf_providers": _Cmd(
        cmd=resource_agent.list_ocf_providers,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "resource_agent.list_standards": _Cmd(
        cmd=resource_agent.list_standards,
        required_permission=p.READ,
    ),
    "resource.ban": _Cmd(
        cmd=resource.ban,
        required_permission=p.WRITE,
    ),
    "resource.create": _Cmd(
        cmd=resource.create,
        required_permission=p.WRITE,
    ),
    "resource.create_as_clone": _Cmd(
        cmd=resource.create_as_clone,
        required_permission=p.WRITE,
    ),
    "resource.create_in_group": _Cmd(
        cmd=resource.create_in_group,
        required_permission=p.WRITE,
    ),
    "resource.disable": _Cmd(
        cmd=resource.disable,
        required_permission=p.WRITE,
    ),
    "resource.disable_safe": _Cmd(
        cmd=resource.disable_safe,
        required_permission=p.WRITE,
    ),
    "resource.disable_simulate": _Cmd(
        cmd=resource.disable_simulate,
        required_permission=p.READ,
    ),
    "resource.enable": _Cmd(
        cmd=resource.enable,
        required_permission=p.WRITE,
    ),
    "resource.get_configured_resources": _Cmd(
        cmd=resource.get_configured_resources,
        required_permission=p.READ,
    ),
    "resource.group_add": _Cmd(
        cmd=resource.group_add,
        required_permission=p.WRITE,
    ),
    "resource.manage": _Cmd(
        cmd=resource.manage,
        required_permission=p.WRITE,
    ),
    "resource.update_meta": _Cmd(
        cmd=resource.update_meta,
        required_permission=p.WRITE,
    ),
    "resource.move": _Cmd(
        cmd=resource.move,
        required_permission=p.WRITE,
    ),
    "resource.move_autoclean": _Cmd(
        cmd=resource.move_autoclean,
        required_permission=p.WRITE,
    ),
    "resource.restart": _Cmd(
        cmd=resource.restart,
        required_permission=p.WRITE,
    ),
    "resource.unmanage": _Cmd(
        cmd=resource.unmanage,
        required_permission=p.WRITE,
    ),
    "resource.unmove_unban": _Cmd(
        cmd=resource.unmove_unban,
        required_permission=p.WRITE,
    ),
    "sbd.disable_sbd": _Cmd(
        cmd=sbd.disable_sbd,
        required_permission=p.WRITE,
    ),
    "sbd.enable_sbd": _Cmd(
        cmd=sbd.enable_sbd,
        required_permission=p.WRITE,
    ),
    "scsi.unfence_node": _Cmd(
        cmd=scsi.unfence_node,
        required_permission=p.WRITE,
    ),
    "scsi.unfence_node_mpath": _Cmd(
        cmd=scsi.unfence_node_mpath,
        required_permission=p.WRITE,
    ),
    # deprecated, API v1 compatibility
    "status.full_cluster_status_plaintext": _Cmd(
        cmd=status.full_cluster_status_plaintext,
        required_permission=p.READ,
    ),
    "status.resources_status": _Cmd(
        cmd=status.resources_status,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "stonith_agent.describe_agent": _Cmd(
        cmd=stonith_agent.describe_agent,
        required_permission=p.READ,
    ),
    # deprecated, API v1 compatibility
    "stonith_agent.list_agents": _Cmd(
        cmd=stonith_agent.list_agents,
        required_permission=p.READ,
    ),
    "stonith.create": _Cmd(
        cmd=stonith.create,
        required_permission=p.WRITE,
    ),
    "tag.get_config_dto": _Cmd(
        cmd=tag.get_config_dto,
        required_permission=p.READ,
    ),
    # CMDs allowed in pcs_internal but not exposed via REST API:
    # "services.disable_service": Cmd(services.disable_service,
    # "services.enable_service": Cmd(services.enable_service,
    # "services.get_services_info": Cmd(services.get_services_info,
    # "services.start_service": Cmd(services.start_service,
    # "services.stop_service": Cmd(services.stop_service,
}


LEGACY_API_COMMANDS = (
    "qdevice.qdevice_net_get_ca_certificate",
    "resource_agent.describe_agent",
    "resource_agent.list_agents",
    "resource_agent.list_agents_for_standard_and_provider",
    "resource_agent.list_ocf_providers",
    "resource_agent.list_standards",
    "status.full_cluster_status_plaintext",
    "stonith_agent.describe_agent",
    "stonith_agent.list_agents",
)
