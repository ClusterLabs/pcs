require 'json'
require 'uri'
require 'open4'

require 'pcs.rb'
require 'resource.rb'
require 'config.rb'
require 'cfgsync.rb'
require 'cluster_entity.rb'

# Commands for remote access
def remote(params,request)
  remote_cmd_without_pacemaker = {
      :status => method(:node_status),
      :status_all => method(:status_all),
      :cluster_status => method(:cluster_status),
      :auth => method(:auth),
      :check_auth => method(:check_auth),
      :fix_auth_of_cluster => method(:fix_auth_of_cluster),
      :setup_cluster => method(:setup_cluster),
      :create_cluster => method(:create_cluster),
      :get_quorum_info => method(:get_quorum_info),
      :get_cib => method(:get_cib),
      :get_corosync_conf => method(:get_corosync_conf),
      :set_cluster_conf => lambda { |param|
        if set_cluster_conf(params)
          return "Updated cluster.conf..."
        else
          return "Failed to update cluster.conf..."
        end
      },
      :set_corosync_conf => lambda { |param|
        if set_corosync_conf(params)
          return "Succeeded"
        else
          return "Failed"
        end
      },
      :get_sync_capabilities => method(:get_sync_capabilities),
      :set_sync_options => method(:set_sync_options),
      :get_configs => method(:get_configs),
      :set_configs => method(:set_configs),
      :set_certs => method(:set_certs),
      :pcsd_restart => method(:remote_pcsd_restart),
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
      :check_gui_status => method(:check_gui_status),
      :get_sw_versions => method(:get_sw_versions),
      :node_available => method(:remote_node_available),
      :add_node_all => lambda { |param|
        remote_add_node(params,true)
      },
      :add_node => lambda { |param|
        remote_add_node(params,false)
      },
      :remove_nodes => method(:remote_remove_nodes),
      :remove_node => method(:remote_remove_node),
      :cluster_destroy => method(:cluster_destroy),
      :get_wizard => method(:get_wizard),
      :wizard_submit => method(:wizard_submit),
      :auth_nodes => method(:auth_nodes),
      :get_tokens => method(:get_tokens),
      :get_cluster_tokens => method(:get_cluster_tokens),
      :save_tokens => method(:save_tokens),
      :add_node_to_cluster => method(:add_node_to_cluster),
  }
  remote_cmd_with_pacemaker = {
      :resource_start => method(:resource_start),
      :resource_stop => method(:resource_stop),
      :resource_cleanup => method(:resource_cleanup),
      :resource_form => method(:resource_form),
      :fence_device_form => method(:fence_device_form),
      :update_resource => method(:update_resource),
      :update_fence_device => method(:update_fence_device),
      :resource_metadata => method(:resource_metadata),
      :fence_device_metadata => method(:fence_device_metadata),
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
      :resource_ungroup => method(:resource_ungroup)
  }

  command = params[:command].to_sym

  if remote_cmd_without_pacemaker.include? command
    return remote_cmd_without_pacemaker[command].call(params)
  elsif remote_cmd_with_pacemaker.include? command
    if pacemaker_running?
      return remote_cmd_with_pacemaker[command].call(params)
    else
      return [200,'{"pacemaker_not_running":true}']
    end
  else
    return [404, "Unknown Request"]
  end
end

