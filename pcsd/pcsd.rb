require 'sinatra'
require 'rexml/document'
require 'openssl'
require 'logger'
require 'thread'
require 'fileutils'
require 'cgi'

require 'bootstrap.rb'
require 'resource.rb'
require 'remote.rb'
require 'cluster.rb'
require 'config.rb'
require 'pcs.rb'
require 'auth.rb'
require 'cfgsync.rb'
require 'permissions.rb'

use Rack::CommonLogger

set :app_file, __FILE__
set :logging, false
set :static, false

def __msg_cluster_name_already_used(cluster_name)
  return "The cluster name '#{cluster_name}' has already been added. You may not add two clusters with the same name."
end

def __msg_node_name_already_used(node_name, cluster_name)
  return "The node '#{node_name}' is already a part of the '#{cluster_name}' cluster. You may not add a node to two different clusters."
end

def __msg_sync_conflict_detected(please_repeat=nil)
  if not please_repeat
    please_repeat = 'Please repeat the last action if appropriate.'
  end
  return "Configuration conflict detected.\n\nSome nodes had a newer configuration than the local node. Local node's configuration was updated. #{please_repeat}"
end

def __msg_sync_nodes_error(node_name_list)
  return "Unable to save settings on local cluster node(s) #{node_name_list.join(', ')}. Make sure pcsd is running on the nodes and the nodes are authorized."
end

def getAuthUser()
  return {
    :username => Thread.current[:tornado_username],
    :usergroups => Thread.current[:tornado_groups],
  }
end

before do
  @auth_user = getAuthUser()
  $cluster_name, $cluster_uuid = get_cluster_name_and_uuid()
  if PCSD_RESTART_AFTER_REQUESTS > 0
    $request_counter += 1
    # Even though Puma is multi-threaded, we don't need to lock here since GVL
    # is only released during blocking I/O operations
    if $request_counter >= PCSD_RESTART_AFTER_REQUESTS
      $request_counter = 0
      # Start Puma hot restart
      $logger.debug('Requested a restart of Ruby server')
      Process.kill("USR2", Process.pid)
    end
  end
end

configure do
  PCS = get_pcs_path()
  PCS_INTERNAL = get_pcs_internal_path()
  $logger = configure_logger()
  early_log($logger)
  capabilities, capabilities_pcsd = get_capabilities($logger)
  CAPABILITIES = capabilities.freeze
  CAPABILITIES_PCSD = capabilities_pcsd.freeze
end

def run_cfgsync
  node_connected = true
  if Cfgsync::ConfigSyncControl.sync_thread_allowed?()
    $logger.info('Config files sync started')
    begin
      # do not sync if this host is not in a cluster
      cluster_name = get_cluster_name()
      cluster_nodes = get_corosync_nodes_names()
      if cluster_name and !cluster_name.empty?() and cluster_nodes and cluster_nodes.count > 1
        $logger.debug('Config files sync fetching')
        fetcher = Cfgsync::ConfigFetcher.new(
          PCSAuth.getSuperuserAuth(),
          Cfgsync::get_cfg_classes(),
          cluster_nodes,
          cluster_name
        )
        cfgs_to_save, _, node_connected = fetcher.fetch()
        cfgs_to_save.each { |cfg_to_save|
          cfg_to_save.save()
        }
        $logger.info('Config files sync finished')
      else
        $logger.info(
          'Config files sync skipped, this host does not seem to be in ' +
          'a cluster of at least 2 nodes'
        )
      end
    rescue => e
      $logger.warn("Config files sync exception: #{e}")
    end
  else
    $logger.info('Config files sync is disabled or paused, skipping')
  end
  if node_connected
    return Cfgsync::ConfigSyncControl.sync_thread_interval()
  else
    return Cfgsync::ConfigSyncControl.sync_thread_interval_previous_not_connected()
  end
end

get '/remote/?:command?' do
  return remote(params, request, @auth_user)
end

post '/remote/?:command?' do
  return remote(params, request, @auth_user)
end

