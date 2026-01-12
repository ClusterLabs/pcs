require 'json'
require 'uri'
require 'childprocess'
require 'set'
require 'timeout'
require 'rexml/document'
require 'tempfile'
require 'stringio'

require 'pcs.rb'
require 'resource.rb'
require 'settings.rb'
require 'config.rb'
require 'cfgsync.rb'
require 'cluster_entity.rb'
require 'permissions.rb'
require 'auth.rb'
require 'pcsd_file'
require 'pcsd_remove_file'
require 'pcsd_action_command'
require 'pcsd_exchange_format.rb'

# Commands for remote access
def remote(params, request, auth_user)
  remote_cmd_without_pacemaker = {
      :status => method(:node_status),
      :cluster_status => method(:cluster_status_remote),
      :get_quorum_info => method(:get_quorum_info),
      :get_corosync_conf => method(:get_corosync_conf_remote),
      :set_corosync_conf => method(:set_corosync_conf),
      :get_sync_capabilities => method(:get_sync_capabilities),
      :set_sync_options => method(:set_sync_options),
      :set_configs => method(:set_configs),
      :set_certs => method(:set_certs),
      :get_permissions => method(:get_permissions_remote),
      :set_permissions => method(:set_permissions_remote),
      :cluster_start => method(:cluster_start),
      :cluster_stop => method(:cluster_stop),
      :config_restore => method(:config_restore),
      :cluster_enable => method(:cluster_enable),
      :cluster_disable => method(:cluster_disable),
      :get_sw_versions => method(:get_sw_versions),
      :cluster_destroy => method(:cluster_destroy),
      :get_cluster_known_hosts => method(:get_cluster_known_hosts),
      :known_hosts_change => method(:known_hosts_change),
      :get_cluster_properties_definition => method(:get_cluster_properties_definition),
      :check_sbd => method(:check_sbd),
      :set_sbd_config => method(:set_sbd_config),
      :get_sbd_config => method(:get_sbd_config),
      :sbd_disable => method(:sbd_disable),
      :sbd_enable => method(:sbd_enable),
      :remove_stonith_watchdog_timeout=> method(:remove_stonith_watchdog_timeout),
      :set_stonith_watchdog_timeout_to_zero => method(:set_stonith_watchdog_timeout_to_zero),
      :qdevice_client_enable => method(:qdevice_client_enable),
      :qdevice_client_disable => method(:qdevice_client_disable),
      :qdevice_client_start => method(:qdevice_client_start),
      :qdevice_client_stop => method(:qdevice_client_stop),
      :booth_set_config => method(:booth_set_config),
      :booth_save_files => method(:booth_save_files),
      :booth_get_config => method(:booth_get_config),
      :put_file => method(:put_file),
      :remove_file => method(:remove_file),
      :manage_services => method(:manage_services),
      :check_host => method(:check_host),
      :reload_corosync_conf => method(:reload_corosync_conf),
      :remove_nodes_from_cib => method(:remove_nodes_from_cib),
      # lib api:
      # /api/v1/resource-agent-list-agents/v1
      :get_avail_resource_agents => method(:get_avail_resource_agents),
  }
  remote_cmd_with_pacemaker = {
      :pacemaker_node_status => method(:remote_pacemaker_node_status),
      :resource_start => method(:resource_start),
      :resource_stop => method(:resource_stop),
      :resource_cleanup => method(:resource_cleanup),
      :resource_refresh => method(:resource_refresh),
      :update_resource => method(:update_resource),
      :update_fence_device => method(:update_fence_device),
      :remove_resource => method(:remove_resource),
      # lib api:
      # /api/v1/constraint-ticket-create/v1
      :add_constraint_remote => method(:add_constraint_remote),
      :add_constraint_rule_remote => method(:add_constraint_rule_remote),
      # lib api:
      # /api/v1/constraint-colocation-create-with-set/v1
      # /api/v1/constraint-order-create-with-set/v1
      # /api/v1/constraint-ticket-create-with-set/v1
      # location is not supported => lib commands fully replaces this url
      :add_constraint_set_remote => method(:add_constraint_set_remote),
      # lib api:
      # /api/v1/constraint-ticket-remove/v1
      :remove_constraint_remote => method(:remove_constraint_remote),
      :remove_constraint_rule_remote => method(:remove_constraint_rule_remote),
      :add_meta_attr_remote => method(:add_meta_attr_remote),
      # lib api:
      # /api/v1/resource-group-add/v1
      :add_group => method(:add_group),
      :update_cluster_settings => method(:update_cluster_settings),
      # lib api:
      # /api/v1/fencing-topology-add-level/v1
      :add_fence_level_remote => method(:add_fence_level_remote),
      :add_node_attr_remote => method(:add_node_attr_remote),
      # lib api:
      # /api/v1/acl-create-role/v1
      :add_acl_role => method(:add_acl_role_remote),
      # lib api:
      # /api/v1/acl-remove-role/v1
      :remove_acl_roles => method(:remove_acl_roles_remote),
      :add_acl => method(:add_acl_remote),
      :remove_acl => method(:remove_acl_remote),
      :resource_change_group => method(:resource_change_group),
      :resource_promotable => method(:resource_promotable),
      :resource_clone => method(:resource_clone),
      :resource_unclone => method(:resource_unclone),
      :resource_ungroup => method(:resource_ungroup),
      :set_resource_utilization => method(:set_resource_utilization),
      :set_node_utilization => method(:set_node_utilization),
  }

  command = params[:command].to_sym
  begin
    if remote_cmd_without_pacemaker.include? command
      return remote_cmd_without_pacemaker[command].call(
        params, request, auth_user
      )
    elsif remote_cmd_with_pacemaker.include? command
      if pacemaker_running?
        return remote_cmd_with_pacemaker[command].call(params, request, auth_user)
      else
        return [200,'{"pacemaker_not_running":true}']
      end
    else
      return [404, "Unknown Request"]
    end
  rescue NotImplementedException => e
    return [501, "#{e}"]
  end
end

def _get_param_list(params)
  param_line = []
  meta_options = []
  flags = []
  params.each { |param, val|
    if param.start_with?("_res_paramne_") or (param.start_with?("_res_paramempty_") and val != "")
      myparam = param.sub(/^_res_paramne_/,"").sub(/^_res_paramempty_/,"")
      param_line << "#{myparam}=#{val}"
    end
    if param == "disabled"
      meta_options << 'meta' << 'target-role=Stopped'
    end
    if param == "force" and val
      flags << "--force"
    end
  }
  return param_line + meta_options, flags
end