def cluster_status(params, cluster_name=nil, dont_update_config=false)
  unless cluster_name
    cluster_name = $cluster_name
  end
  overview = {
      :cluster_name => cluster_name,
      :error_list => [],
      :warning_list => [],
      :quorate => nil,
      :status => 'unknown',
      :node_list => [],
      :resource_list => [],
  }
  if not cluster_name or cluster_name.empty?
    return JSON.generate(overview)
  end

  node_map = {}
  node_list = []
  priority_nodes = []
  threads = []
  not_authorized_nodes = []
  cluster_nodes = get_cluster_nodes(cluster_name)
  old_status = 0
  cluster_nodes.each { |node|
    threads << Thread.new {
      _, response = send_request_with_token(
        node,
        'status',
        false,
        {:version=>'2', :operations=>'1'},
        true,
        nil,
        6
      )
      node_map[node] = {}
      node_map[node].update(overview)
      begin
        parsed_response = JSON.parse(response, {:symbolize_names => true})
        if parsed_response[:noresponse]
          node_map[node][:node] = {
            :status => 'unknown',
            :warning_list => [],
            :error_list => []
          }
        elsif parsed_response[:notoken] or parsed_response[:notauthorized]
          not_authorized_nodes << node
          node_map[node][:node] = {
            :status => 'unknown',
            :notauthorized => true,
            :warning_list => [],
            :error_list => []
          }
        else
          if parsed_response[:node] # status version == 2
            parsed_response[:status_version] = '2'
            parsed_response[:node][:status_version] = '2'
            priority_nodes << node if parsed_response[:node][:quorum]
          else
            parsed_response = status_v1_to_v2(parsed_response)
            old_status += 1
          end
          node_map[node] = parsed_response
        end
        node_map[node][:node][:name] = node
      rescue JSON::ParserError
        node_map[node] = {:status => 'unknown'}
        node_map[node][:node] = {
          :name => node,
          :warning_list => [],
          :error_list => []
        }
      end
    }
  }
  threads.each { |t| t.join }

  cluster_nodes = []
  node_map.each { |_, n|
    node_list << n[:node]
    cluster_nodes += n['corosync_offline'] if n['corosync_offline']
    cluster_nodes += n['corosync_online'] if n['corosync_online']
    cluster_nodes += n['pacemaker_offline'] if n['pacemaker_offline']
    cluster_nodes += n['pacemaker_online'] if n['pacemaker_online']
  }

  cluster_nodes.uniq!
  if cluster_nodes.length > 0
    config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
    old_cluster_nodes = config.get_nodes(params[:cluster])
    if !(dont_update_config or config.cluster_nodes_equal?(params[:cluster], cluster_nodes))
      $logger.info("Updating node list for: #{params[:cluster]} #{old_cluster_nodes}->#{cluster_nodes}")
      config.update_cluster(params[:cluster], cluster_nodes)
      sync_config = Cfgsync::PcsdSettings.from_text(config.text())
      # on version conflict just go on, config will be corrected eventually
      # by displaying the cluster in the web UI
      Cfgsync::save_sync_new_version(
          sync_config, get_corosync_nodes(), cluster_name, true
      )
      return cluster_status(params, cluster_name, true)
    end
  end
  
  if priority_nodes.length > 0
    status = overview.update(node_map[priority_nodes[0]])
    status[:quorate] = true
    status[:node_list] = node_list
  elsif old_status == 0 # all new but no qourum
    status = overview.update(node_map.values[0])
    status[:quorate] = false
    status[:node_list] = node_list
  else
    status = overview.update(node_map.values[0])
    status[:node_list] = node_list
    status[:quorate] = nil
    node_map.each { |_,node|
      if node[:status_version] and node[:status_version] == '1' and
          !node[:cluster_settings][:error]
        status = overview.update(node)
        break
      end
    }
  end

  if status[:quorate]
    fence_count = 0
    status[:resource_list].each { |r|
      if r[:stonith]
        fence_count += 1
      end
    }
    if fence_count == 0
      status[:warning_list] << {
          :message => 'No fence devices configured in the cluster',
      }
    end

    if status[:cluster_settings]['stonith-enabled'.to_sym] and
        not ['true', 'on'].include?(status[:cluster_settings]['stonith-enabled'.to_sym])
      status[:warning_list] << {
          :message => 'Stonith is not enabled',
      }
    end
  end

  if not_authorized_nodes.length > 0
    status[:warning_list] << {
        :message => 'Not authorized against node(s) '\
            + not_authorized_nodes.join(', '),
        :type => 'nodes_not_authorized',
        :node_list => not_authorized_nodes,
    }
  end

  if status[:quorate].nil?
    if old_status > 0
      status[:warning_list] << {
          :message => 'Cluster is running old version of pcs/pcsd which '\
              + "doesn't provide data for dashboard.",
          :type => 'old_pcsd'
      }
    else
      status[:error_list] << {
          :message => 'Unable to connect to cluster.'
      }
    end
    status[:status] == 'unknown'
    return JSON.generate(status)
  end

  if status[:error_list].length > 0 or (not status[:quorate].nil? and not status[:quorate])
    status[:status] = 'error'
  else
    if status[:warning_list].length > 0
      status[:status] = 'warning'
    end
    status[:node_list].each { |node|
      if (node[:error_list] and node[:error_list].length > 0) or
          ['unknown', 'offline'].include?(node[:status])
        status[:status] = 'error'
        break
      elsif node[:warning_list] and node[:warning_list].length > 0
        status[:status] = 'warning'
      end
    }
    if status[:status] != 'error'
      status[:resource_list].each { |resource|
        if resource[:status] == 'failed'
          status[:status] = 'error'
          break
        elsif ['blocked', 'partially running'].include?(resource[:status])
          status[:status] = 'warning'
        end
      }
    end
  end
  status[:status] = 'ok' if status[:status] == 'unknown'
  return JSON.generate(status)
end

def cluster_start(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'cluster_start', true)
  else
    $logger.info "Starting Daemons"
    output =  `#{PCS} cluster start`
    $logger.debug output
    return output
  end
end

def cluster_stop(params)
  if params[:name]
    params_without_name = params.reject {|key, value|
      key == "name" or key == :name
    }
    code, response = send_request_with_token(
      params[:name], 'cluster_stop', true, params_without_name
    )
  else
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
    stdout, stderr, retval = run_cmd(PCS, "cluster", "stop", *options)
    if retval != 0
      return [400, stderr.join]
    else
      return stdout.join
    end
  end
end

def config_backup(params)
  if params[:name]
    code, response = send_request_with_token(
        params[:name], 'config_backup', true
    )
  else
    $logger.info "Backup node configuration"
    stdout, stderr, retval = run_cmd(PCS, "config", "backup")
    if retval == 0
        $logger.info "Backup successful"
        return [200, stdout]
    end
    $logger.info "Error during backup: #{stderr.join(' ').strip()}"
    return [400, "Unable to backup node: #{stderr.join(' ')}"]
  end