post '/run_pcs' do
  std_in = params['stdin'] || nil
  begin
    command = JSON.parse(params['command'] || '[]')
    options = JSON.parse(params['options'] || '[]')
  rescue JSON::ParserError
    result = {
      'status' => 'error',
      'data' => {},
    }
    return JSON.pretty_generate(result)
  end
  # Do not reveal potentially sensitive information: remove --debug and all its
  # prefixes since getopt parser in pcs considers them equal to --debug.
  debug_items = ["--de", "--deb", "--debu", "--debug"]
  options_sanitized = []
  options.each { |item|
    options_sanitized << item unless debug_items.include?(item)
  }

  allowed_commands = {
    ['cluster', 'auth', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    # runs on the local node, check permissions
    ['cluster', 'corosync'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
    # runs on a remote node which checks permissions by itself
    ['cluster', 'corosync', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['cluster', 'destroy', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::FULL,
    },
    # runs on the local node, check permissions
    ['cluster', 'disable'] => {
      'only_superuser' => false,
      'permissions' => Permissions::WRITE,
    },
    # runs on a remote node which checks permissions by itself
    ['cluster', 'disable', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    # runs on the local node, check permissions
    ['cluster', 'enable'] => {
      'only_superuser' => false,
      'permissions' => Permissions::WRITE,
    },
    # runs on a remote node which checks permissions by itself
    ['cluster', 'enable', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['cluster', 'node', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::FULL,
    },
    # TODO deprecated, remove command
    ['cluster', 'pcsd-status', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    # runs on the local node, check permissions
    ['cluster', 'start'] => {
      'only_superuser' => false,
      'permissions' => Permissions::WRITE,
    },
    # runs on a remote node which checks permissions by itself
    ['cluster', 'start', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    # runs on the local node, check permissions
    ['cluster', 'stop'] => {
      'only_superuser' => false,
      'permissions' => Permissions::WRITE,
    },
    # runs on a remote node which checks permissions by itself
    ['cluster', 'stop', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['cluster', 'sync', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::FULL,
    },
    ['config', 'restore', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::FULL,
    },
    ['host', 'auth', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['host', 'deauth', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['pcsd', 'deauth', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['pcsd', 'status', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['pcsd', 'sync-certificates', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::FULL,
    },
    ['quorum', 'device', 'status', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
    ['quorum', 'status', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
    ['status'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
    ['status', 'corosync', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
    ['status', 'pcsd', '...'] => {
      'only_superuser' => false,
      'permissions' => nil,
    },
    ['status', 'quorum', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
    ['status', 'status', '...'] => {
      'only_superuser' => false,
      'permissions' => Permissions::READ,
    },
  }
  allowed = false
  command_settings = {}
  allowed_commands.each { |allowed_cmd, cmd_settings|
    if command == allowed_cmd \
      or \
      (allowed_cmd[-1] == '...' and allowed_cmd[0..-2] == command[0..(allowed_cmd.length - 2)])
      then
        allowed = true
        command_settings = cmd_settings
        break
    end
  }
  if !allowed
    result = {
      'status' => 'bad_command',
      'data' => {},
    }
    return JSON.pretty_generate(result)
  end

  if command_settings['only_superuser']
    if not allowed_for_superuser(@auth_user)
      return 403, 'Permission denied'
    end
  end
  if command_settings['permissions']
    if not allowed_for_local_cluster(@auth_user, command_settings['permissions'])
      return 403, 'Permission denied'
    end
  end

  runner_options = {}
  runner_options['stdin'] = std_in if std_in
  std_out, std_err, retval = run_cmd_options(
    @auth_user, runner_options, PCS, *options_sanitized, '--', *command
  )
  result = {
    'status' => 'ok',
    'data' => {
      'stdout' => std_out.join(""),
      'stderr' => std_err.join(""),
      'code' => retval,
    },
  }
  return JSON.pretty_generate(result)
end

post '/manage/existingcluster' do
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  node = params['node-name']
  code, result = send_request_with_token(
    PCSAuth.getSuperuserAuth(), node, 'status', false, {:version=>'2'}
  )
  begin
    status = JSON.parse(result)
  rescue JSON::ParserError
    return 400, "Unable to communicate with remote pcsd on node '#{node}'."
  end

  if status.has_key?("corosync_offline") and
    status.has_key?("corosync_online") then
    nodes = status["corosync_offline"] + status["corosync_online"]

    if status["cluster_name"] == ''
      return 400, "The node, '#{node}', does not currently have a cluster
 configured.  You must create a cluster using this node before adding it to pcsd."
    end

    if pcs_config.is_cluster_name_in_use(status['cluster_name'])
      return 400, __msg_cluster_name_already_used(status['cluster_name'])
    end

    # auth begin
    new_hosts, warning_messages = pcs_compatibility_layer_get_cluster_known_hosts(
      status['cluster_name'], node
    )
    if not new_hosts.empty?
      no_conflict, sync_responses = Cfgsync::save_sync_new_known_hosts(
        new_hosts, [], get_corosync_nodes_names(), $cluster_name
      )
      sync_notauthorized_nodes, sync_failed_nodes = (
        Cfgsync::get_failed_nodes_from_sync_responses(sync_responses)
      )
      sync_all_failures = (sync_notauthorized_nodes + sync_failed_nodes).sort
      if not sync_all_failures.empty?
        return 400, __msg_sync_nodes_error(sync_all_failures)
      end
      if not no_conflict
        return 400, __msg_sync_conflict_detected()
      end
    end
    #auth end

    pcs_config.clusters << Cluster.new(status["cluster_name"], nodes)

    sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
    no_conflict, sync_responses = Cfgsync::save_sync_new_version(
      sync_config, get_corosync_nodes_names(), $cluster_name, true
    )
    sync_notauthorized_nodes, sync_failed_nodes = (
      Cfgsync::get_failed_nodes_from_sync_responses(sync_responses)
    )
    sync_all_failures = (sync_notauthorized_nodes + sync_failed_nodes).sort
    if not sync_all_failures.empty?
      return 400, __msg_sync_nodes_error(sync_all_failures)
    end
    if not no_conflict
      return 400, __msg_sync_conflict_detected()
    end
    return 200, warning_messages.join("\n\n")
  else
    return 400, "Unable to communicate with remote pcsd on node '#{node}'."
  end
end

### urls related to creating a new cluster - begin
#
# Creating a new cluster consists of several steps which are directed from js.
# Each url provides an action. The actions together orchestrated by js achieve
# creating a new cluster including various checks, the cluster setup itself and
# adding the new cluster into the gui.

# use case:
# - js is already authenticated to all future cluster nodes
# - js calls this url to send its tokens to a future cluster node
# - later, js will instruct that node to setup the cluster
# - the node will distribute the tokens in the cluster
post '/manage/send-known-hosts-to-node' do
  auth_user = getAuthUser()
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied.'
  end
  return pcs_compatibility_layer_known_hosts_add(
    auth_user, false, params[:target_node], params[:node_names]
  )
end

# use case:
# - js asks us if specified cluster name and/or node names are available
get '/manage/can-add-cluster-or-nodes' do
  # This is currently used form cluster setup and node add, both of which
  # require hacluster user anyway. If needed to be used anywhere else, consider
  # if hacluster should be required.
  auth_user = getAuthUser()
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied.'
  end

  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  errors = []

  if params.include?(:cluster)
    if pcs_config.is_cluster_name_in_use(params[:cluster])
      errors << __msg_cluster_name_already_used(params[:cluster])
    end
  end

  if params.include?(:node_names)
    params[:node_names].each { |node_name|
      cluster_name = pcs_config.get_nodes_cluster(node_name)
      if cluster_name
        errors << __msg_node_name_already_used(node_name, cluster_name)
      end
    }
  end

  unless errors.empty?
    return 400, errors.join("\n")
  end
  return 200, ""
end

post '/manage/api/v1/cluster-setup' do
  auth_user = getAuthUser()
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied.'
  end
  if params[:target_node] and params[:setup_data]
    return send_request_with_token(
      auth_user,
      params[:target_node],
      '/api/v1/cluster-setup/v1',
      true, # post
      {}, # data - useless when there are raw_data
      false, # remote
      params[:setup_data] # raw_data
    )
  end
end



# use case:
# - js instructs us to add the just created cluster to our list of clusters
post '/manage/remember-cluster' do
  auth_user = getAuthUser()
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied.'
  end
  no_conflict = false
  sync_responses = {}
  2.times {
    # Add the new cluster to our config and publish the config.
    # If this host is a node of the new cluster, another node may send its own
    # PcsdSettings. To handle it we just need to reload the config, as we are
    # waiting for the request to finish, so no locking is needed.
    # If we are in a different cluster we just try twice to update the config,
    # dealing with any updates in between.
    pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
    pcs_config.clusters << Cluster.new(params[:cluster_name], params[:nodes])
    sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
    no_conflict, sync_responses = Cfgsync::save_sync_new_version(
      sync_config, get_corosync_nodes_names(), $cluster_name, true
    )
    break if no_conflict
  }
  sync_notauthorized_nodes, sync_failed_nodes = (
    Cfgsync::get_failed_nodes_from_sync_responses(sync_responses)
  )
  sync_all_failures = (sync_notauthorized_nodes + sync_failed_nodes).sort
  if not sync_all_failures.empty?
    return 400, __msg_sync_nodes_error(sync_all_failures)
  end
  if not no_conflict
    return 400, __msg_sync_conflict_detected(
      'Please add the cluster manually if appropriate.'
    )
  end
end

### urls related to creating a new cluster - end

post '/manage/removecluster' do
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  params.each { |k,v|
    if k.start_with?("clusterid-")
      pcs_config.remove_cluster(k.sub("clusterid-",""))
    end
  }
  sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
  no_conflict, sync_responses = Cfgsync::save_sync_new_version(
    sync_config, get_corosync_nodes_names(), $cluster_name, true
  )
  sync_notauthorized_nodes, sync_failed_nodes = (
    Cfgsync::get_failed_nodes_from_sync_responses(sync_responses)
  )
  sync_all_failures = (sync_notauthorized_nodes + sync_failed_nodes).sort
  if not sync_all_failures.empty?
    return 400, __msg_sync_nodes_error(sync_all_failures)
  end
  if not no_conflict
    return 400, __msg_sync_conflict_detected()
  end
end

get '/manage/check_auth_against_nodes' do
  auth_user = getAuthUser()
  node_list = []
  if params[:node_list].is_a?(Array)
    node_list = params[:node_list]
  end
  node_results = {}
  online, offline, notauthorized = is_auth_against_nodes(auth_user, node_list)
  online.each { |node|
    node_results[node] = 'Online'
  }
  offline.each { |node|
    node_results[node] = 'Offline'
  }
  notauthorized.each { |node|
    node_results[node] = 'Unable to authenticate'
  }
  return JSON.generate(node_results)
end

post '/manage/auth_gui_against_nodes' do
  auth_user = getAuthUser()
  threads = []
  new_hosts = {}
  node_auth_error = {}

  data = JSON.parse(params.fetch('data_json'))
  data.fetch('nodes').each { |node_name, node_data|
    threads << Thread.new(Thread.current[:pcsd_logger_container]) { |logger|
      Thread.current[:pcsd_logger_container] = logger
      dest_list = node_data.fetch('dest_list')
      addr = dest_list.fetch(0).fetch('addr')
      port = dest_list.fetch(0).fetch('port')
      if addr == ''
        addr = node_name
      end
      if port == ''
        port = PCSD_DEFAULT_PORT
      end
      request_data = {
        :username => SUPERUSER,
        :password => node_data.fetch('password'),
      }
      node_auth_error[node_name] = 1
      code, response = send_request(
        auth_user, addr, port, 'auth', true, request_data, true
      )
      if 200 == code
        token = response.strip
        if not token.empty?
          new_hosts[node_name] = PcsKnownHost.new(
            node_name, token, [{'addr' => addr, 'port' => port}]
          )
          node_auth_error[node_name] = 0
        end
      end
    }
  }
  threads.each { |t| t.join }

  plaintext_error = []
  local_cluster_node_auth_error = {}
  if not new_hosts.empty?
    sync_successful, sync_responses = Cfgsync::save_sync_new_known_hosts(
      new_hosts.values(), [], get_corosync_nodes_names(), $cluster_name
    )

    if not sync_successful
      return [
        200,
        JSON.generate({
          'plaintext_error' => __msg_sync_conflict_detected()
        })
      ]
    end

    # If we cannot save tokens to local cluster nodes, let the user auth them
    # as well. Otherwise the user gets into a loop:
    # 1 the password for the new node is correct and a token is obtained
    # 2 the token for the new node cannot be saved in the local cluster (due
    #   to local cluster nodes not authenticated)
    # 3 the gui asks for authenticating the new node
    # 4 goto 1
    sync_notauthorized_nodes, sync_failed_nodes = (
      Cfgsync::get_failed_nodes_from_sync_responses(sync_responses)
    )
    if not sync_failed_nodes.empty?
      plaintext_error << __msg_sync_nodes_error(sync_failed_nodes)
    end
    sync_notauthorized_nodes.each { |node_name|
      local_cluster_node_auth_error[node_name] = 1
    }
  end

  return [
    200,
    JSON.generate({
      'node_auth_error' => node_auth_error,
      # only nodes where new configs cannot be synchronized due to them not
      # being authenticated
      'local_cluster_node_auth_error' => local_cluster_node_auth_error,
      'plaintext_error' => plaintext_error.join("\n\n")
    })
  ]
end

get '/imported-cluster-list' do
  imported_cluster_list(params, request, getAuthUser())
end

post '/managec/:cluster/permissions_save/?' do
  auth_user = getAuthUser()
  new_params = {
    'json_data' => JSON.generate(params)
  }
  return send_cluster_request_with_token(
    auth_user, params[:cluster], "set_permissions", true, new_params
  )
end

get '/managec/:cluster/cluster_status' do
  auth_user = getAuthUser()
  cluster_status_gui(auth_user, params[:cluster])
end

get '/managec/:cluster/get_resource_agent_metadata' do
  auth_user = getAuthUser()
  cluster = params[:cluster]
  resource_agent = params[:agent]
  code, out = send_cluster_request_with_token(
    auth_user,
    cluster,
    'get_resource_agent_metadata',
    false,
    {:resource_agent => resource_agent}
  )
  return [code, out]
end

get '/managec/:cluster/get_fence_agent_metadata' do
  auth_user = getAuthUser()
  cluster = params[:cluster]
  fence_agent = params[:agent]
  code, out = send_cluster_request_with_token(
    auth_user,
    cluster,
    'get_fence_agent_metadata',
    false,
    {:fence_agent => fence_agent}
  )
  return [code, out]
end

post '/managec/:cluster/fix_auth_of_cluster' do
  clustername = params[:cluster]
  unless clustername
    return [400, "cluster name not defined"]
  end

  retval = pcs_compatibility_layer_known_hosts_add(
    PCSAuth.getSuperuserAuth(), true, clustername, get_cluster_nodes(clustername)
  )
  if retval == 'not_supported'
    return [400, "Old version of PCS/PCSD is running on cluster nodes. Fixing authentication is not supported. Use 'pcs host auth' command to authenticate the nodes."]
  elsif retval == 'error'
    return [400, "Authentication failed."]
  end
  return [200, "Auhentication of nodes in cluster should be fixed."]
end

post '/managec/:cluster/send-known-hosts' do
  # send
  #   data (token, dest_list) of nodes in params[:node_names]
  #   to nodes that belongs to a cluster with name params[:cluster]
  auth_user = getAuthUser()
  if not allowed_for_superuser(auth_user)
    return 403, 'Permission denied.'
  end
  return pcs_compatibility_layer_known_hosts_add(
    auth_user, true, params[:cluster], params[:node_names]
  )
end

# This may be useful for adding node to pcs-0.9.x running cluster
post '/managec/:cluster/add_node_to_cluster' do
  auth_user = getAuthUser()
  clustername = params[:cluster]
  new_node = params["new_nodename"]

  known_hosts = get_known_hosts()
  if not known_hosts.include? new_node
    return [400, "New node is not authenticated."]
  end

  # Save the new node token on all nodes in a cluster the new node is being
  # added to. Send the token to one node and let the cluster nodes synchronize
  # it by themselves.
  retval = pcs_compatibility_layer_known_hosts_add(
    # new node doesn't have config with permissions yet
    PCSAuth.getSuperuserAuth(), true, clustername, [new_node]
  )
  # If the cluster runs an old pcsd which doesn't support adding known hosts,
  # ignore 404 in order to not prevent the node to be added.
  if retval != 'not_supported' and retval != 'success'
    return [400, 'Failed to save the token of the new node in the target cluster.']
  end

  retval, out = send_cluster_request_with_token(
    auth_user, clustername, "/add_node_all", true, params
  )
  if 403 == retval
    return [retval, out]
  end
  if retval != 200
    return [400, "Failed to add new node '#{new_node}' into cluster '#{clustername}': #{out}"]
  end

  return [200, "Node added successfully."]
end

def pcs_compatibility_layer_known_hosts_add(
  auth_user, is_cluster_request, target, host_list
)
  known_hosts = get_known_hosts().select { |name, obj|
    host_list.include?(name)
  }
  known_hosts_request_data = {}
  known_hosts.each { |host_name, host_obj|
    known_hosts_request_data[host_name] = {
      'dest_list' => host_obj.dest_list,
      'token' => host_obj.token,
    }
  }
  request_data = {
    'data_json' => JSON.generate(
      {
        'known_hosts_add' => known_hosts_request_data,
        'known_hosts_remove' => [],
      }
    ),
  }
  if is_cluster_request
    retval, _out = send_cluster_request_with_token(
      auth_user, target, '/known_hosts_change', true, request_data
    )
  else
    retval, _out = send_request_with_token(
      auth_user, target, '/known_hosts_change', true, request_data
    )
  end

  if retval == 200
    return 'success'
  end

  if retval == 404
    return 'not_supported'
  end
  return 'error'
end

def pcs_compatibility_layer_get_cluster_known_hosts(cluster_name, target_node)
  warning_messages = []
  known_hosts = []
  auth_user = PCSAuth.getSuperuserAuth()

  retval, out = send_request_with_token(
    auth_user, target_node, '/get_cluster_known_hosts'
  )
  if retval == 200
    begin
      JSON.parse(out).each { |name, data|
        known_hosts << PcsKnownHost.new(
          name,
          data.fetch('token'),
          data.fetch('dest_list')
        )
      }
    rescue => e
      $logger.error "Unable to parse the response of /get_cluster_known_hosts: #{e}"
      known_hosts = []
      warning_messages << (
        "Unable to automatically authenticate against cluster nodes: " +
        "cannot get authentication info from cluster '#{cluster_name}'"
      )
    end
  elsif retval == 404
    warning_messages << (
      "Unable to automatically authenticate against cluster nodes: " +
      "cluster '#{cluster_name}' is running an old version of pcs/pcsd"
    )
  else
    warning_messages << (
      "Unable to automatically authenticate against cluster nodes: " +
      "cannot get authentication info from cluster '#{cluster_name}'"
    )
  end

  return known_hosts, warning_messages
end

def pcs_0_10_6_get_avail_resource_agents(code, out)
  if code != 200
    return code, out
  end
  begin
    agent_map = {}
    JSON.parse(out).each { |agent_name, agent_data|
      if agent_data == {}
        new_data = get_resource_agent_name_structure(agent_name)
        if not new_data.nil?
          agent_map[agent_name] = new_data
        end
      else
        agent_map[agent_name] = agent_data
      end
    }
    return code, JSON.generate(agent_map)
  rescue
    return code, out
  end
end

post '/managec/:cluster/api/v1/:command' do
  auth_user = getAuthUser()
  if params[:cluster] and params[:command]
    return send_cluster_request_with_token(
      auth_user,
      params[:cluster],
      '/api/v1/' + params[:command] + '/v1',
      true, # post
      {}, # data - useless when there are raw_data
      false, # remote
      request.env['rack.input'].read # raw_data
    )
  end
end

get '/managec/:cluster/api/v1/:command' do
  auth_user = getAuthUser()
  if params[:cluster] and params[:command]
    return send_cluster_request_with_token(
      auth_user,
      params[:cluster],
      '/api/v1/' + params[:command] + '/v1',
      false, # post
      {}, # data - useless when there are raw_data
      false, # remote
      request.env['rack.input'].read # raw_data
    )
  end
end

post '/managec/:cluster/?*' do
  auth_user = getAuthUser()
  raw_data = request.env["rack.input"].read
  if params[:cluster]
    request = "/" + params[:splat].join("/")

    return send_cluster_request_with_token(
      auth_user, params[:cluster], request, true, params, true, raw_data
    )
  end
end

get '/managec/:cluster/?*' do
  auth_user = getAuthUser()
  raw_data = request.env["rack.input"].read
  if params[:cluster]
    request = "/" + params[:splat].join("/")
    code, out = send_cluster_request_with_token(
      auth_user, params[:cluster], request, false, params, true, raw_data
    )

    # backward compatibility layer BEGIN
    # function `send_cluster_request_with_token` sometimes removes the leading
    # slash from the variable `request`; so we must check `request` with
    # optional leading slash in every `when`!
    case request
      # new structured response format added in pcs-0.10.7
      when /\/?get_avail_resource_agents/
        return pcs_0_10_6_get_avail_resource_agents(code, out)
    end
    # backward compatibility layer END
    return code, out
  end
end

get '*' do
  $logger.debug "Bad URL"
  $logger.debug params[:splat]
  $logger.info "Redirecting '*'...\n"
  redirect '/manage'
  redirect "Bad URL"
  call(env.merge("PATH_INFO" => '/nodes'))
end
