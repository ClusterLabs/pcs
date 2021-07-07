require 'json'

require 'pcs.rb'
require 'permissions.rb'

def route_api_v1(auth_user, params, request)
  req_map = {
    'acl-create-role/v1' => {
      :cmd => 'acl.create_role',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-remove-role/v1' => {
      :cmd => 'acl.remove_role',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-assign-role-to-target/v1' => {
      :cmd => 'acl.assign_role_to_target',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-assign-role-to-group/v1' => {
      :cmd => 'acl.assign_role_to_group',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-unassign-role-from-target/v1' => {
      :cmd => 'acl.unassign_role_from_target',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-unassign-role-from-group/v1' => {
      :cmd => 'acl.unassign_role_from_group',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-create-target/v1' => {
      :cmd => 'acl.create_target',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-create-group/v1' => {
      :cmd => 'acl.create_group',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-remove-target/v1' => {
      :cmd => 'acl.remove_target',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-remove-group/v1' => {
      :cmd => 'acl.remove_group',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-add-permission/v1' => {
      :cmd => 'acl.add_permission',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'acl-remove-permission/v1' => {
      :cmd => 'acl.remove_permission',
      :only_superuser => false,
      :permissions => Permissions::GRANT,
    },
    'alert-create-alert/v1' => {
      :cmd => 'alert.create_alert',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'alert-update-alert/v1' => {
      :cmd => 'alert.update_alert',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'alert-remove-alert/v1' => {
      :cmd => 'alert.remove_alert',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'alert-add-recipient/v1' => {
      :cmd => 'alert.add_recipient',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'alert-update-recipient/v1' => {
      :cmd => 'alert.update_recipient',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'alert-remove-recipient/v1' => {
      :cmd => 'alert.remove_recipient',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'cluster-add-nodes/v1' => {
      :cmd => 'cluster.add_nodes',
      :only_superuser => false,
      :permissions => Permissions::FULL,
      # TODO: add allowed HTTP method? (e.g. POST, GET, ...)
    },
    'cluster-node-clear/v1' => {
      :cmd => 'cluster.node_clear',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'cluster-remove-nodes/v1' => {
      :cmd => 'cluster.remove_nodes',
      :only_superuser => false,
      :permissions => Permissions::FULL,
    },
    'cluster-setup/v1' => {
      :cmd => 'cluster.setup',
      :only_superuser => true,
      :permissions => nil,
    },
    'constraint-colocation-create-with-set/v1' => {
      :cmd => 'constraint_colocation.create_with_set',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'constraint-order-create-with-set/v1' => {
      :cmd => 'constraint_order.create_with_set',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'constraint-ticket-create-with-set/v1' => {
      :cmd => 'constraint_ticket.create_with_set',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'constraint-ticket-create/v1' => {
      :cmd => 'constraint_ticket.create',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'constraint-ticket-remove/v1' => {
      :cmd => 'constraint_ticket.remove',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'fencing-topology-add-level/v1' => {
      :cmd => 'fencing_topology.add_level',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'fencing-topology-remove-all-levels/v1' => {
      :cmd => 'fencing_topology.remove_all_levels',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'fencing-topology-remove-levels-by-params/v1' => {
      :cmd => 'fencing_topology.remove_levels_by_params',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'fencing-topology-verify/v1' => {
      :cmd => 'fencing_topology.verify',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'node-maintenance-unmaintenance/v1' => {
      :cmd => 'node.maintenance_unmaintenance_list',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'node-maintenance-unmaintenance-all/v1' => {
      :cmd => 'node.maintenance_unmaintenance_all',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'node-standby-unstandby/v1' => {
      :cmd => 'node.standby_unstandby_list',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'node-standby-unstandby-all/v1' => {
      :cmd => 'node.standby_unstandby_all',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'qdevice-client-net-import-certificate/v1' => {
      :cmd => 'qdevice.client_net_import_certificate',
      :only_superuser => false,
      :permissions => Permissions::FULL,
    },
    'qdevice-qdevice-net-sign-certificate-request/v1' => {
      :cmd => 'qdevice.qdevice_net_sign_certificate_request',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-agent-describe-agent/v1' => {
      :cmd => 'resource_agent.describe_agent',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-agent-list-agents/v1' => {
      :cmd => 'resource_agent.list_agents',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-agent-list-agents-for-standard-and-provider/v1' => {
      :cmd => 'resource_agent.list_agents_for_standard_and_provider',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-agent-list-ocf-providers/v1' => {
      :cmd => 'resource_agent.list_ocf_providers',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-agent-list-standards/v1' => {
      :cmd => 'resource_agent.list_standards',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-ban/v1' => {
      :cmd => 'resource.ban',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-create/v1' => {
      :cmd => 'resource.create',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-create-as-clone/v1' => {
      :cmd => 'resource.create_as_clone',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-create-in-group/v1' => {
      :cmd => 'resource.create_in_group',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-disable/v1' => {
      :cmd => 'resource.disable',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-disable-safe/v1' => {
      :cmd => 'resource.disable_safe',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-disable-simulate/v1' => {
      :cmd => 'resource.disable_simulate',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'resource-enable/v1' => {
      :cmd => 'resource.enable',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-group-add/v1' => {
      :cmd => 'resource.group_add',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-manage/v1' => {
      :cmd => 'resource.manage',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-move/v1' => {
      :cmd => 'resource.move',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-unmanage/v1' => {
      :cmd => 'resource.unmanage',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-unmove-unban/v1' => {
      :cmd => 'resource.unmove_unban',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'sbd-disable-sbd/v1' => {
      :cmd => 'sbd.disable_sbd',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'sbd-enable-sbd/v1' => {
      :cmd => 'sbd.enable_sbd',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'scsi-unfence-node/v1' => {
      :cmd => 'scsi.unfence_node',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
      # TODO: make sure permissons are set properly
    },
    'stonith-agent-describe-agent/v1' => {
      :cmd => 'stonith_agent.describe_agent',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'stonith-agent-list-agents/v1' => {
      :cmd => 'stonith_agent.list_agents',
      :only_superuser => false,
      :permissions => Permissions::READ,
    },
    'stonith-create/v1' => {
      :cmd => 'stonith.create',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'stonith-create-in-group/v1' => {
      :cmd => 'stonith.create_in_group',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
  }
  cmd_str = params[:splat].join('/')
  unless req_map.include?(cmd_str)
    return [
      404,
      JSON.generate(get_pcs_internal_output_format(
        'unknown_command', "Unknown command '/api/v1/#{cmd_str}'"
      )),
    ]
  end
  cmd = req_map[cmd_str]
  if cmd[:only_superuser] and not allowed_for_superuser(auth_user)
    return [
      403,
      JSON.generate(get_pcs_internal_output_format(
        'permission_denied',
        "Permission denied. Superuser required",
      )),
    ]
  end
  if cmd[:permissions] and not allowed_for_local_cluster(auth_user, cmd[:permissions])
    return [
      403,
      JSON.generate(get_pcs_internal_output_format(
        'permission_denied',
        "Permission denied. Required permission level is #{cmd[:permissions]}",
      )),
    ]
  end
  return pcs_internal_proxy(auth_user, request.body.read, cmd[:cmd])
end