end

def config_restore(params)
  if params[:name]
    code, response = send_request_with_token(
        params[:name], 'config_restore', true, {:tarball => params[:tarball]}
    )
  else
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

def node_restart(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'node_restart', true)
  else
    $logger.info "Restarting Node"
    output =  `/sbin/reboot`
    $logger.debug output
    return output
  end
end

def node_standby(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'node_standby', true, {"node"=>params[:name]})
    # data={"node"=>params[:name]} for backward compatibility with older versions of pcs/pcsd
  else
    $logger.info "Standby Node"
    stdout, stderr, retval = run_cmd(PCS,"cluster","standby")
    return stdout
  end
end

def node_unstandby(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'node_unstandby', true, {"node"=>params[:name]})
    # data={"node"=>params[:name]} for backward compatibility with older versions of pcs/pcsd
  else
    $logger.info "Unstandby Node"
    stdout, stderr, retval = run_cmd(PCS,"cluster","unstandby")
    return stdout
  end
end

def cluster_enable(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'cluster_enable', true)
  else
    success = enable_cluster()
    if not success
      return JSON.generate({"error" => "true"})
    end
    return "Cluster Enabled"
  end
end

def cluster_disable(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'cluster_disable', true)
  else
    success = disable_cluster()
    if not success
      return JSON.generate({"error" => "true"})
    end
    return "Cluster Disabled"
  end
end

