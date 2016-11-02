require 'json'
require 'uri'
require 'open4'
require 'set'
require 'timeout'
require 'rexml/document'
require 'base64'
require 'tempfile'

require 'pcs.rb'
require 'resource.rb'
require 'config.rb'
require 'cfgsync.rb'
require 'cluster_entity.rb'
require 'permissions.rb'
require 'auth.rb'

# Commands for remote access
def remote(params, request, auth_user)
  remote_cmd_without_pacemaker = {
      :status => method(:node_status),
      :status_all => method(:status_all),
      :cluster_status => method(:cluster_status_remote),
      :auth => method(:auth),
      :check_auth => method(:check_auth),
      :setup_cluster => method(:setup_cluster),
      :create_cluster => method(:create_cluster),
      :get_quorum_info => method(:get_quorum_info),
      :get_cib => method(:get_cib),
      :get_corosync_conf => method(:get_corosync_conf_remote),
      :set_cluster_conf => method(:set_cluster_conf),
      :set_corosync_conf => method(:set_corosync_conf),
      :get_sync_capabilities => method(:get_sync_capabilities),
      :set_sync_options => method(:set_sync_options),
      :get_configs => method(:get_configs),
      :set_configs => method(:set_configs),
      :set_certs => method(:set_certs),
      :pcsd_restart => method(:remote_pcsd_restart),
      :get_permissions => method(:get_permissions_remote),
      :set_permissions => method(:set_permissions_remote),
      :cluster_start => method(:cluster_start),
      :cluster_stop => method(:cluster_stop),
      :config_backup => method(:config_backup),
      :config_restore => method(:config_restore),
      :node_restart => method(:node_restart),
      :node_standby => method(:node_standby),
      :node_unstandby => method(:node_unstandby),
      :cluster_enable => method(:cluster_enable),
      :cluster_disable => method(:cluster_disable),
      :resource_status => method(:resource_status),
      :get_sw_versions => method(:get_sw_versions),
      :node_available => method(:remote_node_available),
      :add_node_all => lambda { |params_, request_, auth_user_|
        remote_add_node(params_, request_, auth_user_, true)
      },
      :add_node => lambda { |params_, request_, auth_user_|
        remote_add_node(params_, request_, auth_user_, false)
      },
      :remove_nodes => method(:remote_remove_nodes),
      :remove_node => method(:remote_remove_node),
      :cluster_destroy => method(:cluster_destroy),
      :get_wizard => method(:get_wizard),
      :wizard_submit => method(:wizard_submit),
      :get_tokens => method(:get_tokens),
      :get_cluster_tokens => method(:get_cluster_tokens),
      :save_tokens => method(:save_tokens),
      :get_cluster_properties_definition => method(:get_cluster_properties_definition),
      :check_sbd => method(:check_sbd),
      :set_sbd_config => method(:set_sbd_config),
      :get_sbd_config => method(:get_sbd_config),
      :sbd_disable => method(:sbd_disable),
      :sbd_enable => method(:sbd_enable),
      :remove_stonith_watchdog_timeout=> method(:remove_stonith_watchdog_timeout),
      :set_stonith_watchdog_timeout_to_zero => method(:set_stonith_watchdog_timeout_to_zero),
      :remote_enable_sbd => method(:remote_enable_sbd),
      :remote_disable_sbd => method(:remote_disable_sbd),
      :qdevice_net_get_ca_certificate => method(:qdevice_net_get_ca_certificate),
      :qdevice_net_sign_node_certificate => method(:qdevice_net_sign_node_certificate),
      :qdevice_net_client_init_certificate_storage => method(:qdevice_net_client_init_certificate_storage),
      :qdevice_net_client_import_certificate => method(:qdevice_net_client_import_certificate),
      :qdevice_net_client_destroy => method(:qdevice_net_client_destroy),
      :qdevice_client_enable => method(:qdevice_client_enable),
      :qdevice_client_disable => method(:qdevice_client_disable),
      :qdevice_client_start => method(:qdevice_client_start),
      :qdevice_client_stop => method(:qdevice_client_stop),
      :booth_set_config => method(:booth_set_config),
      :booth_save_files => method(:booth_save_files),
      :booth_get_config => method(:booth_get_config),

  }
  remote_cmd_with_pacemaker = {
      :pacemaker_node_status => method(:remote_pacemaker_node_status),
      :resource_start => method(:resource_start),
      :resource_stop => method(:resource_stop),
      :resource_cleanup => method(:resource_cleanup),
      :update_resource => method(:update_resource),
      :update_fence_device => method(:update_fence_device),
      :get_avail_resource_agents => method(:get_avail_resource_agents),
      :get_avail_fence_agents => method(:get_avail_fence_agents),
      :remove_resource => method(:remove_resource),
      :add_constraint_remote => method(:add_constraint_remote),
      :add_constraint_rule_remote => method(:add_constraint_rule_remote),
      :add_constraint_set_remote => method(:add_constraint_set_remote),
      :remove_constraint_remote => method(:remove_constraint_remote),
      :remove_constraint_rule_remote => method(:remove_constraint_rule_remote),
      :add_meta_attr_remote => method(:add_meta_attr_remote),
      :add_group => method(:add_group),
      :update_cluster_settings => method(:update_cluster_settings),
      :add_fence_level_remote => method(:add_fence_level_remote),
      :add_node_attr_remote => method(:add_node_attr_remote),
      :add_acl_role => method(:add_acl_role_remote),
      :remove_acl_roles => method(:remove_acl_roles_remote),
      :add_acl => method(:add_acl_remote),
      :remove_acl => method(:remove_acl_remote),
      :resource_change_group => method(:resource_change_group),
      :resource_master => method(:resource_master),
      :resource_clone => method(:resource_clone),
      :resource_unclone => method(:resource_unclone),
      :resource_ungroup => method(:resource_ungroup),
      :set_resource_utilization => method(:set_resource_utilization),
      :set_node_utilization => method(:set_node_utilization),
      :get_resource_agent_metadata => method(:get_resource_agent_metadata),
      :get_fence_agent_metadata => method(:get_fence_agent_metadata),
      :manage_resource => method(:manage_resource),
      :unmanage_resource => method(:unmanage_resource),
      :create_alert => method(:create_alert),
      :update_alert => method(:update_alert),
      :create_recipient => method(:create_recipient),
      :update_recipient => method(:update_recipient),
      :remove_alerts_and_recipients => method("remove_alerts_and_recipients"),
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

# provides remote cluster status to a local gui
def cluster_status_gui(auth_user, cluster_name, dont_update_config=false)
  cluster_nodes = get_cluster_nodes(cluster_name)
  status = cluster_status_from_nodes(auth_user, cluster_nodes, cluster_name)
  unless status
    return 403, 'Permission denied'
  end

  new_cluster_nodes = []
  new_cluster_nodes += status[:corosync_offline] if status[:corosync_offline]
  new_cluster_nodes += status[:corosync_online] if status[:corosync_online]
  new_cluster_nodes += status[:pacemaker_offline] if status[:pacemaker_offline]
  new_cluster_nodes += status[:pacemaker_online] if status[:pacemaker_online]
  new_cluster_nodes.uniq!

  if new_cluster_nodes.length > 0
    config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
    if !(dont_update_config or config.cluster_nodes_equal?(cluster_name, new_cluster_nodes))
      old_cluster_nodes = config.get_nodes(cluster_name)
      $logger.info("Updating node list for: #{cluster_name} #{old_cluster_nodes}->#{new_cluster_nodes}")
      config.update_cluster(cluster_name, new_cluster_nodes)
      sync_config = Cfgsync::PcsdSettings.from_text(config.text())
      # on version conflict just go on, config will be corrected eventually
      # by displaying the cluster in the web UI
      Cfgsync::save_sync_new_version(
          sync_config, get_corosync_nodes(), $cluster_name, true
      )
      return cluster_status_gui(auth_user, cluster_name, true)
    end
  end
  return JSON.generate(status)
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
    $logger.info "Starting Daemons"
    output, stderr, retval = run_cmd(auth_user, PCS, 'cluster', 'start')
    $logger.debug output
    if retval != 0
      return [400, (output + stderr).join]
    else
      return output
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
    $logger.info "Stopping Daemons"
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, "cluster", "stop", *options
    )
    if retval != 0
      return [400, stderr.join]
    else
      return stdout.join
    end
  end
