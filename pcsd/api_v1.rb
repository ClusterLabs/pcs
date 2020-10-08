require 'json'

require 'pcs.rb'
require 'permissions.rb'

def route_api_v1(auth_user, params, request)
  req_map = {
    'cluster-add-nodes/v1' => {
      :cmd => 'cluster.add_nodes',
      :only_superuser => false,
      :permissions => Permissions::FULL,
      # TODO: add allowed HTTP method? (e.g. POST, GET, ...)
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
    'node-maintenance-unmaintenance/v1' => {
      :cmd => 'node.maintenance_unmaintenance_list',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'node-standby-unstandby/v1' => {
      :cmd => 'node.standby_unstandby_list',
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
    'resource-enable/v1' => {
      :cmd => 'resource.enable',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-manage/v1' => {
      :cmd => 'resource.manage',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'resource-unmanage/v1' => {
      :cmd => 'resource.unmanage',
      :only_superuser => false,
      :permissions => Permissions::WRITE,
    },
    'stonith-create/v1' => {
      :cmd => 'stonith.create',
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