def get_quorum_info(params)
  if ISRHEL6
    stdout_status, stderr_status, retval = run_cmd(CMAN_TOOL, "status")
    stdout_nodes, stderr_nodes, retval = run_cmd(
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
    stdout, stderr, retval = run_cmd(COROSYNC_QUORUMTOOL, "-p", "-s")
    # retval is 0 on success if node is not in partition with quorum
    # retval is 1 on error OR on success if node has quorum
    if stderr.length > 0
      return stderr.join
    else
      return stdout.join
    end
  end
end

def get_cib(params)
  cib, stderr, retval = run_cmd(CIBADMIN, "-Ql")
  if retval != 0
    if not pacemaker_running?
      return [400, '{"pacemaker_not_running":true}']
    end
    return [500, "Unable to get CIB: " + cib.to_s + stderr.to_s]
  else
    return [200, cib]
  end
end

def get_corosync_conf(params)
  return Cfgsync::cluster_cfg_class.from_file().text()
end

def set_cluster_conf(params)
  if params[:cluster_conf] != nil and params[:cluster_conf] != ""
    Cfgsync::ClusterConf.backup()
    Cfgsync::ClusterConf.from_text(params[:cluster_conf]).save()
    return true
  else
    $logger.info "Invalid cluster.conf file"
    return false
  end
end


def set_corosync_conf(params)
  if params[:corosync_conf] != nil and params[:corosync_conf] != ""
    Cfgsync::CorosyncConf.backup()
    Cfgsync::CorosyncConf.from_text(params[:corosync_conf]).save()
    return true
  else
    $logger.info "Invalid corosync.conf file"
    return false
  end
end

def get_sync_capabilities(params)
  return JSON.generate({
    'syncable_configs' => Cfgsync::get_cfg_classes_by_name().keys,
  })
end

def set_sync_options(params)
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

def get_configs(params)
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

def set_configs(params)
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

def set_certs(params)
  if SUPERUSER != $session[:username]
    return 403, "Permission denied"
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
    begin
      write_file_lock(CRT_FILE, 0700, ssl_cert)
      write_file_lock(KEY_FILE, 0700, ssl_key)
    rescue
      # clean the files if we ended in the middle
      # the files will be regenerated on next pcsd start
      FileUtils.rm(CRT_FILE, {:force => true})
      FileUtils.rm(KEY_FILE, {:force => true})
      return [400, 'cannot save ssl files']
    end
  end

  if params['cookie_secret']
    cookie_secret = params['cookie_secret'].strip
    if !cookie_secret.empty?
      begin
        write_file_lock(COOKIE_FILE, 0700, cookie_secret)
      rescue
        return [400, 'cannot save cookie secret']
      end
    end
  end

  return [200, 'success']
end

def remote_pcsd_restart(params)
  pcsd_restart()
  return [200, 'success']
end

def check_gui_status(params)
  node_results = {}
  if params[:nodes] != nil and params[:nodes] != ""
    node_array = params[:nodes].split(",")
    online, offline, notauthorized = check_gui_status_of_nodes(node_array)
    online.each { |node|
      node_results[node] = "Online"
    }
    offline.each { |node|
      node_results[node] = "Offline"
    }
    notauthorized.each { |node|
      node_results[node] = "Unable to authenticate"
    }
  end
  return JSON.generate(node_results)
end

def get_sw_versions(params)
  if params[:nodes] != nil and params[:nodes] != ""
    nodes = params[:nodes].split(",")
    final_response = {}
    threads = []
    nodes.each {|node|
      threads << Thread.new {
        code, response = send_request_with_token(node, 'get_sw_versions')
        begin
          node_response = JSON.parse(response)
          if node_response and node_response["notoken"] == true
            $logger.error("ERROR: bad token for #{node}")
          end
          final_response[node] = node_response
        rescue JSON::ParserError => e
        end
      }
    }
    threads.each { |t| t.join }
    return JSON.generate(final_response)
  end
  versions = {
    "rhel" => get_rhel_version(),
    "pcs" => get_pcsd_version(),
    "pacemaker" => get_pacemaker_version(),
    "corosync" => get_corosync_version(),
    "cman" => get_cman_version(),
  }
  return JSON.generate(versions)
end

def remote_node_available(params)
  if (not ISRHEL6 and File.exist?(Cfgsync::CorosyncConf.file_path)) or (ISRHEL6 and File.exist?(Cfgsync::ClusterConf.file_path)) or File.exist?("/var/lib/pacemaker/cib/cib.xml")
    return JSON.generate({:node_available => false})
  end
  return JSON.generate({:node_available => true})
end

def remote_add_node(params,all = false)
  auto_start = false
  if params[:auto_start] and params[:auto_start] == "1"
    auto_start = true
  end

  if params[:new_nodename] != nil
    node = params[:new_nodename]
    if params[:new_ring1addr] != nil
      node += ',' + params[:new_ring1addr]
    end
    retval, output = add_node(node, all, auto_start)
  end

  if retval == 0
    return [200,JSON.generate([retval,get_corosync_conf([])])]
  end

  return [400,output]
end

def remote_remove_nodes(params)
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
  stdout, stderr, retval = run_cmd(PCS, "cluster", "stop", *stop_params)
  if retval != 0
    return [400, stderr.join]
  end

  node_list.each {|node|
    retval, output = remove_node(node,true)
    out = out + output.join("\n")
  }
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
  if config.get_nodes($cluster_name) == nil or config.get_nodes($cluster_name).length == 0
    return [200,"No More Nodes"]
  end
  return out
end

def remote_remove_node(params)
  if params[:remove_nodename] != nil
    retval, output = remove_node(params[:remove_nodename])
  else
    return 400, "No nodename specified"
  end

  if retval == 0
    return JSON.generate([retval,get_corosync_conf([])])
  end

  return JSON.generate([retval,output])
end

def setup_cluster(params)
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
  stdout, stderr, retval = run_cmd(PCS, "cluster", "setup", "--enable", "--start", "--name",params[:clustername], *nodes_options)
  if retval != 0
    return [
      400,
      (stdout + [''] + stderr).collect { |line| line.rstrip() }.join("\n")
    ]
  end
  return 200
end

def create_cluster(params)
  if set_corosync_conf(params)
    cluster_start(params)
  else
    return "Failed"
  end
end

def node_status(params)
  if params[:node] and params[:node] != '' and params[:node] !=
    $cur_node_name and !params[:redirected]
    return send_request_with_token(
      params[:node],
      'status?redirected=1',
      false,
      params.select { |k,_|
        [:version, :operations].include?(k)
      }
    )
  end

  cib_dom = get_cib_dom
  crm_dom = get_crm_mon_dom

  status = get_node_status(cib_dom)
  resources = get_resources(
    cib_dom,
    crm_dom,
    (params[:operations] and params[:operations] == '1')
  )

  node = ClusterEntity::Node.load_current_node(crm_dom)

  _,_,not_authorized_nodes = check_gui_status_of_nodes(
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
  node.attr.each { |v|
    node_attr[v.name.to_sym] = v.value
  }

  old_status = {
    :uptime => node.uptime,
    :corosync => node.corosync,
    :pacemaker => node.pacemaker,
    :cman => node.cman,
    :corosync_enabled => node.corosync_enabled,
    :pacemaker_enabled => node.pacemaker_enabled,
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
    :fence_levels => node.fence_levels,
    :need_ring1_address => status[:need_ring1_address],
    :is_cman_with_udpu_transport => status[:is_cman_with_udpu_transport],
    :acls => status[:acls],
    :username => status[:username]
  }

  return JSON.generate(old_status)
end

def status_all(params, nodes = [], dont_update_config=false)
  if nodes == nil
    return JSON.generate({"error" => "true"})
  end

  final_response = {}
  threads = []
  nodes.each {|node|
    threads << Thread.new {
      code, response = send_request_with_token(node, 'status')
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
    config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
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
      return status_all(params, node_list, true)
    end
  end
  $logger.debug("NODE LIST: " + node_list.inspect)
  return JSON.generate(final_response)
end

def clusters_overview()
  cluster_map = {}
  threads = []
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
  config.clusters.each { |cluster|
    threads << Thread.new {
      overview_cluster = nil
      online, offline, not_authorized_nodes = check_gui_status_of_nodes(
        get_cluster_nodes(cluster.name),
        false,3
      )
      not_supported = false
      cluster_nodes_auth = (online + offline).uniq
      cluster_nodes_all = (cluster_nodes_auth + not_authorized_nodes).uniq
      nodes_not_in_cluster = []
      for node in cluster_nodes_auth
        code, response = send_request_with_token(
          node, 'cluster_status', true, {}, true, nil, 15
        )
        if code == 404
          not_supported = true
          next
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
          'error_list' => !not_supported ?
            [{:message=>'Unable to connect to cluster.'}] : [],
          'warning_list' => not_supported ?
            [{:message=>"Cluster is running old version of pcs/pcsd which " +
               "doesn't provide data for dashboard."}] : [],
          'status' => 'unknown',
          'node_list' => get_default_node_list(cluster.name),
          'resource_list' => []
        }
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
  threads.each { |t| t.join }

  # update clusters in PCSConfig
  not_current_data = false
  config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
  cluster_map.each { |cluster, values|
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

def get_default_node_list(clustername)
  nodes = get_cluster_nodes clustername
  node_list = []
  nodes.each { |node|
    node_list << {
        "error_list" => [],
        "warning_list" => [],
        "status" => "unknown",
        "quorum" => false,
        "name" => node
    }
  }
  return node_list
end

def auth(params)
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
      pcs_auth(node_list, params['username'], params['password'], params["force"] == "1")
    end
  end
  return token
end

# If we get here, we're already authorized
def check_auth(params)
  if params.include?("check_auth_only")
    return [200, "{\"success\":true}"]
  end
  return JSON.generate({
    'success' => true,
    'node_list' => get_token_node_list,
  })
end

def resource_status(params)
  resource_id = params[:resource]
  @resources,@groups = getResourcesGroups
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

def resource_stop(params)
  stdout, stderr, retval = run_cmd(PCS,"resource","disable", params[:resource])
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

def resource_cleanup(params)
  stdout, stderr, retval = run_cmd(PCS,"resource","cleanup", params[:resource])
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

def resource_start(params)
  stdout, stderr, retval = run_cmd(PCS,"resource","enable", params[:resource])
  if retval == 0
    return JSON.generate({"success" => "true"})
  else
    return JSON.generate({"error" => "true", "stdout" => stdout, "stderror" => stderr})
  end
end

def resource_form(params)
  cib_dom = get_cib_dom
  @cur_resource = get_resource_by_id(params[:resource], cib_dom)
  @groups = get_resource_groups(cib_dom)
  @version = params[:version]

  if @cur_resource.instance_of?(ClusterEntity::Primitive) and !@cur_resource.stonith
    @cur_resource_group = @cur_resource.get_group
    @cur_resource_clone = @cur_resource.get_clone
    @cur_resource_ms = @cur_resource.get_master
    @resource = ResourceAgent.new(@cur_resource.agentname)
    if @cur_resource.provider == 'heartbeat'
      @resource.required_options, @resource.optional_options, @resource.info = getResourceMetadata(HEARTBEAT_AGENTS_DIR + @cur_resource.type)
    elsif @cur_resource.provider == 'pacemaker'
      @resource.required_options, @resource.optional_options, @resource.info = getResourceMetadata(PACEMAKER_AGENTS_DIR + @cur_resource.type)
    end
    @existing_resource = true
    if @resource
      erb :resourceagentform
    else
      "Can't find resource"
    end
  else
    "Resource #{params[:resource]} doesn't exist"
  end
end

def fence_device_form(params)
  @cur_resource = get_resource_by_id(params[:resource], get_cib_dom)

  if @cur_resource.instance_of?(ClusterEntity::Primitive) and @cur_resource.stonith
    @resource_agents = getFenceAgents(@cur_resource.agentname)
    @existing_resource = true
    @fenceagent = @resource_agents[@cur_resource.type]
    erb :fenceagentform
  else
    "Can't find fence device"
  end
end

# Creates resource if params[:resource_id] is not set
def update_resource (params)
  param_line = getParamList(params)
  if not params[:resource_id]
    out, stderr, retval = run_cmd(PCS, "resource", "create", params[:name], params[:resource_type],
	    *param_line)
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
    if params[:resource_group] and params[:resource_group] != ""
      run_cmd(PCS, "resource","group", "add", params[:resource_group],
	      params[:name])
      resource_group = params[:resource_group]
    end

    if params[:resource_clone] and params[:resource_clone] != ""
      name = resource_group ? resource_group : params[:name]
      run_cmd(PCS, "resource", "clone", name)
    elsif params[:resource_ms] and params[:resource_ms] != ""
      name = resource_group ? resource_group : params[:name]
      run_cmd(PCS, "resource", "master", name)
    end

    return JSON.generate({})
  end

  if param_line.length != 0
    # If it's a clone resource we strip off everything after the last ':'
    if params[:resource_clone]
      params[:resource_id].sub!(/(.*):.*/,'\1')
    end
    run_cmd(PCS, "resource", "update", params[:resource_id], *param_line)
  end

  if params[:resource_group]
    if params[:resource_group] == ""
      if params[:_orig_resource_group] != ""
	run_cmd(PCS, "resource", "group", "remove", params[:_orig_resource_group], params[:resource_id])
      end
    else
      run_cmd(PCS, "resource", "group", "add", params[:resource_group], params[:resource_id])
    end
  end

  if params[:resource_clone] and params[:_orig_resource_clone] == "false"
    run_cmd(PCS, "resource", "clone", params[:resource_id])
  end
  if params[:resource_ms] and params[:_orig_resource_ms] == "false"
    run_cmd(PCS, "resource", "master", params[:resource_id])
  end

  if params[:_orig_resource_clone] == "true" and not params[:resource_clone]
    run_cmd(PCS, "resource", "unclone", params[:resource_id].sub(/:.*/,''))
  end
  if params[:_orig_resource_ms] == "true" and not params[:resource_ms]
    run_cmd(PCS, "resource", "unclone", params[:resource_id].sub(/:.*/,''))
  end

  return JSON.generate({})
end

def update_fence_device (params)
  logger.info "Updating fence device"
  logger.info params
  param_line = getParamList(params)
  logger.info param_line

  if not params[:resource_id]
    out, stderr, retval = run_cmd(PCS, "stonith", "create", params[:name], params[:resource_type],
	    *param_line)
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
    return "{}"
  end

  if param_line.length != 0
    out, stderr, retval = run_cmd(PCS, "stonith", "update", params[:resource_id], *param_line)
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
  end
  return "{}"
end

def get_avail_resource_agents (params)
  agents = getResourceAgents()
  return JSON.generate(agents)
end

def get_avail_fence_agents(params)
  agents = getFenceAgents()
  return JSON.generate(agents)
end

def resource_metadata (params)
  return 200 if not params[:resourcename] or params[:resourcename] == ""
  resource_name = params[:resourcename][params[:resourcename].rindex(':')+1..-1]
  class_provider = params[:resourcename][0,params[:resourcename].rindex(':')]

  @resource = ResourceAgent.new(params[:resourcename])
  if class_provider == "ocf:heartbeat"
    @resource.required_options, @resource.optional_options, @resource.info = getResourceMetadata(HEARTBEAT_AGENTS_DIR + resource_name)
  elsif class_provider == "ocf:pacemaker"
    @resource.required_options, @resource.optional_options, @resource.info = getResourceMetadata(PACEMAKER_AGENTS_DIR + resource_name)
  end
  @new_resource = params[:new]
  @resources, @groups = getResourcesGroups
  
  erb :resourceagentform
end

def fence_device_metadata (params)
  return 200 if not params[:resourcename] or params[:resourcename] == ""
  @fenceagent = FenceAgent.new(params[:resourcename])
  @fenceagent.required_options, @fenceagent.optional_options, @fenceagent.advanced_options, @fenceagent.info = getFenceAgentMetadata(params[:resourcename])
  @new_fenceagent = params[:new]
  
  erb :fenceagentform
end

def remove_resource (params)
  force = params['force']
  no_error_if_not_exists = params.include?('no_error_if_not_exists')
  errors = ""
  params.each { |k,v|
    if k.index("resid-") == 0
      resid = k.gsub('resid-', '')
      command = [PCS, 'resource', 'delete', resid]
      command << '--force' if force
      out, errout, retval = run_cmd(*command)
      if retval != 0
        unless out.index(" does not exist.") != -1 and no_error_if_not_exists  
          errors += errout.join(' ').strip + "\n"
        end
      end
    end
  }
  errors.strip!
  if errors == ""
    return 200
  else
    logger.info("Remove resource errors:\n"+errors)
    return [400, errors]
  end
end

def add_fence_level_remote(params)
  retval, stdout, stderr = add_fence_level(params["level"], params["devices"], params["node"], params["remove"])
  if retval == 0
    return [200, "Successfully added fence level"]
  else
    return [400, stderr]
  end
end

def add_node_attr_remote(params)
  retval = add_node_attr(params["node"], params["key"], params["value"])
  if retval == 0
    return [200, "Successfully added attribute to node"]
  else
    return [400, "Error adding attribute to node"]
  end
end

def add_acl_role_remote(params)
  retval = add_acl_role(params["name"], params["description"])
  if retval == ""
    return [200, "Successfully added ACL role"]
  else
    return [
      400,
      retval.include?("cib_replace failed") ? "Error adding ACL role" : retval
    ]
  end
end

def remove_acl_roles_remote(params)
  errors = ""
  params.each { |name, value|
    if name.index("role-") == 0
      out, errout, retval = run_cmd(
        PCS, "acl", "role", "delete", value.to_s, "--autodelete"
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

def add_acl_remote(params)
  if params["item"] == "permission"
    retval = add_acl_permission(
      params["role_id"], params["type"], params["xpath_id"], params["query_id"]
    )
  elsif (params["item"] == "user") or (params["item"] == "group")
    retval = add_acl_usergroup(
      params["role_id"], params["item"], params["usergroup"]
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

def remove_acl_remote(params)
  if params["item"] == "permission"
    retval = remove_acl_permission(params["acl_perm_id"])
  elsif params["item"] == "usergroup"
    retval = remove_acl_usergroup(params["role_id"],params["usergroup_id"])
  else
    retval = "Error: Unknown removal request"
  end

  if retval == ""
    return [200, "Successfully removed permission from role"]
  else
    return [400, retval]
  end
end

def add_meta_attr_remote(params)
  retval = add_meta_attr(params["res_id"], params["key"],params["value"])
  if retval == 0
    return [200, "Successfully added meta attribute"]
  else
    return [400, "Error adding meta attribute"]
  end
end

def add_constraint_remote(params)
  case params["c_type"]
  when "loc"
    retval, error = add_location_constraint(
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
      resA, resB, score, params["force"], !params['disable_autocorrect']
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

def add_constraint_rule_remote(params)
  if params["c_type"] == "loc"
    retval, error = add_location_constraint_rule(
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

def add_constraint_set_remote(params)
  case params["c_type"]
  when "ord"
    retval, error = add_order_set_constraint(
      params["resources"].values, params["force"], !params['disable_autocorrect']
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

def remove_constraint_remote(params)
  if params[:constraint_id]
    retval = remove_constraint(params[:constraint_id])
    if retval == 0
      return "Constraint #{params[:constraint_id]} removed"
    else
      return [400, "Error removing constraint: #{params[:constraint_id]}"]
    end
  else
    return [400,"Bad Constraint Options"]
  end
end

def remove_constraint_rule_remote(params)
  if params[:rule_id]
    retval = remove_constraint_rule(params[:rule_id])
    if retval == 0
      return "Constraint rule #{params[:rule_id]} removed"
    else
      return [400, "Error removing constraint rule: #{params[:rule_id]}"]
    end
  else
    return [400, "Bad Constraint Rule Options"]
  end
end

def add_group(params)
  rg = params["resource_group"]
  resources = params["resources"]
  output, errout, retval = run_cmd(PCS, "resource", "group", "add", rg, *(resources.split(" ")))
  if retval == 0
    return 200
  else
    return 400, errout
  end
end

def update_cluster_settings(params)
  settings = params["config"]
  hidden_settings = params["hidden"]
  output = ""
  hidden_settings.each{|name,val|
    found = false
    settings.each{|name2,val2|
      if name == name2
	found = true
	break
      end
    }
    if not found
      settings[name] = val
    end
  }

  settings.each{|name,val|
    if name == "enable-acl"
      run_cmd(PCS, "property", "set", name + "=" + val, "--force")
    else
      run_cmd(PCS, "property", "set", name + "=" + val)
    end
  }
  return [200, "Update Successful"]
end

def cluster_destroy(params)
  out, errout, retval = run_cmd(PCS, "cluster", "destroy")
  if retval == 0
    return [200, "Successfully destroyed cluster"]
  else
    return [400, "Error destroying cluster:\n#{out}\n#{errout}\n#{retval}\n"]
  end
end

def get_wizard(params)
  wizard = PCSDWizard.getWizard(params["wizard"])
  if wizard != nil
    return erb wizard.collection_page
  else
    return "Error finding Wizard - #{params["wizard"]}"
  end
end

def wizard_submit(params)
  wizard = PCSDWizard.getWizard(params["wizard"])
  if wizard != nil
    return erb wizard.process_responses(params)
  else
    return "Error finding Wizard - #{params["wizard"]}"
  end

end

def get_local_node_id
  if ISRHEL6
    out, errout, retval = run_cmd(COROSYNC_CMAPCTL, "cluster.cman")
    if retval != 0
      return ""
    end
    match = /cluster\.nodename=(.*)/.match(out.join("\n"))
    if not match
      return ""
    end
    local_node_name = match[1]
    out, errout, retval = run_cmd(CMAN_TOOL, "nodes", "-F", "id", "-n", local_node_name)
    if retval != 0
      return ""
    end
    return out[0].strip()
  end
  out, errout, retval = run_cmd(COROSYNC_CMAPCTL, "-g", "runtime.votequorum.this_node_id")
  if retval != 0
    return ""
  else
    return out[0].split(/ = /)[1].strip()
  end
end

def need_ring1_address?
  out, errout, retval = run_cmd(COROSYNC_CMAPCTL)
  if retval != 0
    return false
  else
    udpu_transport = false
    rrp = false
    out.each { |line|
      # support both corosync-objctl and corosync-cmapctl format
      if /^\s*totem\.transport(\s+.*)?=\s*udpu$/.match(line)
        udpu_transport = true
      elsif /^\s*totem\.rrp_mode(\s+.*)?=\s*(passive|active)$/.match(line)
        rrp = true
      end
    }
    # on rhel6 ring1 address is required regardless of transport
    # it has to be added to cluster.conf in order to set up ring1
    # in corosync by cman
    return ((ISRHEL6 and rrp) or (rrp and udpu_transport))
  end
end

def is_cman_with_udpu_transport?
  if not ISRHEL6
    return false
  end
  begin
    cluster_conf = Cfgsync::ClusterConf.from_file().text()
    conf_dom = REXML::Document.new(cluster_conf)
    conf_dom.elements.each("cluster/cman") { |elem|
      if elem.attributes["transport"].downcase == "udpu"
        return true
      end
    }
  rescue
    return false
  end
  return false
end

def auth_nodes(params)
  retval = {}
  params.each{|node|
    if node[0].end_with?"-pass" and node[0].length > 5
      nodename = node[0][0..-6]
      if params.has_key?("all")
        pass = params["pass-all"]
      else
        pass = node[1]
      end
      result, sync_successful, _, _ = pcs_auth(
        [nodename], SUPERUSER, pass, true, true
      )
      if not sync_successful
        retval[nodename] = 1
      else
        node_status = result[nodename]['status']
        if 'ok' == node_status or 'already_authorized' == node_status
          retval[nodename] = 0
        else
          retval[nodename] = 1
        end
      end
    end
  }
  return [200, JSON.generate(retval)]
end

def get_tokens(params)
  return [200, JSON.generate(read_tokens)]
end

def get_cluster_tokens(params)
  on, off = get_nodes
  nodes = on + off
  nodes.uniq!
  return [200, JSON.generate(get_tokens_of_nodes(nodes))]
end

def save_tokens(params)
  new_tokens = {}

  params.each{|nodes|
    if nodes[0].start_with?"node:" and nodes[0].length > 5
      node = nodes[0][5..-1]
      token = nodes[1]
      new_tokens[node] = token
    end
  }

  tokens_cfg = Cfgsync::PcsdTokens.from_file('')
  sync_successful, sync_responses = Cfgsync::save_sync_new_tokens(
    tokens_cfg, new_tokens, get_corosync_nodes(), $cluster_name
  )

  if sync_successful
    return [200, JSON.generate(read_tokens())]
  else
    return [400, "Cannot update tokenfile."]
  end
end

def add_node_to_cluster(params)
  clustername = params["clustername"]
  new_node = params["new_nodename"]
  tokens = read_tokens

  if not tokens.include? new_node
    return [400, "New node is not authenticated."]
  end

  # Save the new node token on all nodes in a cluster the new node is beeing
  # added to. Send the token to one node and let the cluster nodes synchronize
  # it by themselves.
  token_data = {"node:#{new_node}" => tokens[new_node]}
  retval, out = send_cluster_request_with_token(
    clustername, '/save_tokens', true, token_data
  )
  # If the cluster runs an old pcsd which doesn't support /save_tokens,
  # ignore 404 in order to not prevent the node to be added.
  if retval != 404 and retval != 200
    return [400, 'Failed to save the token of the new node in target cluster.']
  end

  retval, out = send_cluster_request_with_token(clustername, "/add_node_all", true, params)
  if retval != 200
    return [400, "Failed to add new node '#{new_node}' into cluster '#{clustername}': #{out}"]
  end

  return [200, "Node added successfully."]
end

def fix_auth_of_cluster(params)
  if not params["clustername"]
    return [400, "cluster name not defined"]
  end

  clustername = params["clustername"]
  nodes = get_cluster_nodes(clustername)
  tokens_data = add_prefix_to_keys(get_tokens_of_nodes(nodes), "node:")

  retval, out = send_cluster_request_with_token(
    clustername, "/save_tokens", true, tokens_data
  )
  if retval == 404
    return [400, "Old version of PCS/PCSD is runnig on cluster nodes. Fixing authentication is not supported."]
  elsif retval != 200
    return [400, "Authentication failed."]
  end
  return [200, "Auhentication of nodes in cluster should be fixed."]
end

def resource_master(params)
  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end
  _, stderr, retval = run_cmd(
    PCS, 'resource', 'master', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to create master/slave resource from ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_change_group(params)
  if params[:resource_id].nil? or params[:group_id].nil?
    return [400, 'resource_id and group_id have to be specified.']
  end
  if params[:group_id].empty?
    if params[:old_group_id]
      _, stderr, retval = run_cmd(
        PCS, 'resource', 'group', 'remove', params[:old_group_id],
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
  _, stderr, retval = run_cmd(
    PCS, 'resource', 'group', 'add', params[:group_id], params[:resource_id]
  )
  if retval != 0
    return [400, "Unable to add resource '#{params[:resource_id]}' to " +
      "group '#{params[:group_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_ungroup(params)
  unless params[:group_id]
    return [400, 'group_id has to be specified.']
  end
  
  _, stderr, retval = run_cmd(
    PCS, 'resource', 'ungroup', params[:group_id]
  )
  if retval != 0
    return [400, 'Unable to ungroup group ' +
      "'#{params[:group_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_clone(params)
  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end
  
  _, stderr, retval = run_cmd(
    PCS, 'resource', 'clone', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to create clone resource from ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end

def resource_unclone(params)
  unless params[:resource_id]
    return [400, 'resource_id has to be specified.']
  end

  _, stderr, retval = run_cmd(
    PCS, 'resource', 'unclone', params[:resource_id]
  )
  if retval != 0
    return [400, 'Unable to unclone ' +
      "'#{params[:resource_id]}': #{stderr.join('')}"
    ]
  end
  return 200
end