end

def config_backup(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'config_backup', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::FULL)
      return 403, 'Permission denied'
    end
    $logger.info "Backup node configuration"
    stdout, stderr, retval = run_cmd(auth_user, PCS, "config", "backup")
    if retval == 0
        $logger.info "Backup successful"
        return [200, stdout]
    end
    $logger.info "Error during backup: #{stderr.join(' ').strip()}"
    return [400, "Unable to backup node: #{stderr.join(' ')}"]
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
      out = ""
      errout = ""
      status = Open4::popen4(PCS, "config", "restore", "--local") { |pid, stdin, stdout, stderr|
        stdin.print(params[:tarball])
        stdin.close()
        out = stdout.readlines()
        errout = stderr.readlines()
      }
      retval = status.exitstatus
      if retval == 0
        $logger.info "Restore successful"
        return "Succeeded"
      else
        $logger.info "Error during restore: #{errout.join(' ').strip()}"
        return errout.length > 0 ? errout.join(' ').strip() : "Error"
      end
    else
      $logger.info "Error: Invalid tarball"
      return "Error: Invalid tarball"
    end
  end
end

def node_restart(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'node_restart', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    $logger.info "Restarting Node"
    output =  `/sbin/reboot`
    $logger.debug output
    return output
  end
end

def node_standby(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'node_standby', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    $logger.info "Standby Node"
    stdout, stderr, retval = run_cmd(auth_user, PCS, "node", "standby")
    return stdout
  end
end

def node_unstandby(params, request, auth_user)
  if params[:name]
    code, response = send_request_with_token(
      auth_user, params[:name], 'node_unstandby', true
    )
  else
    if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
      return 403, 'Permission denied'
    end
    $logger.info "Unstandby Node"
    stdout, stderr, retval = run_cmd(auth_user, PCS, "node", "unstandby")
    return stdout
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
    success = enable_cluster(auth_user)
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
    success = disable_cluster(auth_user)
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
  if ISRHEL6
    stdout_status, stderr_status, retval = run_cmd(
      PCSAuth.getSuperuserAuth(), CMAN_TOOL, "status"
    )
    stdout_nodes, stderr_nodes, retval = run_cmd(
      PCSAuth.getSuperuserAuth(),
      CMAN_TOOL, "nodes", "-F", "id,type,votes,name"
    )
    if stderr_status.length > 0
      return stderr_status.join
    elsif stderr_nodes.length > 0
      return stderr_nodes.join
    else
      return stdout_status.join + "\n---Votes---\n" + stdout_nodes.join
    end
  else
    stdout, stderr, retval = run_cmd(
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
end

def get_cib(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  cib, stderr, retval = run_cmd(auth_user, CIBADMIN, "-Ql")
  if retval != 0
    if not pacemaker_running?
      return [400, '{"pacemaker_not_running":true}']
    end
    return [500, "Unable to get CIB: " + cib.to_s + stderr.to_s]
  else
    return [200, cib]
  end
end

def get_corosync_conf_remote(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  return get_corosync_conf()
end

def set_cluster_conf(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  if params[:cluster_conf] != nil and params[:cluster_conf].strip != ""
    Cfgsync::ClusterConf.backup()
    Cfgsync::ClusterConf.from_text(params[:cluster_conf]).save()
    return 200, 'Updated cluster.conf...'
  else
    $logger.info "Invalid cluster.conf file"
    return 400, 'Failed to update cluster.conf...'
  end
end

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
    if Cfgsync::ConfigSyncControl.sync_thread_disable($semaphore_cfgsync)
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
    if Cfgsync::ConfigSyncControl.sync_thread_pause(
        $semaphore_cfgsync, params['sync_thread_pause']
      )
      return 'sync thread paused'
    else
      return [400, 'sync thread pause error']
    end
  end

  return [400, 'Exactly one option has to be specified']
end

def get_configs(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  if not $cluster_name or $cluster_name.empty?
    return JSON.generate({'status' => 'not_in_cluster'})
  end
  if params[:cluster_name] != $cluster_name
    return JSON.generate({'status' => 'wrong_cluster_name'})
  end
  out = {
    'status' => 'ok',
    'cluster_name' => $cluster_name,
    'configs' => {},
  }
  Cfgsync::get_configs_local.each { |name, cfg|
    out['configs'][cfg.class.name] = {
      'type' => 'file',
      'text' => cfg.text,
    }
  }
  return JSON.generate(out)
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

  $semaphore_cfgsync.synchronize {
    force = configs_json['force']
    remote_configs, unknown_cfg_names = Cfgsync::sync_msg_to_configs(configs_json)
    local_configs = Cfgsync::get_configs_local

    result = {}
    unknown_cfg_names.each { |name| result[name] = 'not_supported' }
    remote_configs.each { |name, remote_cfg|
      begin
        # Save a remote config if it is a newer version than local. If the config
        # is not present on a local node, the node is beeing added to a cluster,
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
  }
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
      return [400, ssl_errors.join]
    end
    begin
      write_file_lock(CRT_FILE, 0700, ssl_cert)
      write_file_lock(KEY_FILE, 0700, ssl_key)
    rescue => e
      # clean the files if we ended in the middle
      # the files will be regenerated on next pcsd start
      FileUtils.rm(CRT_FILE, {:force => true})
      FileUtils.rm(KEY_FILE, {:force => true})
      return [400, "cannot save ssl files: #{e}"]
    end
  end

  if params['cookie_secret']
    cookie_secret = params['cookie_secret'].strip
    if !cookie_secret.empty?
      begin
        write_file_lock(COOKIE_FILE, 0700, cookie_secret)
      rescue => e
        return [400, "cannot save cookie secret: #{e}"]
      end
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
      sync_config, get_corosync_nodes(), $cluster_name, true
    )
    return [200, 'Permissions saved'] if pushed
  }
  return 400, 'Unable to save permissions'
end

def remote_pcsd_restart(params, request, auth_user)
  pcsd_restart()
  return [200, 'success']
end

def get_sw_versions(params, request, auth_user)
  versions = {
    "rhel" => get_rhel_version(),
    "pcs" => get_pcsd_version(),
    "pacemaker" => get_pacemaker_version(),
    "corosync" => get_corosync_version(),
    "cman" => get_cman_version(),
  }
  return JSON.generate(versions)
end

def remote_node_available(params, request, auth_user)
  if (
    (not ISRHEL6 and File.exist?(Cfgsync::CorosyncConf.file_path)) or
    (ISRHEL6 and File.exist?(Cfgsync::ClusterConf.file_path)) or
    File.exist?("/var/lib/pacemaker/cib/cib.xml")
  )
    return JSON.generate({:node_available => false})
  end
  if pacemaker_remote_running?()
    return JSON.generate({
      :node_available => false,
      :pacemaker_remote => true,
    })
  end
  return JSON.generate({:node_available => true})
end

def remote_add_node(params, request, auth_user, all=false)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  auto_start = false
  if params[:auto_start] and params[:auto_start] == "1"
    auto_start = true
  end

  if params[:new_nodename] != nil
    node = params[:new_nodename]
    if params[:new_ring1addr] != nil
      node += ',' + params[:new_ring1addr]
    end
    retval, output = add_node(
      auth_user, node, all, auto_start, params[:watchdog]
    )
  end

  if retval == 0
    return [200, JSON.generate([retval, get_corosync_conf()])]
  end

  return [400,output]
end

def remote_remove_nodes(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  count = 0
  out = ""
  node_list = []
  options = []
  while params["nodename-" + count.to_s]
    node_list << params["nodename-" + count.to_s]
    count = count + 1
  end
  options << "--force" if params["force"]

  cur_node = get_current_node_name()
  if i = node_list.index(cur_node)
    node_list.push(node_list.delete_at(i))
  end

  # stop the nodes at once in order to:
  # - prevent resources from moving pointlessly
  # - get possible quorum loss warning
  stop_params = node_list + options
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "cluster", "stop", *stop_params
  )
  if retval != 0 and not params['force']
    # If forced, keep going even if unable to stop all nodes (they may be dead).
    # Add info this error is forceable if pcs did not do it (e.g. when unable
    # to connect to some nodes).
    message = stderr.join
    if not message.include?(', use --force to override')
      message += ', use --force to override'
    end
    return [400, message]
  end

  node_list.each {|node|
    retval, output = remove_node(auth_user, node, true)
    out = out + output.join("\n")
  }
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  if config.get_nodes($cluster_name) == nil or config.get_nodes($cluster_name).length == 0
    return [200,"No More Nodes"]
  end
  if retval != 0
    return [400, out]
  else
    return [200, out]
  end
end

def remote_remove_node(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  if params[:remove_nodename] != nil
    retval, output = remove_node(auth_user, params[:remove_nodename])
  else
    return 400, "No nodename specified"
  end

  if retval == 0
    return JSON.generate([retval, get_corosync_conf()])
  end

  return JSON.generate([retval,output])
end

def setup_cluster(params, request, auth_user)
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied'
  end
  $logger.info("Setting up cluster: " + params.inspect)
  nodes_rrp = params[:nodes].split(';')
  options = []
  myoptions = JSON.parse(params[:options])
  transport_udp = false
  options_udp = []
  myoptions.each { |o,v|
    if ["wait_for_all", "last_man_standing", "auto_tie_breaker"].include?(o)
      options << "--" + o + "=1"
    end

    options << "--" + o + "=" + v if [
        "token", "token_coefficient", "join", "consensus", "miss_count_const",
        "fail_recv_const", "last_man_standing_window",
      ].include?(o)

    if o == "transport" and v == "udp"
      options << "--transport=udp"
      transport_udp = true
    end
    if o == "transport" and v == "udpu"
      options << "--transport=udpu"
      transport_udp = false
    end

    if ["addr0", "addr1", "mcast0", "mcast1", "mcastport0", "mcastport1", "ttl0", "ttl1"].include?(o)
      options_udp << "--" + o + "=" + v
    end

    if ["broadcast0", "broadcast1"].include?(o)
      options_udp << "--" + o
    end

    if o == "ipv6"
      options << "--ipv6"
    end
  }
  if transport_udp
    nodes = []
    nodes_rrp.each { |node| nodes << node.split(',')[0] }
  else
    nodes = nodes_rrp
  end
  nodes_options = nodes + options
  nodes_options += options_udp if transport_udp
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "cluster", "setup", "--enable", "--start",
    "--name", params[:clustername], *nodes_options
  )
  if retval != 0
    return [
      400,
      (stdout + [''] + stderr).collect { |line| line.rstrip() }.join("\n")
    ]
  end
  return 200
end

def create_cluster(params, request, auth_user)
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied'
  end
  if set_corosync_conf(params, request, auth_user)
    cluster_start(params, request, auth_user)
  else
    return "Failed"
  end
end

def remote_pacemaker_node_status(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  output, stderr, retval = run_cmd(auth_user, PCS, 'node', 'pacemaker-status')
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
        [:version, :operations].include?(k)
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

  _,_,not_authorized_nodes = check_gui_status_of_nodes(
    auth_user,
    status[:known_nodes],
    false,
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

  resource_list = []
  resources.each do |r|
    resource_list.concat(r.to_status('1'))
  end

  cluster_settings = (status[:cluster_settings].empty?) ?
    {'error' => 'Unable to get configuration settings'} :
    status[:cluster_settings]

  node_attr = {}
  status[:node_attr].each { |node, attrs|
    node_attr[node] = []
    attrs.each { |attr|
      node_attr[node] << {
        :key => attr[:name],
        :value => attr[:value]
      }
    }
  }

  old_status = {
    :uptime => node.uptime,
    :corosync => node.corosync,
    :pacemaker => node.pacemaker,
    :cman => node.cman,
    :corosync_enabled => node.corosync_enabled,
    :pacemaker_enabled => node.pacemaker_enabled,
    :pacemaker_remote => node.services[:pacemaker_remote][:running],
    :pacemaker_remote_enabled => node.services[:pacemaker_remote][:enabled],
    :pcsd_enabled => node.pcsd_enabled,
    :corosync_online => status[:corosync_online],
    :corosync_offline => status[:corosync_offline],
    :pacemaker_online => status[:pacemaker_online],
    :pacemaker_offline => status[:pacemaker_offline],
    :pacemaker_standby => status[:pacemaker_standby],
    :cluster_name => status[:cluster_name],
    :resources => resource_list,
    :groups => status[:groups],
    :constraints => status[:constraints],
    :cluster_settings => cluster_settings,
    :node_id => node.id,
    :node_attr => node_attr,
    :fence_levels => status[:fence_levels],
    :need_ring1_address => status[:need_ring1_address],
    :is_cman_with_udpu_transport => status[:is_cman_with_udpu_transport],
    :acls => status[:acls],
    :username => status[:username]
  }

  return JSON.generate(old_status)
end

def status_all(params, request, auth_user, nodes=[], dont_update_config=false)
  if nodes == nil
    return JSON.generate({"error" => "true"})
  end

  final_response = {}
  threads = []
  forbidden_nodes = {}
  nodes.each {|node|
    threads << Thread.new {
      code, response = send_request_with_token(auth_user, node, 'status')
      if 403 == code
        forbidden_nodes[node] = true
      end
      begin
        final_response[node] = JSON.parse(response)
      rescue JSON::ParserError => e
        final_response[node] = {"bad_json" => true}
        $logger.info("ERROR: Parse Error when parsing status JSON from #{node}")
      end
      if final_response[node] and final_response[node]["notoken"] == true
        $logger.error("ERROR: bad token for #{node}")
      end
    }
  }
  threads.each { |t| t.join }
  if forbidden_nodes.length > 0
    return 403, 'Permission denied'
  end

  # Get full list of nodes and see if we need to update the configuration
  node_list = []
  final_response.each { |fr,n|
    node_list += n["corosync_offline"] if n["corosync_offline"]
    node_list += n["corosync_online"] if n["corosync_online"]
    node_list += n["pacemaker_offline"] if n["pacemaker_offline"]
    node_list += n["pacemaker_online"] if n["pacemaker_online"]
  }

  node_list.uniq!
  if node_list.length > 0
    config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
    old_node_list = config.get_nodes(params[:cluster])
    if !(dont_update_config or config.cluster_nodes_equal?(params[:cluster], node_list))
      $logger.info("Updating node list for: #{params[:cluster]} #{old_node_list}->#{node_list}")
      config.update_cluster(params[:cluster], node_list)
      sync_config = Cfgsync::PcsdSettings.from_text(config.text())
      # on version conflict just go on, config will be corrected eventually
      # by displaying the cluster in the web UI
      Cfgsync::save_sync_new_version(
        sync_config, get_corosync_nodes(), $cluster_name, true
      )
      return status_all(params, request, auth_user, node_list, true)
    end
  end
  $logger.debug("NODE LIST: " + node_list.inspect)
  return JSON.generate(final_response)
end

def clusters_overview(params, request, auth_user)
  cluster_map = {}
  forbidden_clusters = {}
  threads = []
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  config.clusters.each { |cluster|
    threads << Thread.new {
      cluster_map[cluster.name] = {
        'cluster_name' => cluster.name,
        'error_list' => [
          {'message' => 'Unable to connect to the cluster. Request timeout.'}
        ],
        'warning_list' => [],
        'status' => 'unknown',
        'node_list' => get_default_overview_node_list(cluster.name),
        'resource_list' => []
      }
      overview_cluster = nil
      online, offline, not_authorized_nodes = check_gui_status_of_nodes(
        auth_user,
        get_cluster_nodes(cluster.name),
        false,
        3
      )
      not_supported = false
      forbidden = false
      cluster_nodes_auth = (online + offline).uniq
      cluster_nodes_all = (cluster_nodes_auth + not_authorized_nodes).uniq
      nodes_not_in_cluster = []
      for node in cluster_nodes_auth
        code, response = send_request_with_token(
          auth_user, node, 'cluster_status', true, {}, true, nil, 8
        )
        if code == 404
          not_supported = true
          next
        end
        if 403 == code
          forbidden = true
          forbidden_clusters[cluster.name] = true
          break
        end
        begin
          parsed_response = JSON.parse(response)
          if parsed_response['noresponse'] or parsed_response['pacemaker_not_running']
            next
          elsif parsed_response['notoken'] or parsed_response['notauthorized']
            next
          elsif parsed_response['cluster_name'] != cluster.name
            # queried node is not in the cluster (any more)
            nodes_not_in_cluster << node
            next
          else
            overview_cluster = parsed_response
            break
          end
        rescue JSON::ParserError
        end
      end

      if cluster_nodes_all.sort == nodes_not_in_cluster.sort
        overview_cluster = {
          'cluster_name' => cluster.name,
          'error_list' => [],
          'warning_list' => [],
          'status' => 'unknown',
          'node_list' => [],
          'resource_list' => []
        }
      end

      if not overview_cluster
        overview_cluster = {
          'cluster_name' => cluster.name,
          'error_list' => [],
          'warning_list' => [],
          'status' => 'unknown',
          'node_list' => get_default_overview_node_list(cluster.name),
          'resource_list' => []
        }
        if not_supported
          overview_cluster['warning_list'] = [
            {
              'message' => 'Cluster is running an old version of pcs/pcsd which does not provide data for the dashboard.',
            },
          ]
        else
          if forbidden
            overview_cluster['error_list'] = [
              {
                'message' => 'You do not have permissions to view the cluster.',
                'type' => 'forbidden',
              },
            ]
            overview_cluster['node_list'] = []
          else
            overview_cluster['error_list'] = [
              {
                'message' => 'Unable to connect to the cluster.',
              },
            ]
          end
        end
      end
      if not_authorized_nodes.length > 0
        overview_cluster['warning_list'] << {
          'message' => 'GUI is not authorized against node(s) '\
            + not_authorized_nodes.join(', '),
          'type' => 'nodes_not_authorized',
          'node_list' => not_authorized_nodes,
        }
      end

      overview_cluster['node_list'].each { |node|
        if node['status_version'] == '1'
          overview_cluster['warning_list'] << {
            :message => 'Some nodes are running old version of pcs/pcsd.'
          }
          break
        end
      }

      cluster_map[cluster.name] = overview_cluster
    }
  }

  begin
    Timeout::timeout(18) {
      threads.each { |t| t.join }
    }
  rescue Timeout::Error
    threads.each { |t| t.exit }
  end

  # update clusters in PCSConfig
  not_current_data = false
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  cluster_map.each { |cluster, values|
    next if forbidden_clusters[cluster]
    nodes = []
    values['node_list'].each { |node|
      nodes << node['name']
    }
    if !config.cluster_nodes_equal?(cluster, nodes)
      $logger.info("Updating node list for: #{cluster} #{config.get_nodes(cluster)}->#{nodes}")
      config.update_cluster(cluster, nodes)
      not_current_data = true
    end
  }
  if not_current_data
    sync_config = Cfgsync::PcsdSettings.from_text(config.text())
    # on version conflict just go on, config will be corrected eventually
    # by displaying the cluster in the web UI
    Cfgsync::save_sync_new_version(
      sync_config, get_corosync_nodes(), $cluster_name, true
    )
  end

  overview = {
    'not_current_data' => not_current_data,
    'cluster_list' => cluster_map.values.sort { |a, b|
      a['clustername'] <=> b['clustername']
    }
  }
  return JSON.generate(overview)
end

def auth(params, request, auth_user)
  token = PCSAuth.validUser(params['username'],params['password'], true)
  # If we authorized to this machine, attempt to authorize everywhere
  node_list = []
  if token and params["bidirectional"]
    params.each { |k,v|
      if k.start_with?("node-")
        node_list.push(v)
      end
    }
    if node_list.length > 0
      pcs_auth(
        auth_user, node_list, params['username'], params['password'],
        params["force"] == "1"
      )
    end
  end
  return token
end

# If we get here, we're already authorized
def check_auth(params, request, auth_user)
  if params.include?("check_auth_only")
    return [200, "{\"success\":true}"]
  end
  return JSON.generate({
    'success' => true,
    'node_list' => get_token_node_list,
  })
end

# not used anymore, left here for backward compatability reasons
def resource_status(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  resource_id = params[:resource]
  @resources,@groups = getResourcesGroups(auth_user)
  location = ""
  res_status = ""
  @resources.each {|r|
    if r.id == resource_id
      if r.failed
        res_status =  "Failed"
      elsif !r.active
        res_status = "Inactive"
      else
        res_status = "Running"
      end
      if r.nodes.length != 0
        location = r.nodes[0].name
        break
      end
    end
  }
  status = {"location" => location, "status" => res_status}
  return JSON.generate(status)
end

def resource_stop(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "resource", "disable", params[:resource]
  )
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

def resource_cleanup(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "resource", "cleanup", params[:resource]
  )
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

def resource_start(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "resource", "enable", params[:resource]
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

  param_line = getParamList(params)
  if not params[:resource_id]
    cmd = [PCS, "resource", "create", params[:name], params[:resource_type]]
    cmd += param_line
    if params[:resource_group] and params[:resource_group] != ""
      cmd += ['--group', params[:resource_group]]
      if (
        ['before', 'after'].include?(params[:in_group_position]) and
        params[:in_group_reference_resource_id]
      )
        cmd << "--#{params[:in_group_position]}"
        cmd << params[:in_group_reference_resource_id]
      end
      resource_group = params[:resource_group]
    end
    out, stderr, retval = run_cmd(auth_user, *cmd)
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end

    if params[:resource_clone] and params[:resource_clone] != ""
      name = resource_group ? resource_group : params[:name]
      run_cmd(auth_user, PCS, "resource", "clone", name)
    elsif params[:resource_ms] and params[:resource_ms] != ""
      name = resource_group ? resource_group : params[:name]
      run_cmd(auth_user, PCS, "resource", "master", name)
    end

    return JSON.generate({})
  end

  if param_line.length != 0
    # If it's a clone resource we strip off everything after the last ':'
    if params[:resource_clone]
      params[:resource_id].sub!(/(.*):.*/,'\1')
    end
    run_cmd(
      auth_user, PCS, "resource", "update", params[:resource_id], *param_line
    )
  end

  if params[:resource_group]
    if params[:resource_group] == ""
      if params[:_orig_resource_group] != ""
        run_cmd(
          auth_user, PCS, "resource", "group", "remove",
          params[:_orig_resource_group], params[:resource_id]
        )
      end
    else
      cmd = [
        PCS, "resource", "group", "add", params[:resource_group],
        params[:resource_id]
      ]
      if (
        ['before', 'after'].include?(params[:in_group_position]) and
        params[:in_group_reference_resource_id]
      )
        cmd << "--#{params[:in_group_position]}"
        cmd << params[:in_group_reference_resource_id]
      end
      run_cmd(auth_user, *cmd)
    end
  end

  if params[:resource_clone] and params[:_orig_resource_clone] == "false"
    run_cmd(auth_user, PCS, "resource", "clone", params[:resource_id])
  end
  if params[:resource_ms] and params[:_orig_resource_ms] == "false"
    run_cmd(auth_user, PCS, "resource", "master", params[:resource_id])
  end

  if params[:_orig_resource_clone] == "true" and not params[:resource_clone]
    run_cmd(
      auth_user, PCS, "resource", "unclone", params[:resource_id].sub(/:.*/,'')
    )
  end
  if params[:_orig_resource_ms] == "true" and not params[:resource_ms]
    run_cmd(
      auth_user, PCS, "resource", "unclone", params[:resource_id].sub(/:.*/,'')
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
  param_line = getParamList(params)
  $logger.info param_line

  if not params[:resource_id]
    out, stderr, retval = run_cmd(
      auth_user,
      PCS, "stonith", "create", params[:name], params[:resource_type],
      *param_line
    )
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
    return "{}"
  end

  if param_line.length != 0
    out, stderr, retval = run_cmd(
      auth_user, PCS, "stonith", "update", params[:resource_id], *param_line
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
  agents = getResourceAgents(auth_user)
  return JSON.generate(agents)
end

def get_avail_fence_agents(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  agents = getFenceAgents(auth_user)
  return JSON.generate(agents)
end

def remove_resource(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  force = params['force']
  user = PCSAuth.getSuperuserAuth()
  no_error_if_not_exists = params.include?('no_error_if_not_exists')
  resource_list = []
  errors = ''
  resource_to_remove = []
  params.each { |param,_|
    if param.start_with?('resid-')
      resource_list << param.split('resid-', 2)[1]
    end
  }
  tmp_file = nil
  if force
    resource_to_remove = resource_list
  else
    begin
      tmp_file = Tempfile.new('temp_cib')
      _, err, retval = run_cmd(user, PCS, 'cluster', 'cib', tmp_file.path)
      if retval != 0
        return [400, 'Unable to stop resource(s).']
      end
      cmd = [PCS, '-f', tmp_file.path, 'resource', 'disable']
      resource_list.each { |resource|
        out, err, retval = run_cmd(user, *(cmd + [resource]))
        if retval != 0
          unless (
            (out + err).join('').include?('unable to find a resource') and
            no_error_if_not_exists
          )
            errors += "Unable to stop resource '#{resource}': #{err.join('')}"
          end
        else
          resource_to_remove << resource
        end
      }
      _, _, retval = run_cmd(
        user, PCS, 'cluster', 'cib-push', tmp_file.path, '--config', '--wait'
      )
      if retval != 0
        return [400, 'Unable to stop resource(s).']
      end
      errors.strip!
      unless errors.empty?
        $logger.info("Stopping resource(s) errors:\n#{errors}")
        return [400, errors]
      end
    rescue IOError
      return [400, 'Unable to stop resource(s).']
    ensure
      if tmp_file
        tmp_file.close!
      end
    end
  end
  resource_to_remove.each { |resource|
    cmd = [PCS, 'resource', 'delete', resource]
    if force
      cmd << '--force'
    end
    out, err, retval = run_cmd(auth_user, *cmd)
    if retval != 0
      unless (
        (out + err).join('').include?(' does not exist.') and
        no_error_if_not_exists
      )
        errors += err.join(' ').strip + "\n"
      end
    end
  }
  errors.strip!
  if errors.empty?
    return 200
  else
    $logger.info("Remove resource errors:\n"+errors)
    return [400, errors]
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
        auth_user, PCS, "acl", "role", "delete", value.to_s, "--autodelete"
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
    auth_user, params["res_id"], params["key"],params["value"]
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
      params["res_id"], params["node_id"], params["score"], params["force"],
      !params['disable_autocorrect']
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
      resA, resB, actionA, actionB, params["score"], true, params["force"],
      !params['disable_autocorrect']
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
      auth_user,
      resA, resB, score, params["force"], !params['disable_autocorrect']
    )
  when "ticket"
    retval, error = add_ticket_constraint(
      auth_user,
      params["ticket"], params["res_id"], params["role"], params["loss-policy"],
      params["force"], !params['disable_autocorrect']
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
      !params['disable_autocorrect']
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
      auth_user,
      params["resources"].values, params["force"], !params['disable_autocorrect']
    )
  when "col"
    retval, error = add_colocation_set_constraint(
      auth_user,
      params["resources"].values, params["force"], !params['disable_autocorrect']
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
      !params['disable_autocorrect']
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
    auth_user, PCS, "resource", "group", "add", rg, *(resources.split(" "))
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

  # We need to be able to set cluster properties also from older version GUI.
  # This code handles proper processing of checkboxes.
  # === backward compatibility layer start ===
  params['hidden'].each { |prop, val|
    next if prop == 'hidden_input'
    unless properties.include?(prop)
      properties[prop] = val
      to_update << prop
    end
  }
  # === backward compatibility layer end ===

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

  if to_update.empty?
    $logger.info('No properties to update')
  else
    cmd_args = []
    to_update.each { |prop|
      cmd_args << "#{prop.downcase}=#{properties[prop]}"
    }
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, 'property', 'set', *cmd_args
    )
    if retval != 0
      return [400, stderr.join('').gsub(', (use --force to override)', '')]
    end
  end
  return [200, "Update Successful"]
end

def cluster_destroy(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  out, errout, retval = run_cmd(auth_user, PCS, "cluster", "destroy")
  if retval == 0
    return [200, "Successfully destroyed cluster"]
  else
    return [400, "Error destroying cluster:\n#{out}\n#{errout}\n#{retval}\n"]
  end
end

def get_wizard(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  wizard = PCSDWizard.getWizard(params["wizard"])
  if wizard != nil
    return erb wizard.collection_page
  else
    return "Error finding Wizard - #{params["wizard"]}"
  end
end

def wizard_submit(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  wizard = PCSDWizard.getWizard(params["wizard"])
  if wizard != nil
    return erb wizard.process_responses(params)
  else
    return "Error finding Wizard - #{params["wizard"]}"
  end

end

# not used anymore, left here for backward compatability reasons
def get_tokens(params, request, auth_user)
  # pcsd runs as root thus always returns hacluster's tokens
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  return [200, JSON.generate(read_tokens)]
end

def get_cluster_tokens(params, request, auth_user)
  # pcsd runs as root thus always returns hacluster's tokens
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, "Permission denied"
  end
  on, off = get_nodes
  nodes = on + off
  nodes.uniq!
  return [200, JSON.generate(get_tokens_of_nodes(nodes))]
end

def save_tokens(params, request, auth_user)
  # pcsd runs as root thus always returns hacluster's tokens
  if not allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, "Permission denied"
  end

  new_tokens = {}

  params.each{|nodes|
    if nodes[0].start_with?"node:" and nodes[0].length > 5
      node = nodes[0][5..-1]
      token = nodes[1]
      new_tokens[node] = token
    end
  }

  tokens_cfg = Cfgsync::PcsdTokens.from_file()
  sync_successful, sync_responses = Cfgsync::save_sync_new_tokens(
    tokens_cfg, new_tokens, get_corosync_nodes(), $cluster_name
  )

  if sync_successful
    return [200, JSON.generate(read_tokens())]
  else
    return [400, "Cannot update tokenfile."]
  end
end

def resource_master(params, request, auth_user)
  if not allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end
  _, stderr, retval = run_cmd(
    auth_user, PCS, 'resource', 'master', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to create master/slave resource from ' +
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
        auth_user, PCS, 'resource', 'group', 'remove', params[:old_group_id],
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
    PCS, 'resource', 'group', 'add', params[:group_id], params[:resource_id]
  ]
  if (
  ['before', 'after'].include?(params[:in_group_position]) and
    params[:in_group_reference_resource_id]
  )
    cmd << "--#{params[:in_group_position]}"
    cmd << params[:in_group_reference_resource_id]
  end
  _, stderr, retval = run_cmd(auth_user, *cmd)
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
    auth_user, PCS, 'resource', 'ungroup', params[:group_id]
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
    auth_user, PCS, 'resource', 'clone', params[:resource_id]
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
    auth_user, PCS, 'resource', 'unclone', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to unclone ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def set_resource_utilization(params, reqest, auth_user)
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
    auth_user, PCS, 'resource', 'utilization', res_id, "#{name}=#{value}"
  )

  if retval != 0
    return [400, "Unable to set utilization '#{name}=#{value}' for " +
      "resource '#{res_id}': #{stderr.join('')}"
    ]
  end
  return 200
end

def set_node_utilization(params, reqest, auth_user)
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
    auth_user, PCS, 'node', 'utilization', node, "#{name}=#{value}"
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
    auth_user, PCS, 'property', 'get_cluster_properties_definition'
  )
  if retval == 0
    return [200, stdout]
  end
  return [400, '{}']
end

def get_resource_agent_metadata(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  agent = params[:resource_agent]
  unless agent
    return [400, 'Parameter "resource_agent" required.']
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, 'resource', 'get_resource_agent_info', agent
  )
  if retval != 0
    if stderr.join('').include?('is not supported')
      return [200, JSON.generate({
        :name => agent,
        :longdesc => '',
        :shortdesc => '',
        :parameters => []
      })]
    else
      return [400, stderr.join("\n")]
    end
  end
  return [200, stdout.join("\n")]
end

def get_fence_agent_metadata(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  agent = params[:fence_agent]
  unless agent
    return [400, 'Parameter "fence_agent" required.']
  end
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, 'stonith', 'get_fence_agent_info', agent
  )
  if retval != 0
    return [400, stderr.join("\n")]
  end
  return [200, stdout.join("\n")]
end

def check_sbd(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  out = {
    :sbd => {
      :installed => is_service_installed?(get_sbd_service_name()),
      :enabled => is_service_enabled?(get_sbd_service_name()),
      :running => is_service_running?(get_sbd_service_name())
    }
  }
  watchdog = param[:watchdog]
  if watchdog
    out[:watchdog] = {
      :path => watchdog,
      :exist => File.exist?(watchdog)
    }
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
    msg = "Unable to save SBD configuration: #{e}"
    $logger.error(msg)
    return [400, msg]
  ensure
    if file
      file.flock(File::LOCK_UN)
      file.close()
    end
  end
  msg = 'SBD configuration saved.'
  $logger.info(msg)
  return [200, msg]
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
    msg = "Unable to get SBD configuration: #{e}"
    $logger.error(msg)
    return [400, msg]
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
    msg = 'SBD disabled'
    $logger.info(msg)
    return [200, msg]
  else
    msg = 'Disabling SBD failed'
    $logger.error(msg)
    return [400, msg]
  end
end

def sbd_enable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if enable_service(get_sbd_service_name())
    msg = 'SBD enabled'
    $logger.info(msg)
    return [200, msg]
  else
    msg = 'Enabling SBD failed'
    $logger.error(msg)
    return [400, msg]
  end
end

def remove_stonith_watchdog_timeout(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if set_cluster_prop_force(auth_user, 'stonith-watchdog-timeout', '')
    $logger.info('Cluster property "stonith-watchdog-timeout" removed')
    return [200, 'OK']
  else
    $logger.info('Failed to remove cluster property "stonith-watchdog-timeout"')
    return [400, 'ERROR']
  end
end

def set_stonith_watchdog_timeout_to_zero(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if set_cluster_prop_force(auth_user, 'stonith-watchdog-timeout', '0')
    $logger.info('Cluster property "stonith-watchdog-timeout" set to "0"')
    return [200, 'OK']
  else
    $logger.info(
      'Failed to set cluster property "stonith-watchdog-timeout"to 0'
    )
    return [400, 'ERROR']
  end
end

def remote_enable_sbd(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  arg_list = []

  if ['true', '1', 'on'].include?(params[:ignore_offline_nodes])
    arg_list << '--skip-offline'
  end

  params[:watchdog].each do |node, watchdog|
    unless watchdog.strip.empty?
      arg_list << "--watchdog=#{watchdog.strip}@#{node}"
    end
  end

  params[:config].each do |option, value|
    unless value.empty?
      arg_list << "#{option}=#{value}"
    end
  end

  _, stderr, retcode = run_cmd(
    auth_user, PCS, 'stonith', 'sbd', 'enable', *arg_list
  )

  if retcode != 0
    return [400, "Unable to enable sbd in cluster:\n#{stderr.join('')}"]
  end

  return [200, 'Sbd has been enabled.']
end

def remote_disable_sbd(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end

  arg_list = []

  if ['true', '1', 'on'].include?(params[:ignore_offline_nodes])
    arg_list << '--skip-offline'
  end

  _, stderr, retcode = run_cmd(
    auth_user, PCS, 'stonith', 'sbd', 'disable', *arg_list
  )

  if retcode != 0
    return [400, "Unable to disable sbd in cluster:\n#{stderr.join('')}"]
  end

  return [200, 'Sbd has been disabled.']
end

def qdevice_net_get_ca_certificate(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  begin
    return [
      200,
      Base64.encode64(File.read(COROSYNC_QDEVICE_NET_SERVER_CA_FILE))
    ]
  rescue => e
    return [400, "Unable to read certificate: #{e}"]
  end
end

def qdevice_net_sign_node_certificate(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::READ)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd_options(
    auth_user,
    {'stdin' => params[:certificate_request]},
    PCS, 'qdevice', 'sign-net-cert-request', '--name', params[:cluster_name]
  )
  if retval != 0
    return [400, stderr.join('')]
  end
  return [200, stdout.join('')]
end

def qdevice_net_client_init_certificate_storage(params, request, auth_user)
  # Last step of adding qdevice into a cluster is distribution of corosync.conf
  # file with qdevice settings. This requires FULL permissions currently.
  # If that gets relaxed, we can require lower permissions in here as well.
  unless allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd_options(
    auth_user,
    {'stdin' => params[:ca_certificate]},
    PCS, 'qdevice', 'net-client', 'setup'
  )
  if retval != 0
    return [400, stderr.join('')]
  end
  return [200, stdout.join('')]
end

def qdevice_net_client_import_certificate(params, request, auth_user)
  # Last step of adding qdevice into a cluster is distribution of corosync.conf
  # file with qdevice settings. This requires FULL permissions currently.
  # If that gets relaxed, we can require lower permissions in here as well.
  unless allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd_options(
    auth_user,
    {'stdin' => params[:certificate]},
    PCS, 'qdevice', 'net-client', 'import-certificate'
  )
  if retval != 0
    return [400, stderr.join('')]
  end
  return [200, stdout.join('')]
end

def qdevice_net_client_destroy(param, request, auth_user)
  # When removing a qdevice from a cluster, an updated corosync.conf file
  # with removed qdevice settings is distributed. This requires FULL permissions
  # currently. If that gets relaxed, we can require lower permissions in here
  # as well.
  unless allowed_for_local_cluster(auth_user, Permissions::FULL)
    return 403, 'Permission denied'
  end
  stdout, stderr, retval = run_cmd(
    auth_user,
    PCS, 'qdevice', 'net-client', 'destroy'
  )
  if retval != 0
    return [400, stderr.join('')]
  end
  return [200, stdout.join('')]
end

def qdevice_client_disable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if disable_service('corosync-qdevice')
    msg = 'corosync-qdevice disabled'
    $logger.info(msg)
    return [200, msg]
  else
    msg = 'Disabling corosync-qdevice failed'
    $logger.error(msg)
    return [400, msg]
  end
end

def qdevice_client_enable(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if not is_service_enabled?('corosync')
    msg = 'corosync is not enabled, skipping'
    $logger.info(msg)
    return [200, msg]
  elsif enable_service('corosync-qdevice')
    msg = 'corosync-qdevice enabled'
    $logger.info(msg)
    return [200, msg]
  else
    msg = 'Enabling corosync-qdevice failed'
    $logger.error(msg)
    return [400, msg]
  end
end

def qdevice_client_stop(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if stop_service('corosync-qdevice')
    msg = 'corosync-qdevice stopped'
    $logger.info(msg)
    return [200, msg]
  else
    msg = 'Stopping corosync-qdevice failed'
    $logger.error(msg)
    return [400, msg]
  end
end

def qdevice_client_start(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  if not is_service_running?('corosync')
    msg = 'corosync is not running, skipping'
    $logger.info(msg)
    return [200, msg]
  elsif start_service('corosync-qdevice')
    msg = 'corosync-qdevice started'
    $logger.info(msg)
    return [200, msg]
  else
    msg = 'Starting corosync-qdevice failed'
    $logger.error(msg)
    return [400, msg]
  end
end

def manage_resource(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  unless param[:resource_list_json]
    return [400, "Required parameter 'resource_list_json' is missing."]
  end
  begin
    resource_list = JSON.parse(param[:resource_list_json])
    _, err, retval = run_cmd(
      auth_user, PCS, 'resource', 'manage', *resource_list
    )
    if retval != 0
      return [400, err.join('')]
    end
    return [200, '']
  rescue JSON::ParserError
    return [400, 'Invalid input data format']
  end
end

def unmanage_resource(param, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  unless param[:resource_list_json]
    return [400, "Required parameter 'resource_list_json' is missing."]
  end
  begin
    resource_list = JSON.parse(param[:resource_list_json])
    _, err, retval = run_cmd(
      auth_user, PCS, 'resource', 'unmanage', *resource_list
    )
    if retval != 0
      return [400, err.join('')]
    end
    return [200, '']
  rescue JSON::ParserError
    return [400, 'Invalid input data format']
  end
end

def booth_set_config(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  begin
    unless params[:data_json]
      return [400, "Missing required parameter 'data_json'"]
    end
    data = JSON.parse(params[:data_json], {:symbolize_names => true})
  rescue JSON::ParserError
    return [400, 'Invalid input data format']
  end
  config = data[:config]
  authfile = data[:authfile]
  return [400, 'Invalid input data format'] unless (
    config and config[:name] and config[:data]
  )
  return [400, 'Invalid input data format'] if (
    authfile and (not authfile[:name] or not authfile[:data])
  )
  begin
    write_booth_config(config[:name], config[:data])
    if authfile
      write_booth_authfile(authfile[:name], authfile[:data])
    end
  rescue InvalidFileNameException => e
    return [400, "Invalid format of config/key file name '#{e.message}'"]
  rescue => e
    msg = "Unable to save booth configuration: #{e.message}"
    $logger.error(msg)
    return [400, msg]
  end
  msg = 'Booth configuration saved.'
  $logger.info(msg)
  return [200, msg]
end

def booth_save_files(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  begin
    data = JSON.parse(params[:data_json], {:symbolize_names => true})
    data.each { |file|
      unless file[:name] and file[:data]
        return [400, 'Invalid input data format']
      end
      if file[:name].include?('/')
        return [400, "Invalid file name format '#{file[:name]}'"]
      end
    }
  rescue JSON::ParserError, NoMethodError
    return [400, 'Invalid input data format']
  end
  rewrite_existing = (
  params.include?('rewrite_existing') || params.include?(:rewrite_existing)
  )

  conflict_files = []
  data.each { |file|
    next unless File.file?(File.join(BOOTH_CONFIG_DIR, file[:name]))
    if file[:is_authfile]
      cur_data = read_booth_authfile(file[:name])
    else
      cur_data = read_booth_config(file[:name])
    end
    if cur_data != file[:data]
      conflict_files << file[:name]
    end
  }

  write_failed = {}
  saved_files = []
  data.each { |file|
    next if conflict_files.include?(file[:name]) and not rewrite_existing
    begin
      if file[:is_authfile]
        write_booth_authfile(file[:name], file[:data])
      else
        write_booth_config(file[:name], file[:data])
      end
      saved_files << file[:name]
    rescue => e
      msg = "Unable to save file (#{file[:name]}): #{e.message}"
      $logger.error(msg)
      write_failed[file[:name]] = e
    end
  }
  return [200, JSON.generate({
    :existing => conflict_files,
    :saved => saved_files,
    :failed => write_failed
  })]
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

def _hash_to_argument_list(hash)
  result = []
  if hash.kind_of?(Hash)
    hash.each {|key, value|
      value = '' if value.nil?
      result << "#{key}=#{value}"
    }
  end
  return result
end

def create_alert(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  path = params[:path]
  unless path
    return [400, 'Missing required parameter: path']
  end
  alert_id = params[:alert_id]
  description = params[:description]
  meta_attr_list = _hash_to_argument_list(params[:meta_attr])
  instance_attr_list = _hash_to_argument_list(params[:instance_attr])
  cmd = [PCS, 'alert', 'create', "path=#{path}"]
  cmd << "id=#{alert_id}" if alert_id and alert_id != ''
  cmd << "description=#{description}" if description and description != ''
  cmd += ['options', *instance_attr_list] if instance_attr_list.any?
  cmd += ['meta', *meta_attr_list] if meta_attr_list.any?
  output, stderr, retval = run_cmd(auth_user, *cmd)
  if retval != 0
    return [400, "Unable to create alert: #{stderr.join("\n")}"]
  end
  return [200, 'Alert created']
end

def update_alert(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  alert_id = params[:alert_id]
  unless alert_id
    return [400, 'Missing required parameter: alert_id']
  end
  path = params[:path]
  description = params[:description]
  meta_attr_list = _hash_to_argument_list(params[:meta_attr])
  instance_attr_list = _hash_to_argument_list(params[:instance_attr])
  cmd = [PCS, 'alert', 'update', alert_id]
  cmd << "path=#{path}" if path
  cmd << "description=#{description}" if description
  cmd += ['options', *instance_attr_list] if instance_attr_list.any?
  cmd += ['meta', *meta_attr_list] if meta_attr_list.any?
  output, stderr, retval = run_cmd(auth_user, *cmd)
  if retval != 0
    return [400, "Unable to update alert: #{stderr.join("\n")}"]
  end
  return [200, 'Alert updated']
end

def remove_alerts_and_recipients(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  alert_list = params[:alert_list]
  recipient_list = params[:recipient_list]
  if recipient_list.kind_of?(Array) and recipient_list.any?
    output, stderr, retval = run_cmd(
      auth_user, PCS, 'alert', 'recipient', 'remove', *recipient_list
    )
    if retval != 0
      return [400, "Unable to remove recipients: #{stderr.join("\n")}"]
    end
  end
  if alert_list.kind_of?(Array) and alert_list.any?
    output, stderr, retval = run_cmd(
      auth_user, PCS, 'alert', 'remove', *alert_list
    )
    if retval != 0
      return [400, "Unable to remove alerts: #{stderr.join("\n")}"]
    end
  end
  return [200, 'All removed']
end

def create_recipient(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  alert_id = params[:alert_id]
  if not alert_id or alert_id.strip! == ''
    return [400, 'Missing required paramter: alert_id']
  end
  value = params[:value]
  if not value or value == ''
    return [400, 'Missing required paramter: value']
  end
  recipient_id = params[:recipient_id]
  description = params[:description]
  meta_attr_list = _hash_to_argument_list(params[:meta_attr])
  instance_attr_list = _hash_to_argument_list(params[:instance_attr])
  cmd = [PCS, 'alert', 'recipient', 'add', alert_id, "value=#{value}"]
  cmd << "id=#{recipient_id}" if recipient_id and recipient_id != ''
  cmd << "description=#{description}" if description and description != ''
  cmd += ['options', *instance_attr_list] if instance_attr_list.any?
  cmd += ['meta', *meta_attr_list] if meta_attr_list.any?
  output, stderr, retval = run_cmd(auth_user, *cmd)
  if retval != 0
    return [400, "Unable to create recipient: #{stderr.join("\n")}"]
  end
  return [200, 'Recipient created']
end

def update_recipient(params, request, auth_user)
  unless allowed_for_local_cluster(auth_user, Permissions::WRITE)
    return 403, 'Permission denied'
  end
  recipient_id = params[:recipient_id]
  if not recipient_id or recipient_id.strip! == ''
    return [400, 'Missing required paramter: recipient_id']
  end
  value = params[:value]
  if value and value.strip! == ''
    return [400, 'Parameter value canot be empty string']
  end
  description = params[:description]
  meta_attr_list = _hash_to_argument_list(params[:meta_attr])
  instance_attr_list = _hash_to_argument_list(params[:instance_attr])
  cmd = [PCS, 'alert', 'recipient', 'update', recipient_id]
  cmd << "value=#{value}" if value
  cmd << "description=#{description}" if description
  cmd += ['options', *instance_attr_list] if instance_attr_list.any?
  cmd += ['meta', *meta_attr_list] if meta_attr_list.any?
  output, stderr, retval = run_cmd(auth_user, *cmd)
  if retval != 0
    return [400, "Unable to update recipient: #{stderr.join("\n")}"]
  end
  return [200, 'Recipient updated']
end