# provides remote cluster status to a local gui
def cluster_status_gui(auth_user, cluster_name, dont_update_config=false)
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  unless config.is_cluster_name_in_use(cluster_name)
    return 404, 'Unknown cluster'
  end
  cluster_nodes = config.get_nodes(cluster_name)
  status = cluster_status_from_nodes(auth_user, cluster_nodes, cluster_name)
  unless status
    return 403, 'Permission denied'
  end

  if dont_update_config
    return JSON.generate(status)
  end

  # source for :corosync_offline, etc... is result of command `pcs status nodes
  # both` launched on one of cluster nodes.
  new_cluster_nodes = []
  new_cluster_nodes += status[:corosync_offline] if status[:corosync_offline]
  new_cluster_nodes += status[:corosync_online] if status[:corosync_online]
  new_cluster_nodes += status[:pacemaker_offline] if status[:pacemaker_offline]
  new_cluster_nodes += status[:pacemaker_online] if status[:pacemaker_online]
  new_cluster_nodes.uniq!
  if new_cluster_nodes.length == 0
    # We haven't got direct info about participating nodes from one of cluster
    # nodes. But it does not mean that cluster does not exist - all nodes can
    # be offline!
    # So, we use nodes from :node_list. There is a set of nodes we have
    # provided to `cluster_status_from_nodes` (i.e. from pcs_settings) minus
    # nodes that reliably have said that they are in another cluster. If
    # :node_list is empty it means that all nodes from pcs_settings have said
    # that they are in another cluster and requested cluster should be removed
    # from pcs_settings.
    new_cluster_nodes = status[:node_list].map{|n| n[:name]}
  end


  if config.cluster_nodes_equal?(cluster_name, new_cluster_nodes)
    return JSON.generate(status)
  end

  _update_pcsd_settings(config, cluster_name, new_cluster_nodes)

  if new_cluster_nodes.length > 0
    return cluster_status_gui(auth_user, cluster_name, true)
  end
  return JSON.generate(status)
end

def _update_pcsd_settings(config, cluster_name, new_nodes)
  old_nodes = config.get_nodes(cluster_name)

  # removing log is embedded in config.update_cluster
  $logger.info(
    "Updating node list for: #{cluster_name} #{old_nodes}->#{new_nodes}"
  )

  config.update_cluster(cluster_name, new_nodes)
  sync_config = Cfgsync::PcsdSettings.from_text(config.text())
  # on version conflict just go on, config will be corrected eventually
  # by displaying the cluster in the web UI
  Cfgsync::save_sync_new_version(
    sync_config, get_corosync_nodes_names(), $cluster_name, true
  )
end

# get cluster status and return it to a remote gui or other client
def cluster_status_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end

  cluster_name = $cluster_name
  # If node is not in a cluster, return empty data
  if not cluster_name or cluster_name.empty?
    overview = {
      :cluster_name => nil,
      :error_list => [],
      :warning_list => [],
      :quorate => nil,
      :status => 'unknown',
      :node_list => [],
      :resource_list => [],
    }
    return JSON.generate(overview)
  end

  cluster_nodes = get_nodes().flatten
  status = cluster_status_from_nodes(auth_user, cluster_nodes, cluster_name)
  unless status
    return 403, 'Permission denied'
  end
  return JSON.generate(status)
end

def cluster_start(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'cluster_start', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    cmd = ['cluster', 'start']
    flags = []
    flags << '--all' if params[:all] == '1'
    $logger.info "Starting Daemons"
    output, stderr, retval = run_cmd(auth_user, PCS, *flags, '--',  *cmd)
    if retval != 0
      return [400, (output + stderr).join]
    else
      return stderr
    end
  end
end

def cluster_stop(params, request, auth_user)
  if params[:name]
    params_without_name = params.reject {|key, value|
      key == "name" or key == :name
    }
    code, response = send_request_with_token(
      auth_user, params[:name], 'cluster_stop', true, params_without_name
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    options = []
    if params.has_key?("component")
      if params["component"].downcase == "pacemaker"
        options << "--pacemaker"
      elsif params["component"].downcase == "corosync"
        options << "--corosync"
      end
    end
    options << "--force" if params["force"]
    options << '--all' if params[:all] == '1'
    $logger.info "Stopping Daemons"
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, *options, "--", "cluster", "stop"
    )
    if retval != 0
      return [400, stderr.join]
    else
      return stderr.join
    end
  end
end

def config_restore(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'config_restore', true,
      {:tarball => params[:tarball]}
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::FULL)
      return 403, 'Permission denied'
    end
    $logger.info "Restore node configuration"
    if params[:tarball] != nil and params[:tarball] != ""
      read_stderr, write_stderr = IO.pipe
      begin
        pcs_restore_config = ChildProcess.build(PCS, "config", "restore", "--local")
        pcs_restore_config.io.stderr = write_stderr
        pcs_restore_config.duplex = true
        pcs_restore_config.start
        write_stderr.close
        pcs_restore_config.io.stdin.print params[:tarball]
        pcs_restore_config.io.stdin.close
        error_output_io = StringIO.new
        thread = Thread.new do
          begin
            loop do
              error_output_io.write(read_stderr.readpartial(16384))
            end
          rescue EOFError
            # Child has closed the write end of the pipe
          end
        end
      pcs_restore_config.wait
      thread.join
      ensure
        read_stderr.close
      end
      error_output_io.rewind
      error_output = error_output_io.readlines()
      retval = pcs_restore_config.exit_code
      if retval == 0
        $logger.info "Restore successful"
        return "Succeeded"
      else
        $logger.info "Error during restore: #{error_output.join('').strip()}"
        return error_output.length > 0 ? error_output.join('').strip() : "Error"
      end
    else
      $logger.info "Error: Invalid tarball"
      return "Error: Invalid tarball"
    end
  end
end

def cluster_enable(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'cluster_enable', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    success = enable_cluster(auth_user, params[:all])
    if not success
      return JSON.generate({"error" => "true"})
    end
    return "Cluster Enabled"
  end
end

def cluster_disable(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'cluster_disable', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    success = disable_cluster(auth_user, params[:all])
    if not success
      return JSON.generate({"error" => "true"})
    end
    return "Cluster Disabled"
  end
end

def get_quorum_info(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  stdout, stderr, _retval = run_cmd(
    PCSAuth.getSuperuserAuth(), COROSYNC_QUORUMTOOL, "-p", "-s"
  )
  # retval is 0 on success if node is not in partition with quorum
  # retval is 1 on error OR on success if node has quorum
  if stderr.length > 0
    return stderr.join
  else
    return stdout.join
  end
end

def get_corosync_conf_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  begin
    return get_corosync_conf()
  rescue
    return 400, 'Unable to read corosync.conf'
  end
end

# deprecated, use /remote/put_file (note that put_file doesn't support backup
# yet)
def set_corosync_conf(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  if params[:corosync_conf] != nil and params[:corosync_conf].strip != ""
    Cfgsync::CorosyncConf.backup()
    Cfgsync::CorosyncConf.from_text(params[:corosync_conf]).save()
    return 200, "Succeeded"
  else
    $logger.info "Invalid corosync.conf file"
    return 400, "Failed"
  end
end

def get_sync_capabilities(params, request, auth_user)
  return JSON.generate({
    'syncable_configs' => Cfgsync::get_cfg_classes_by_name().keys,
  })
end

def set_sync_options(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end

  options = [
    'sync_thread_pause', 'sync_thread_resume',
    'sync_thread_disable', 'sync_thread_enable',
  ]
  if params.keys.count { |key| options.include?(key) } != 1
    return [400, 'Exactly one option has to be specified']
  end

  if params['sync_thread_disable']
    if Cfgsync::ConfigSyncControl.sync_thread_disable()
      return 'sync thread disabled'
    else
      return [400, 'sync thread disable error']
    end
  end

  if params['sync_thread_enable']
    if Cfgsync::ConfigSyncControl.sync_thread_enable()
      return 'sync thread enabled'
    else
      return [400, 'sync thread enable error']
    end
  end

  if params['sync_thread_resume']
    if Cfgsync::ConfigSyncControl.sync_thread_resume()
      return 'sync thread resumed'
    else
      return [400, 'sync thread resume error']
    end
  end

  if params['sync_thread_pause']
    if Cfgsync::ConfigSyncControl.sync_thread_pause(params['sync_thread_pause'])
      return 'sync thread paused'
    else
      return [400, 'sync thread pause error']
    end
  end

  return [400, 'Exactly one option has to be specified']
end

def set_configs(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  return JSON.generate({'status' => 'bad_json'}) if not params['configs']
  begin
    configs_json = JSON.parse(params['configs'])
  rescue JSON::ParserError
    return JSON.generate({'status' => 'bad_json'})
  end
  has_cluster = !($cluster_name == nil or $cluster_name.empty?)
  if has_cluster and $cluster_name != configs_json['cluster_name']
    return JSON.generate({'status' => 'wrong_cluster_name'})
  end

  force = configs_json['force']
  remote_configs, unknown_cfg_names = Cfgsync::sync_msg_to_configs(configs_json)
  local_configs = Cfgsync::get_configs_local

  result = {}
  unknown_cfg_names.each { |name| result[name] = 'not_supported' }
  remote_configs.each { |name, remote_cfg|
    begin
      # Save a remote config if it is a newer version than local. If the config
      # is not present on a local node, the node is being added to a cluster,
      # so we need to save the config as well.
      if force or not local_configs.key?(name) or remote_cfg > local_configs[name]
        local_configs[name].class.backup() if local_configs.key?(name)
        remote_cfg.save()
        result[name] = 'accepted'
      elsif remote_cfg == local_configs[name]
        # Someone wants this node to have a config that it already has.
        # So the desired state is met and the result is a success then.
        result[name] = 'accepted'
      else
        result[name] = 'rejected'
      end
    rescue => e
      $logger.error("Error saving config '#{name}': #{e}")
      result[name] = 'error'
    end
  }
  return JSON.generate({'status' => 'ok', 'result' => result})
end

def set_certs(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end

  ssl_cert = (params['ssl_cert'] || '').strip
  ssl_key = (params['ssl_key'] || '').strip
  if ssl_cert.empty? and !ssl_key.empty?
    return [400, 'cannot save ssl certificate without ssl key']
  end
  if !ssl_cert.empty? and ssl_key.empty?
    return [400, 'cannot save ssl key without ssl certificate']
  end
  if !ssl_cert.empty? and !ssl_key.empty?
    ssl_errors = verify_cert_key_pair(ssl_cert, ssl_key)
    if ssl_errors and !ssl_errors.empty?
      return [400, ssl_errors.join('; ')]
    end
    begin
      write_file_lock(CRT_FILE, 0600, ssl_cert)
      write_file_lock(KEY_FILE, 0600, ssl_key)
    rescue => e
      # clean the files if we ended in the middle
      # the files will be regenerated on next pcsd start
      FileUtils.rm(CRT_FILE, :force => true)
      FileUtils.rm(KEY_FILE, :force => true)
      return [400, "cannot save ssl files: #{e}"]
    end
  end

  return [200, 'success']
end

def get_permissions_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
    return 403, 'Permission denied'
  end

  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  data = {
    'user_types' => Permissions::get_user_types(),
    'permission_types' => Permissions::get_permission_types(),
    'permissions_dependencies' => Permissions::permissions_dependencies(),
    'users_permissions' => pcs_config.permissions_local.to_hash(),
  }
  return [200, JSON.generate(data)]
end

def set_permissions_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
    return 403, 'Permission denied'
  end

  begin
    data = JSON.parse(params['json_data'])
  rescue JSON::ParserError
    return 400, JSON.generate({'status' => 'bad_json'})
  end

  user_set = {}
  perm_list = []
  full_users_new = Set.new
  perm_deps = Permissions.permissions_dependencies
  if data['permissions']
    data['permissions'].each { |key, perm|
      name = (perm['name'] || '').strip
      type = (perm['type'] || '').strip
      return [400, 'Missing user name'] if '' == name
      return [400, 'Missing user type'] if '' == type
      if not Permissions::is_user_type(type)
        return [400, "Unknown user type '#{type}'"]
      end

      if user_set.key?([name, type])
        return [400, "Duplicate permissions for #{type} #{name}"]
      end
      user_set[[name, type]] = true

      allow = []
      if perm['allow']
        perm['allow'].each { |perm_allow, enabled|
          next if "1" != enabled
          if not Permissions::is_permission_type(perm_allow)
            return [400, "Unknown permission '#{perm_allow}'"]
          end
          if Permissions::FULL == perm_allow
            full_users_new << [type, name]
          end
          allow << perm_allow
          # Explicitly save dependant permissions. That way if the dependency is
          # changed in the future it won't revoke permissions which were once
          # granted.
          if perm_deps['also_allows'] and perm_deps['also_allows'][perm_allow]
            allow += perm_deps['also_allows'][perm_allow]
          end
        }
      end

      perm_list << Permissions::EntityPermissions.new(type, name, allow.uniq())
    }
  end
  perm_set = Permissions::PermissionsSet.new(perm_list)

  full_users_old = Set.new
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  pcs_config.permissions_local.entity_permissions_list.each{ |entity_perm|
    if entity_perm.allow_list.include?(Permissions::FULL)
      full_users_old << [entity_perm.type, entity_perm.name]
    end
  }

  if full_users_new != full_users_old
    label = 'Full'
    Permissions.get_permission_types.each { |perm_type|
      if Permissions::FULL == perm_type['code']
        label = perm_type['label']
        break
      end
    }
    if not allowed_for_local_cluster(auth_user, Permissions::FULL)
      return [
        403,
        "Permission denied\nOnly #{SUPERUSER} and users with #{label} "\
          + "permission can grant or revoke #{label} permission."
      ]
    end
  end

  2.times {
    pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
    pcs_config.permissions_local = perm_set
    sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
    pushed, _ = Cfgsync::save_sync_new_version(
      sync_config, get_corosync_nodes_names(), $cluster_name, true
    )
    return [200, 'Permissions saved'] if pushed
  }
  return 400, 'Unable to save permissions'
end

def get_sw_versions(params, request, auth_user)
  versions = {
    "rhel" => get_rhel_version(),
    "pcs" => get_pcsd_version(),
    "pacemaker" => get_pacemaker_version(),
    "corosync" => get_corosync_version(),
  }
  return JSON.generate(versions)
end

def remote_pacemaker_node_status(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  output, stderr, retval = run_cmd(auth_user, PCS, '--', 'node', 'pacemaker-status')
  if retval != 0
    return [400, stderr]
  else
    return output
  end
end

def node_status(params, request, auth_user)
  if params[:node] and params[:node] != '' and params[:node] !=
    $cur_node_name and !params[:redirected]
    return send_request_with_token(
      auth_user,
      params[:node],
      'status?redirected=1',
      false,
      params.select { |k,_|
        [:version, :operations, :skip_auth_check].include?(k)
      }
    )
  end

  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end

  cib_dom = get_cib_dom(auth_user)
  crm_dom = get_crm_mon_dom(auth_user)

  status = get_node_status(auth_user, cib_dom)
  resources = get_resources(
    cib_dom,
    crm_dom,
    (params[:operations] and params[:operations] == '1')
  )

  node = ClusterEntity::Node.load_current_node(crm_dom)

  if params[:skip_auth_check] != '1'
    _,_,not_authorized_nodes = is_auth_against_nodes(
      auth_user,
      status[:known_nodes],
      3
    )

    if not_authorized_nodes.length > 0
      node.warning_list << {
        :message => 'Not authorized against node(s) ' +
          not_authorized_nodes.join(', '),
        :type => 'nodes_not_authorized',
        :node_list => not_authorized_nodes,
      }
    end
  end

  version = params[:version] || '1'

  if version == '2'
    status[:node] = node.to_status(version)
    resource_list = nil
    if resources
      resource_list = []
      resources.each do |r|
        resource_list << r.to_status(version)
      end
    end

    status[:resource_list] = resource_list

    return JSON.generate(status)
  end

  return [400, "Unsupported version '#{version}' of status requested"]
end

def imported_cluster_list(params, request, auth_user)
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  imported_clusters = {"cluster_list" => []}
  config.clusters.each { |cluster|
    imported_clusters["cluster_list"] << { "name": cluster.name }
  }
  return JSON.generate(imported_clusters)
end

def resource_stop(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "--", "resource", "disable", params[:resource]
  )
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

def resource_cleanup(params, request, auth_user)
  return _resource_cleanup_refresh("cleanup", params, request, auth_user)
end

def resource_refresh(params, request, auth_user)
  return _resource_cleanup_refresh("refresh", params, request, auth_user)
end

def _resource_cleanup_refresh(action, params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  cmd = ["resource", action, params[:resource]]
  flags = []
  if params[:strict] == '1'
    flags << "--strict"
  end
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate(
      {"error" => "true", "stdout" => stdout, "stderror" => stderr}
    )
  end
end

def resource_start(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "--", "resource", "enable", params[:resource]
  )
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

# Creates resource if params[:resource_id] is not set
def update_resource (params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  param_line, param_flags = _get_param_list(params)
  flags = param_flags.clone
  if not params[:resource_id]
    cmd = ["resource", "create", params[:name], params[:resource_type]]
    cmd += param_line
    if params[:resource_group] and params[:resource_group] != ""
      flags += ['--group', params[:resource_group]]
      if (
        ['before', 'after'].include?(params[:in_group_position]) and
        params[:in_group_reference_resource_id]
      )
        flags << "--#{params[:in_group_position]}"
        flags << params[:in_group_reference_resource_id]
      end
      resource_group = params[:resource_group]
    end
    if params[:resource_type] == "ocf:pacemaker:remote" and not flags.include?("--force")
      # Workaround for Error: this command is not sufficient for create remote
      # connection, use 'pcs cluster node add-remote', use --force to override.
      # It is not possible to specify meta attributes so we don't need to take
      # care of those.
      flags << "--force"
    end
    out, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end

    if params[:resource_clone] and params[:resource_clone] != ""
      name = resource_group ? resource_group : params[:name]
      run_cmd(auth_user, PCS, "--", "resource", "clone", name)
    elsif params[:resource_promotable] and params[:resource_promotable] != ""
      name = resource_group ? resource_group : params[:name]
      run_cmd(auth_user, PCS, "--", "resource", "promotable", name)
    end

    return JSON.generate({})
  end

  if param_line.length != 0
    # If it's a clone resource we strip off everything after the last ':'
    if params[:resource_clone]
      params[:resource_id].sub!(/(.*):.*/,'\1')
    end
    run_cmd(
      auth_user, PCS, *param_flags, "--", "resource", "update", params[:resource_id], *param_line
    )
  end

  if params[:resource_group]
    if params[:resource_group] == ""
      if params[:_orig_resource_group] != ""
        run_cmd(
          auth_user, PCS, "--", "resource", "group", "remove",
          params[:_orig_resource_group], params[:resource_id]
        )
      end
    else
      cmd = [
        "resource", "group", "add", params[:resource_group],
        params[:resource_id]
      ]
      flags = []
      if (
        ['before', 'after'].include?(params[:in_group_position]) and
        params[:in_group_reference_resource_id]
      )
        flags << "--#{params[:in_group_position]}"
        flags << params[:in_group_reference_resource_id]
      end
      run_cmd(auth_user, PCS, *flags, "--", *cmd)
    end
  end

  if params[:resource_clone] and params[:_orig_resource_clone] == "false"
    run_cmd(auth_user, PCS, "--", "resource", "clone", params[:resource_id])
  end
  if params[:resource_promotable] and params[:_orig_resource_promotable] == "false"
    run_cmd(auth_user, PCS, "--", "resource", "promotable", params[:resource_id])
  end

  if params[:_orig_resource_clone] == "true" and not params[:resource_clone]
    run_cmd(
      auth_user, PCS, "--", "resource", "unclone", params[:resource_id].sub(/:.*/,'')
    )
  end
  if params[:_orig_resource_promotable] == "true" and not params[:resource_promotable]
    run_cmd(
      auth_user, PCS, "--", "resource", "unclone", params[:resource_id].sub(/:.*/,'')
    )
  end

  return JSON.generate({})
end

def update_fence_device(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  $logger.info "Updating fence device"
  $logger.info params
  param_line, flags = _get_param_list(params)
  $logger.info param_line

  if not params[:resource_id]
    out, stderr, retval = run_cmd(
      auth_user,
      PCS, "--", "stonith", "create", params[:name], params[:resource_type],
      *param_line
    )
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
    return "{}"
  end

  if param_line.length != 0
    out, stderr, retval = run_cmd(
      auth_user, PCS, *flags, "--", "stonith", "update", params[:resource_id], *param_line
    )
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
  end
  return "{}"
end

def get_avail_resource_agents(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  return JSON.generate(getResourceAgents(auth_user).map{|a| [a, get_resource_agent_name_structure(a)]}.to_h)
end

def remove_resource(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  force = params['force']
  user = PCSAuth.getSuperuserAuth()
  resource_list = []
  params.each { |param,_|
    if param.start_with?('resid-')
      resource_list << param.split('resid-', 2)[1]
    end
  }

  resource_or_stonith = if params["is-stonith"] == "true" then
    "stonith"
  else
    "resource"
  end

  cmd = [resource_or_stonith, 'delete']
  flags = []
  if force
    flags << '--force'
  end
  out, err, retval = run_cmd(auth_user, PCS, *flags, '--', *cmd, *resource_list)

  if retval == 0
    return 200
  else
    $logger.info("Remove resource errors:\n"+err.join('\n'))
    return [400, err]
  end
end

def add_fence_level_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  retval, stdout, stderr = add_fence_level(
    auth_user, params["level"], params["devices"], params["node"], params["remove"]
  )
  if retval == 0
    return [200, "Successfully added fence level"]
  else
    return [400, stderr]
  end
end

def add_node_attr_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  retval = add_node_attr(
    auth_user, params["node"], params["key"], params["value"]
  )
  # retval = 2 if removing attr which doesn't exist
  if retval == 0 or retval == 2
    return [200, "Successfully added attribute to node"]
  else
    return [400, "Error adding attribute to node"]
  end
end

def add_acl_role_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
    return 403, 'Permission denied'
  end
  retval = add_acl_role(auth_user, params["name"], params["description"])
  if retval == ""
    return [200, "Successfully added ACL role"]
  else
    return [
      400,
      retval.include?("cib_replace failed") ? "Error adding ACL role" : retval
    ]
  end
end

def remove_acl_roles_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
    return 403, 'Permission denied'
  end
  errors = ""
  params.each { |name, value|
    if name.index("role-") == 0
      out, errout, retval = run_cmd(
        auth_user, PCS, "--autodelete", "--", "acl", "role", "delete", value.to_s
      )
      if retval != 0
        errors += "Unable to remove role #{value}"
        unless errout.include?("cib_replace failure")
          errors += ": #{errout.join(" ").strip()}"
        end
        errors += "\n"
        $logger.info errors
      end
    end
  }
  if errors == ""
    return [200, "Successfully removed ACL roles"]
  else
    return [400, errors]
  end
end

def add_acl_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
    return 403, 'Permission denied'
  end
  if params["item"] == "permission"
    retval = add_acl_permission(
      auth_user,
      params["role_id"], params["type"], params["xpath_id"], params["query_id"]
    )
  elsif (params["item"] == "user") or (params["item"] == "group")
    retval = add_acl_usergroup(
      auth_user, params["role_id"], params["item"], params["usergroup"]
    )
  else
    retval = "Error: Unknown adding request"
  end

  if retval == ""
    return [200, "Successfully added permission to role"]
  else
    return [
      400,
      retval.include?("cib_replace failed") ? "Error adding permission" : retval
    ]
  end
end

def remove_acl_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
    return 403, 'Permission denied'
  end
  if params["item"] == "permission"
    retval = remove_acl_permission(auth_user, params["acl_perm_id"])
  elsif params["item"] == "usergroup"
    retval = remove_acl_usergroup(
      auth_user, params["role_id"],params["usergroup_id"], params["item_type"]
    )
  else
    retval = "Error: Unknown removal request"
  end

  if retval == ""
    return [200, "Successfully removed permission from role"]
  else
    return [400, retval]
  end
end

def add_meta_attr_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  retval = add_meta_attr(
    auth_user,
    params["res_id"],
    params["key"],
    params["value"],
    params["is-stonith"] == "true"
  )
  if retval == 0
    return [200, "Successfully added meta attribute"]
  else
    return [400, "Error adding meta attribute"]
  end
end

def add_constraint_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  case params["c_type"]
  when "loc"
    retval, error = add_location_constraint(
      auth_user,
      params["res_id"], params["node_id"], params["score"], params["force"]
    )
  when "ord"
    resA = params["res_id"]
    resB = params["target_res_id"]
    actionA = params['res_action']
    actionB = params['target_action']
    if params["order"] == "before"
      resA, resB = resB, resA
      actionA, actionB = actionB, actionA
    end

    retval, error = add_order_constraint(
      auth_user,
      resA, resB, actionA, actionB, params["score"], true, params["force"]
    )
  when "col"
    resA = params["res_id"]
    resB = params["target_res_id"]
    score = params["score"]
    if params["colocation_type"] == "apart"
      if score.length > 0 and score[0] != "-"
        score = "-" + score
      elsif score == ""
        score = "-INFINITY"
      end
    end

    retval, error = add_colocation_constraint(
      auth_user, resA, resB, score, params["force"]
    )
  when "ticket"
    retval, error = add_ticket_constraint(
      auth_user,
      params["ticket"], params["res_id"], params["role"], params["loss-policy"],
      params["force"]
    )
  else
    return [400, "Unknown constraint type: #{params['c_type']}"]
  end

  if retval == 0
    return [200, "Successfully added constraint"]
  else
    return [400, "Error adding constraint: #{error}"]
  end
end

def add_constraint_rule_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if params["c_type"] == "loc"
    retval, error = add_location_constraint_rule(
      auth_user,
      params["res_id"], params["rule"], params["score"], params["force"],
    )
  else
    return [400, "Unknown constraint type: #{params["c_type"]}"]
  end

  if retval == 0
    return [200, "Successfully added constraint"]
  else
    return [400, "Error adding constraint: #{error}"]
  end
end

def add_constraint_set_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  case params["c_type"]
  when "ord"
    retval, error = add_order_set_constraint(
      auth_user, params["resources"].values, params["force"]
    )
  when "col"
    retval, error = add_colocation_set_constraint(
      auth_user, params["resources"].values, params["force"]
    )
  when "ticket"
    unless params["options"]["ticket"]
      return [400, "Error adding constraint ticket: option ticket missing"]
    end
    retval, error = add_ticket_set_constraint(
      auth_user,
      params["options"]["ticket"],
      (params["options"]["loss-policy"] or ""),
      params["resources"].values,
      params["force"],
    )
  else
    return [400, "Unknown constraint type: #{params["c_type"]}"]
  end

  if retval == 0
    return [200, "Successfully added constraint"]
  else
    return [400, "Error adding constraint: #{error}"]
  end
end

def remove_constraint_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if params[:constraint_id]
    retval = remove_constraint(auth_user, params[:constraint_id])
    if retval == 0
      return "Constraint #{params[:constraint_id]} removed"
    else
      return [400, "Error removing constraint: #{params[:constraint_id]}"]
    end
  else
    return [400,"Bad Constraint Options"]
  end
end

def remove_constraint_rule_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if params[:rule_id]
    retval = remove_constraint_rule(auth_user, params[:rule_id])
    if retval == 0
      return "Constraint rule #{params[:rule_id]} removed"
    else
      return [400, "Error removing constraint rule: #{params[:rule_id]}"]
    end
  else
    return [400, "Bad Constraint Rule Options"]
  end
end

def add_group(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  rg = params["resource_group"]
  resources = params["resources"]
  output, errout, retval = run_cmd(
    auth_user, PCS, "--", "resource", "group", "add", rg, *(resources.split(" "))
  )
  if retval == 0
    return 200
  else
    return 400, errout
  end
end

def update_cluster_settings(params, request, auth_user)
  properties = params['config']
  to_update = []
  current = getAllSettings(auth_user)

  properties.each { |prop, val|
    val.strip!
    if not current.include?(prop) and val != '' # add
      to_update << prop
    elsif current.include?(prop) and val == '' # remove
      to_update << prop
    elsif current.include?(prop) and current[prop] != val # update
      to_update << prop
    end
  }

  if to_update.count { |x| x.downcase == 'enable-acl' } > 0
    if not allowed_for_local_cluster(auth_user, Permissions::GRANT)
      return 403, 'Permission denied'
    end
  end
  if to_update.count { |x| x.downcase != 'enable-acl' } > 0
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
  end

  options = []
  options << "--force" if params["force"]

  if to_update.empty?
    $logger.info('No properties to update')
  else
    cmd_args = []
    to_update.each { |prop|
      cmd_args << "#{prop.downcase}=#{properties[prop]}"
    }
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, *options, '--', 'property', 'set', *cmd_args
    )
    if retval != 0
      return [400, stderr.join('')]
    end
  end
  return [200, "Update Successful"]
end

def cluster_destroy(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  cmd = ["cluster", "destroy"]
  flags = []
  if params[:all] == '1'
    flags << '--all'
  end
  out, errout, retval = run_cmd(auth_user, PCS, *flags, '--', *cmd)
  if retval == 0
    return [200, "Successfully destroyed cluster"]
  else
    return [400, "Error destroying cluster:\n#{out}\n#{errout}\n#{retval}\n"]
  end
end

def get_cluster_known_hosts(params, request, auth_user)
  # pcsd runs as root thus always returns hacluster's tokens
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, "Permission denied"
  end
  on, off = get_nodes()
  nodes = (on + off).uniq()
  data = {}
  get_known_hosts().each { |host_name, host_obj|
    if nodes.include?(host_name)
      data[host_name] = {
        'dest_list' => host_obj.dest_list,
        'token' => host_obj.token,
      }
    end
  }
  return [200, JSON.generate(data)]
end

def known_hosts_change(params, request, auth_user)
  # pcsd runs as root thus always works with hacluster's tokens
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, "Permission denied"
  end

  new_hosts = []
  remove_hosts = []
  begin
    data = JSON.parse(params.fetch('data_json'))
    data.fetch('known_hosts_add').each { |host_name, host_data|
      new_hosts << PcsKnownHost.new(
        host_name,
        host_data.fetch('token'),
        host_data.fetch('dest_list')
      )
    }
    data.fetch('known_hosts_remove').each { |host_name|
      remove_hosts << host_name
    }
  rescue => e
    return 400, "Incorrect format of request data: #{e}"
  end

  sync_successful, _sync_responses = Cfgsync::save_sync_new_known_hosts(
    new_hosts, remove_hosts, get_corosync_nodes_names(), $cluster_name
  )
  if sync_successful
    return [200, '']
  else
    return [400, 'Cannot update known-hosts file.']
  end
end

def resource_promotable(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end
  _, stderr, retval = run_cmd(
    auth_user, PCS, '--', 'resource', 'promotable', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to create promotable resource from ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_change_group(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  if params[:resource_id].nil? or params[:group_id].nil?
    return [400, 'resource_id and group_id have to be specified.']
  end
  if params[:group_id].empty?
    if params[:old_group_id]
      _, stderr, retval = run_cmd(
        auth_user, PCS, '--', 'resource', 'group', 'remove', params[:old_group_id],
        params[:resource_id]
      )
      if retval != 0
        return [400, "Unable to remove resource '#{params[:resource_id]}' " +
          "from group '#{params[:old_group_id]}': #{stderr.join('')}"
        ]
      end
    end
    return 200
  end
  cmd = [
    'resource', 'group', 'add', params[:group_id], params[:resource_id]
  ]
  flags = []
  if (
  ['before', 'after'].include?(params[:in_group_position]) and
    params[:in_group_reference_resource_id]
  )
    flags << "--#{params[:in_group_position]}"
    flags << params[:in_group_reference_resource_id]
  end
  _, stderr, retval = run_cmd(auth_user, PCS, *flags, '--', *cmd)
  if retval != 0
    return [400, "Unable to add resource '#{params[:resource_id]}' to " +
      "group '#{params[:group_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_ungroup(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:group_id]
    return [400, 'group_id has to be specified.']
  end

  _, stderr, retval = run_cmd(
    auth_user, PCS, '--', 'resource', 'ungroup', params[:group_id]
  )
  if retval != 0
    return [400, 'Unable to ungroup group ' +
      "'#{params[:group_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_clone(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end

  _, stderr, retval = run_cmd(
    auth_user, PCS, '--', 'resource', 'clone', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to create clone resource from ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_unclone(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end

  _, stderr, retval = run_cmd(
    auth_user, PCS, '--', 'resource', 'unclone', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to unclone ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def set_resource_utilization(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:resource_id] and params[:name]
    return 400, 'resource_id and name are required'
  end

  res_id = params[:resource_id]
  name = params[:name]
  value = params[:value] || ''

  _, stderr, retval = run_cmd(
    auth_user, PCS, '--', 'resource', 'utilization', res_id, "#{name}=#{value}"
  )

  if retval != 0
    return [400, "Unable to set utilization '#{name}=#{value}' for " +
      "resource '#{res_id}': #{stderr.join('')}"
    ]
  end
  return 200
end

def set_node_utilization(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:node] and params[:name]
    return 400, 'node and name are required'
  end

  node = params[:node]
  name = params[:name]
  value = params[:value] || ''

  _, stderr, retval = run_cmd(
    auth_user, PCS, '--', 'node', 'utilization', node, "#{name}=#{value}"
  )

  if retval != 0
    return [400, "Unable to set utilization '#{name}=#{value}' for node " +
      "'#{node}': #{stderr.join('')}"
    ]
  end
  return 200
end

def get_cluster_properties_definition(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  stdout, _, retval = run_cmd(
    auth_user, PCS, '--', 'property', 'get_cluster_properties_definition'
  )
  if retval == 0
    return [200, stdout]
  end
  return [400, '{}']
end

def check_sbd(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  sbd_name = get_sbd_service_name()
  service_checker = ServiceChecker.new(
    [sbd_name], installed: true, enabled: true, running: true
  )
  out = {
    :sbd => service_checker.get_info(sbd_name),
  }
  watchdog = param[:watchdog]
  if not watchdog.to_s.empty?
    stdout, stderr, ret_val = run_cmd(
      auth_user, PCS, '--', 'stonith', 'sbd', 'watchdog', 'list_json'
    )
    if ret_val != 0
      return [400, "Unable to get list of watchdogs: #{stderr.join("\n")}"]
    end
    begin
      available_watchdogs = JSON.parse(stdout.join("\n"))
      exists = available_watchdogs.include?(watchdog)
      out[:watchdog] = {
        :path => watchdog,
        :exist => exists,
        :is_supported => (
          # this method is not reliable so all watchdog devices listed by SBD
          # will be listed as supported for now
          # exists and available_watchdogs[watchdog]['caution'] == nil
          exists
        ),
      }
    rescue JSON::ParserError
      return [400, "Unable to get list of watchdogs: unable to parse JSON"]
    end
  end
  begin
    device_list = JSON.parse(param[:device_list])
    if device_list and device_list.respond_to?('each')
      out[:device_list] = []
      device_list.each { |device|
        out[:device_list] << {
          :path => device,
          :exist => File.exist?(device),
          :block_device => File.blockdev?(device),
        }
      }
    end
  rescue JSON::ParserError
    return [400, 'Invalid input data format']
  end
  return [200, JSON.generate(out)]
end

def set_sbd_config(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  config = param[:config]
  unless config
    return [400, 'Parameter "config" required']
  end

  file = nil
  begin
    file = File.open(SBD_CONFIG, 'w')
    file.flock(File::LOCK_EX)
    file.write(config)
  rescue => e
    return pcsd_error("Unable to save SBD configuration: #{e}")
  ensure
    if file
      file.flock(File::LOCK_UN)
      file.close()
    end
  end
  return pcsd_success('SBD configuration saved.')
end

def get_sbd_config(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  out = []
  file = nil
  begin
    file = File.open(SBD_CONFIG, 'r')
    file.flock(File::LOCK_SH)
    out = file.readlines()
  rescue => e
    return pcsd_error("Unable to get SBD configuration: #{e}")
  ensure
    if file
      file.flock(File::LOCK_UN)
      file.close()
    end
  end
  return [200, out.join('')]
end

def sbd_disable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if disable_service(get_sbd_service_name())
    return pcsd_success('SBD disabled')
  else
    return pcsd_error("Disabling SBD failed")
  end
end

def sbd_enable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if enable_service(get_sbd_service_name())
    return pcsd_success('SBD enabled')
  else
    return pcsd_error("Enabling SBD failed")
  end
end

# Original name of the cluster property is 'stonith-watchdog-timeout'. In
# pacemaker feature set 3.20.5 (at the time of writing this comment it hasn't
# been released in any pacemaker version yet), it was renamed to
# 'fencing-watchdog-timeout', while the original property is still kept as
# deprecated.
#
# Analyzing the pacemaker source code revealed how they are processed:
# - first, the new property is looked for
# - if it's found, its value is used and the deprecated property is ignored
# - if it's not found or has no value, the deprecated property is used
# The safest and easiest approach is to set or unset both properties:
# - old pacemaker ignores the new property, no issues are caused by setting it
# - both properties are set to the same value for the new pacemaker preventing
#   inconsistencies
#
# Alternatively, pcs code could detect if it runs with the new pacemaker. If it
# does, it would set the new property and remove the deprecated one. If it runs
# with the old pacemaker, only the original property would be worked with.
#
# Once the deprecated property is removed from pacemaker, it should be removed
# from pcs as well.

def remove_stonith_watchdog_timeout(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  _STONITH_WATCHDOG_TIMEOUT_PROPERTIES = [
      "stonith-watchdog-timeout",
      "fencing-watchdog-timeout",
  ]
  error = false

  # see comment above
  for prop_name in _STONITH_WATCHDOG_TIMEOUT_PROPERTIES
    if set_cluster_prop_force(auth_user, prop_name, '')
      $logger.info("Cluster property '#{prop_name}' removed")
    else
      $logger.info("Failed to remove cluster property '#{prop_name}'")
      error = true
    end
  end

  if error
    return [400, 'Failed to remove cluster property fencing-watchdog-timeout / stonith-watchdog-timeout']
  else
    return [200, 'OK']
  end
end

def set_stonith_watchdog_timeout_to_zero(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  _STONITH_WATCHDOG_TIMEOUT_PROPERTIES = [
      "stonith-watchdog-timeout",
      "fencing-watchdog-timeout",
  ]
  error = false

  # see comment above
  for prop_name in _STONITH_WATCHDOG_TIMEOUT_PROPERTIES
    if set_cluster_prop_force(auth_user, prop_name, '0')
      $logger.info("Cluster property '#{prop_name}' set to '0'")
    else
      $logger.info("Failed to set cluster property '#{prop_name}' to '0'")
      error = true
    end
  end

  if error
    return [400, 'Failed to set cluster property fencing-watchdog-timeout / stonith-watchdog-timeout to zero']
  else
    return [200, 'OK']
  end
end

def qdevice_client_disable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if disable_service('corosync-qdevice')
    return pcsd_success('corosync-qdevice disabled')
  else
    return pcsd_error("Disabling corosync-qdevice failed")
  end
end

def qdevice_client_enable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if not ServiceChecker.new(['corosync'], enabled: true).is_enabled?('corosync')
    return pcsd_success('corosync is not enabled, skipping')
  elsif enable_service('corosync-qdevice')
    return pcsd_success('corosync-qdevice enabled')
  else
    return pcsd_error("Enabling corosync-qdevice failed")
  end
end

def qdevice_client_stop(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if stop_service('corosync-qdevice')
    return pcsd_success('corosync-qdevice stopped')
  else
    return pcsd_error("Stopping corosync-qdevice failed")
  end
end

def qdevice_client_start(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if not ServiceChecker.new(['corosync'], running: true).is_running?('corosync')
    return pcsd_success('corosync is not running, skipping')
  elsif start_service('corosync-qdevice')
    return pcsd_success('corosync-qdevice started')
  else
    return pcsd_error("Starting corosync-qdevice failed")
  end
end

def booth_set_config(params, request, auth_user)
  begin
    check_permissions(auth_user, Permissions::WRITE)
    data = check_request_data_for_json(params, auth_user)

    if not File.directory?(BOOTH_CONFIG_DIR)
      raise "Configuration directory for booth '/etc/booth' is missing. Is booth installed?"
    end

    PcsdExchangeFormat::validate_item_map_is_Hash('files', data)
    PcsdExchangeFormat::validate_item_is_Hash('file', :config, data[:config])
    if data[:authfile]
      PcsdExchangeFormat::validate_item_is_Hash('file', :config, data[:config])
    end

    action_results = {
      :config => PcsdExchangeFormat::run_action(
        PcsdFile::TYPES,
        "file",
        :config,
        data[:config].merge({
          :type => "booth_config",
          :rewrite_existing => true
        })
      )
    }

    if data[:authfile]
      action_results[:authfile] = PcsdExchangeFormat::run_action(
        PcsdFile::TYPES,
        "file",
        :authfile,
        data[:authfile].merge({
          :type => "booth_authfile",
          :rewrite_existing => true
        })
      )
    end

    success_codes = [:written, :rewritten]
    failed_results = action_results.select{|key, result|
      !success_codes.include?(result[:code])
    }

    if failed_results.empty?
      return pcsd_success('Booth configuration saved.')
    end

    return pcsd_error("Unable to save booth configuration: #{
      failed_results.reduce([]){|memo, (key, result)|
        memo << "#{key}: #{result[:code]}: #{result[:message]}"
      }.join(";")
    }")
  rescue PcsdRequestException => e
    return e.code, e.message
  rescue PcsdExchangeFormat::Error => e
    return 400, "Invalid input data format: #{e.message}"
  rescue => e
    return pcsd_error("Unable to save booth configuration: #{e.message}")
  end
end

def booth_save_files(params, request, auth_user)
  begin
    check_permissions(auth_user, Permissions::WRITE)
    data = check_request_data_for_json(params, auth_user)
    rewrite_existing = (
      params.include?('rewrite_existing') || params.include?(:rewrite_existing)
    )

    action_results = Hash[data.each_with_index.map{|file, i|
      PcsdExchangeFormat::validate_item_is_Hash('file', i, file)
      [
        i,
        PcsdExchangeFormat::run_action(
          PcsdFile::TYPES,
          'file',
          i,
          file.merge({
            :rewrite_existing => rewrite_existing,
            :type => file[:is_authfile] ? "booth_authfile" : "booth_config"
          })
        )
      ]
    }]

    results = {:existing => [], :saved => [], :failed => {}}

    code_result_map = {
      :written => :saved,
      :rewritten => :existing,
      :same_content => :existing,
      :conflict => :existing,
    }

    action_results.each{|i, result|
      name = data[i][:name]

      if code_result_map.has_key?(result[:code])
        results[code_result_map[result[:code]]] << name

      elsif result[:code] == :unexpected
        results[:failed][name] = result[:message]

      else
        results[:failed][name] = "Unknown process file result:"+
          "code: '#{result[:code]}': message: '#{result[:message]}'"

      end
    }

    return [200, JSON.generate(results)]
  rescue PcsdRequestException => e
    return e.code, e.message
  rescue PcsdExchangeFormat::Error => e
    return 400, "Invalid input data format: #{e.message}"
  end
end

def booth_get_config(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  name = params[:name]
  if name
    config_file_name = "#{name}.conf"
  else
    config_file_name = 'booth.conf'
  end
  if config_file_name.include?('/')
    return [400, 'Invalid name of booth configuration']
  end
  begin
    config_data = read_booth_config(config_file_name)
    unless config_data
      return [400, "Config doesn't exist"]
    end
    authfile_name = nil
    authfile_data = nil
    authfile_path = get_authfile_from_booth_config(config_data)
    if authfile_path
      if File.dirname(authfile_path) != BOOTH_CONFIG_DIR
        return [
          400, "Authfile of specified config is not in '#{BOOTH_CONFIG_DIR}'"
        ]
      end
      authfile_name = File.basename(authfile_path)
      authfile_data = read_booth_authfile(authfile_name)
    end
    return [200, JSON.generate({
      :config => {
        :name => config_file_name,
        :data => config_data
      },
      :authfile => {
        :name => authfile_name,
        :data => authfile_data
      }
    })]
  rescue => e
    return [400, "Unable to read booth config/key file: #{e.message}"]
  end
end

def put_file(params, request, auth_user)
  begin
    check_permissions(auth_user, Permissions::WRITE)

    files = check_request_data_for_json(params, auth_user)
    PcsdExchangeFormat::validate_item_map_is_Hash('files', files)

    operation_types = files.map{ |id, data| data[:type] }.uniq
    if operation_types & ['corosync_conf']
      check_permissions(auth_user, Permissions::FULL)
    end

    return pcsd_success(
      JSON.generate({"files" => Hash[files.map{|id, file_data|
        PcsdExchangeFormat::validate_item_is_Hash('file', id, file_data)
        [id, PcsdExchangeFormat::run_action(
          PcsdFile::TYPES, 'file', id, file_data
        )]
      }]})
    )
  rescue PcsdRequestException => e
    return e.code, e.message
  rescue PcsdExchangeFormat::Error => e
    return 400, "Invalid input data format: #{e.message}"
  end
end

def remove_file(params, request, auth_user)
  begin
    check_permissions(auth_user, Permissions::WRITE)

    files = check_request_data_for_json(params, auth_user)
    PcsdExchangeFormat::validate_item_map_is_Hash('files', files)

    return pcsd_success(
      JSON.generate({"files" => Hash[files.map{|id, file_data|
        PcsdExchangeFormat::validate_item_is_Hash('file', id, file_data)
        [id, PcsdExchangeFormat::run_action(
          PcsdRemoveFile::TYPES, 'file', id, file_data
        )]
      }]})
    )
  rescue PcsdRequestException => e
    return e.code, e.message
  rescue PcsdExchangeFormat::Error => e
    return 400, "Invalid input data format: #{e.message}"
  end
end


def manage_services(params, request, auth_user)
  begin
    check_permissions(auth_user, Permissions::WRITE)

    actions = check_request_data_for_json(params, auth_user)
    PcsdExchangeFormat::validate_item_map_is_Hash('actions', actions)

    return pcsd_success(
      JSON.generate({"actions" => Hash[actions.map{|id, action_data|
        PcsdExchangeFormat::validate_item_is_Hash("action", id, action_data)
        [id, PcsdExchangeFormat::run_action(
          PcsdActionCommand::TYPES, "action", id, action_data
        )]
      }]})
    )
  rescue PcsdRequestException => e
    return e.code, e.message
  rescue PcsdExchangeFormat::Error => e
    return 400, "Invalid input data format: #{e.message}"
  end
end

def pcsd_success(msg)
  $logger.info(msg)
  return [200, msg]
end

def pcsd_error(msg)
  $logger.error(msg)
  return [400, msg]
end

class PcsdRequestException < StandardError
  attr_accessor :code

  def initialize(message = nil, code = 400)
    super(message)
    self.code = code
  end
end

def check_permissions(auth_user, permission)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    raise PcsdRequestException.new('Permission denied', 403)
  end
end

def check_request_data_for_json(params, auth_user)
  unless params[:data_json]
    raise PcsdRequestException.new("Missing required parameter 'data_json'")
  end
  begin
    return JSON.parse(params[:data_json], {:symbolize_names => true})
  rescue JSON::ParserError
    raise PcsdRequestException.new('Invalid input data format')
  end
end

def check_host(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  service_list = [
    :pacemaker, :pacemaker_remote, :corosync, :pcsd, :sbd, :qdevice, :booth
  ]
  service_version_getter = {
    :pacemaker => method(:get_pacemaker_version),
    :corosync => method(:get_corosync_version),
    :pcsd => method(:get_pcsd_version),
    # TODO: add version getters for all services
  }
  output = {
    :services => {},
    :cluster_configuration_exists => (
      File.exist?(Cfgsync::CorosyncConf.file_path) or File.exist?(CIB_PATH)
    )
  }

  service_checker = ServiceChecker.new(
    service_list.map {|item| item.to_s},
    installed: true,
    enabled: true,
    running: true,
  )
  service_list.each do |service|
    output[:services][service] = service_checker.get_info(service.to_s).merge(
      {:version => nil}
    )
  end
  service_version_getter.each do |service, version_getter|
    version = version_getter.call()
    output[:services][service][:version] = (
      version == nil ? version : version.join('.')
    )
  end
  return [200, JSON.generate(output)]
end

def reload_corosync_conf(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  if ServiceChecker.new(['corosync'], running: true).is_running?('corosync')
    output, stderr, retval = run_cmd(
      auth_user, File.join(COROSYNC_BINARIES, "corosync-cfgtool"), "-R"
    )
    if retval != 0
      msg_lines = output + stderr
      if not msg_lines.empty? and msg_lines[0].strip() == 'Reloading corosync.conf...'
        msg_lines.delete_at(0)
      end
      result = PcsdExchangeFormat::result(
        :failed,
        "Unable to reload corosync configuration: #{msg_lines.join("\n").strip()}"
      )
    else
      result = PcsdExchangeFormat::result(:reloaded)
    end
  else
    result = PcsdExchangeFormat::result(:not_running)
  end

  return JSON.generate(result)
end

def remove_nodes_from_cib(params, request, auth_user)
  begin
    check_permissions(auth_user, Permissions::WRITE)
    data = check_request_data_for_json(params, auth_user)
    PcsdExchangeFormat::validate_item_map_is_Hash("data_json", data)
    PcsdExchangeFormat::validate_item_is_Array("node_list", data[:node_list])

    stdout, stderr, retval = run_cmd(
      auth_user, PCS, "--", "cluster", "remove_nodes_from_cib", *data[:node_list]
    )
    if retval == 0
      result = PcsdExchangeFormat::result(:success)
    else
      result = PcsdExchangeFormat::result(
        :failed, (stdout + stderr).join("\n").strip()
      )
    end
    return JSON.generate(result)
  rescue PcsdRequestException => e
    return e.code, e.message
  rescue PcsdExchangeFormat::Error => e
    return 400, "Invalid input data format: #{e.message}"
  end
end
