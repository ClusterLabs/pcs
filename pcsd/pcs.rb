# Wrapper for PCS command

require 'etc'
require 'childprocess'
require 'shellwords'
require 'cgi'
require 'net/http'
require 'net/https'
require 'uri'
require 'json'
require 'fileutils'
require 'backports/latest'
require 'base64'
require 'ethon'
require 'openssl'

require 'config.rb'
require 'cfgsync.rb'
require 'corosyncconf.rb'
require 'resource.rb'
require 'cluster_entity.rb'
require 'auth.rb'
require 'settings.rb'

class NotImplementedException < NotImplementedError
end

class InvalidFileNameException < NameError
end

def getAllSettings(auth_user, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(auth_user)
  end
  ret = {}
  if cib_dom
    cib_dom.elements.each('/cib/configuration/crm_config//nvpair') { |e|
      ret[e.attributes['name']] = e.attributes['value']
    }
  end
  return ret
end

def add_fence_level(auth_user, level, devices, node, remove = false)
  if not remove
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, "--", "stonith", "level", "add", level, node, devices
    )
    return retval,stdout, stderr
  else
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, "--", "stonith", "level", "remove", level, "target", node, "stonith", devices
    )
    return retval,stdout, stderr
  end
end

def add_node_attr(auth_user, node, key, value)
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "--", "node", "attribute", node, key.to_s + '=' + value.to_s
  )
  return retval
end

def add_meta_attr(auth_user, resource, key, value)
  cmd = ["resource", "meta", resource, key.to_s + "=" + value.to_s]
  flags = []
  if key.to_s == "remote-node"
    # --force is a workaround for:
    # 1) Error: this command is not sufficient for create guest node, use 'pcs
    # cluster node add-guest', use --force to override
    # 2) Error: this command is not sufficient for remove guest node, use 'pcs
    # cluster node remove-guest', use --force to override
    flags << "--force"
  end
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  return retval
end

def add_location_constraint(
  auth_user, resource, node, score, force=false
)
  if node == ""
    return "Bad node"
  end

  if score == ""
    nodescore = node
  else
    nodescore = node + "=" + score
  end

  cmd = ["constraint", "location", resource, "prefers", nodescore]
  flags = []
  flags << '--force' if force

  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  return retval, stderr.join(' ')
end

def add_location_constraint_rule(
  auth_user, resource, rule, score, force=false
)
  cmd = ["constraint", "location", resource, "rule"]
  if score != ''
    if is_score(score.upcase)
      cmd << "score=#{score.upcase}"
    else
      cmd << "score-attribute=#{score}"
    end
  end
  cmd.concat(rule.shellsplit())
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  return retval, stderr.join(' ')
end

def add_order_constraint(
    auth_user, resourceA, resourceB, actionA, actionB, score, symmetrical=true,
    force=false
)
  command = [
    "constraint", "order", actionA, resourceA, "then", actionB, resourceB
  ]
  command << "score=" + score if score != ""
  command << (symmetrical ? "symmetrical" : "nonsymmetrical")
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *command)
  return retval, stderr.join(' ')
end

def add_order_set_constraint(auth_user, resource_set_list, force=false)
  command = ["constraint", "order"]
  resource_set_list.each { |resource_set|
    command << "set"
    command.concat(resource_set)
  }
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *command)
  return retval, stderr.join(' ')
end

def add_colocation_set_constraint(auth_user, resource_set_list, force=false)
  command = ["constraint", "colocation"]
  resource_set_list.each { |resource_set|
    command << "set"
    command.concat(resource_set)
  }
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *command)
  return retval, stderr.join(' ')
end

def add_ticket_constraint(
    auth_user, ticket, resource_id, role, loss_policy, force=false
)
  command = ["constraint", "ticket", "add", ticket]
  if role
    command << role
  end
  command << resource_id
  command << 'loss-policy=' + loss_policy unless loss_policy.strip().empty?()
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *command)
  return retval, stderr.join(' ')
end

def add_ticket_set_constraint(
  auth_user, ticket, loss_policy, resource_set_list, force=false
)
  command = ['constraint', 'ticket']
  resource_set_list.each { |resource_set|
    command << 'set'
    command.concat(resource_set)
  }
  command << 'setoptions'
  command << 'ticket=' + ticket
  command << 'loss-policy=' + loss_policy unless loss_policy.strip().empty?()
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *command)
  return retval, stderr.join(' ')
end

def add_colocation_constraint(
  auth_user, resourceA, resourceB, score, force=false
)
  if score == "" or score == nil
    score = "INFINITY"
  end
  command = [
    "constraint", "colocation", "add", resourceA, "with", resourceB, score
  ]
  flags = []
  flags << '--force' if force
  stdout, stderr, retval = run_cmd(auth_user, PCS, *flags, "--", *command)
  return retval, stderr.join(' ')
end

def remove_constraint(auth_user, constraint_id)
  stdout, stderror, retval = run_cmd(
    auth_user, PCS, "--", "constraint", "remove", constraint_id
  )
  $logger.info stdout
  return retval
end

def remove_constraint_rule(auth_user, rule_id)
  stdout, stderror, retval = run_cmd(
    auth_user, PCS, "--", "constraint", "rule", "remove", rule_id
  )
  $logger.info stdout
  return retval
end

def add_acl_role(auth_user, name, description)
  cmd = [PCS, "--", "acl", "role", "create", name.to_s]
  if description.to_s != ""
    cmd << "description=#{description.to_s}"
  end
  stdout, stderror, retval = run_cmd(auth_user, *cmd)
  if retval != 0
    return stderror.join("\n").strip
  end
  return ""
end

def add_acl_permission(auth_user, acl_role_id, perm_type, xpath_id, query_id)
  stdout, stderror, retval = run_cmd(
    auth_user, PCS, "--", "acl", "permission", "add", acl_role_id.to_s, perm_type.to_s,
    xpath_id.to_s, query_id.to_s
  )
  if retval != 0
    if stderror.empty?
      return "Error adding permission"
    else
      return stderror.join("\n").strip
    end
  end
  return ""
end

def add_acl_usergroup(auth_user, acl_role_id, user_group, name)
  if (user_group == "user") or (user_group == "group")
    stdout, stderr, retval = run_cmd(
      auth_user, PCS, "--", "acl", user_group, "create", name.to_s, acl_role_id.to_s
    )
    if retval == 0
      return ""
    end
    $logger.info(stdout)
    if not /^Error: '#{name.to_s}' already exists$/i.match(stderr.join("\n").strip)
      return stderr.join("\n").strip
    end
  end
  stdout, stderror, retval = run_cmd(
    auth_user, PCS, "--", "acl", "role", "assign",
    acl_role_id.to_s, user_group, name.to_s
  )
  if retval != 0
    if stderror.empty?
      return "Error adding #{user_group}"
    else
      return stderror.join("\n").strip
    end
  end
  return ""
end

def remove_acl_permission(auth_user, acl_perm_id)
  stdout, stderror, retval = run_cmd(
    auth_user, PCS, "--", "acl", "permission", "delete", acl_perm_id.to_s
  )
  if retval != 0
    if stderror.empty?
      return "Error removing permission"
    else
      return stderror.join("\n").strip
    end
  end
  return ""
end

def remove_acl_usergroup(auth_user, role_id, usergroup_id, user_or_group)
  if ['user', 'group'].include?(user_or_group)
    stdout, stderror, retval = run_cmd(
      auth_user, PCS, "--autodelete", "--", "acl", "role", "unassign", role_id.to_s, user_or_group,
      usergroup_id.to_s
    )
  else
    stdout, stderror, retval = run_cmd(
      auth_user, PCS, "--autodelete", "--", "acl", "role", "unassign", role_id.to_s,
      usergroup_id.to_s
    )
  end
  if retval != 0
    if stderror.empty?
      return "Error removing user / group"
    else
      return stderror.join("\n").strip
    end
  end
  return ""
end

# Gets all of the nodes specified in the pcs config file for the cluster
def get_cluster_nodes(cluster_name)
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  clusters = pcs_config.clusters
  cluster = nil
  for c in clusters
    if c.name == cluster_name
      cluster = c
      break
    end
  end

  if cluster && cluster.nodes != nil
    nodes = cluster.nodes
  else
    $logger.info "Error: no nodes found for #{cluster_name}"
    nodes = []
  end
  return nodes
end

def send_cluster_request_with_token(auth_user, cluster_name, request, post=false, data={}, remote=true, raw_data=nil)
  $logger.info("SCRWT: " + request)
  nodes = get_cluster_nodes(cluster_name)
  return send_nodes_request_with_token(
    auth_user, nodes, request, post, data, remote, raw_data
  )
end

def send_nodes_request_with_token(auth_user, nodes, request, post=false, data={}, remote=true, raw_data=nil)
  out = ""
  code = 0
  $logger.info("SNRWT: " + request)

  for node in nodes
    $logger.info "SNRWT Node: #{node} Request: #{request}"
    code, out = send_request_with_token(
      auth_user, node, request, post, data, remote, raw_data
    )
    # try next node if:
    # - current node does not support the request (old version of pcsd?) (404)
    # - an exception or other error occurred (5xx)
    # - we don't have a token for the node (401, notoken)
    # - we didn't get a response form the node (e.g. an exception occurred)
    # - pacemaker is not running on the node
    # do not try next node if
    # - node returned 400 - it means the request cannot be processed because of
    #   invalid arguments or another known issue, no node would be able to
    #   process the request (e.g. removing a non-existing resource)
    # - node returned 403 - permission denied, no node should allow to process
    #   the request
    log = "SNRWT Node #{node} Request #{request}"
    if (404 == code) or (code >= 500 and code <= 599)
      $logger.info("#{log}: HTTP code #{code}")
      next
    end
    if (401 == code) or ('{"notoken":true}' == out)
      $logger.info("#{log}: Bad or missing token")
      next
    end
    if '{"pacemaker_not_running":true}' == out
      $logger.info("#{log}: Pacemaker not running")
      next
    end
    if '{"noresponse":true}' == out
      $logger.info("#{log}: No response")
      next
    end
    $logger.info("#{log}: HTTP code #{code}")
    break
  end
  return code, out
end

def send_request_with_token(
  auth_user, node, request, post=false, data={}, remote=true, raw_data=nil,
  timeout=nil, additional_known_hosts={}
)
  $logger.info "SRWT Node: #{node} Request: #{request}"
  target_info = additional_known_hosts[node] || get_known_hosts()[node] || nil
  if not target_info
    $logger.error "Unable to connect to node #{node}, the node is not known"
    return 400,'{"notoken":true}'
  end
  target_token = target_info.token
  if not target_token
    $logger.error "Unable to connect to node #{node}, no token available"
    return 400,'{"notoken":true}'
  end
  target_addr = target_info.first_dest()['addr']
  target_port = target_info.first_dest()['port']
  if not target_addr
    $logger.error "Unable to connect to node #{node}, its address is not known"
    return 400,'{"notoken":true}'
  end
  if not target_port
    $logger.error "Unable to connect to node #{node}, its port is not known"
    return 400,'{"notoken":true}'
  end
  cookies_data = {
    'token' => target_token,
  }
  return send_request(
    auth_user, target_addr, target_port, request, post, data, remote, raw_data,
    timeout, cookies_data
  )
end

def _get_cookie_list(auth_user, cookies_data)
  cookie_list = []
  cookies_data_default = {}
  # Let's be safe about characters in cookie variables and do base64.
  # We cannot do it for CIB_user however to be backward compatible
  # so we at least remove disallowed characters.
  cookies_data_default['CIB_user'] = PCSAuth.cookieUserSafe(
    auth_user[:username].to_s
  )
  cookies_data_default['CIB_user_groups'] = PCSAuth.cookieUserEncode(
    (auth_user[:usergroups] || []).join(' ')
  )

  cookies_data_default.update(cookies_data)
  cookies_data_default.each { |name, value|
    cookie_list << CGI::Cookie.new('name' => name, 'value' => value).to_s
  }
  return cookie_list
end

def _transform_data(data)
  # Converts data in a way that URI.encode_www_form method will encode it
  # correctly. If an array is passed as a value to encode_www_form, then parser
  # of webrick will use only the last value.
  new_data = []
  data.each { |key, val|
    if val.kind_of?(Array)
      val.each { |value|
        new_data << ["#{key.to_s}[]", value]
      }
    else
      new_data << [key, val]
    end
  }
  return new_data
end

def send_request(
  auth_user, node, port, request, post=false, data={}, remote=true,
  raw_data=nil, timeout=nil, cookies_data=nil
)
  cookies_data = {} if not cookies_data
  if request.start_with?("/")
    request.slice!(0)
  end

  node6 = node
  if (node.include?(":") and ! node.start_with?("["))
    node6 = "[#{node}]"
  end

  if remote
    url = "https://#{node6}:#{port}/remote/#{request}"
  else
    url = "https://#{node6}:#{port}/#{request}"
  end

  data = _transform_data(data)

  if post
    encoded_data = (raw_data) ? raw_data : URI.encode_www_form(data)
  else
    url_data = (raw_data) ? raw_data : URI.encode_www_form(data)
    prefix = request.include?('?') ? '&' : '?'
    url += "#{prefix}#{url_data}"
  end


  timeout_ms = 30000
  begin
    if timeout
      timeout_ms = (Float(timeout) * 1000).to_i
    elsif ENV['PCSD_NETWORK_TIMEOUT']
       timeout_ms = (Float(ENV['PCSD_NETWORK_TIMEOUT']) * 1000).to_i
    end
  rescue
  end

  $logger.info "Connecting to: #{url}"

  req = Ethon::Easy.new()
  req.set_attributes({
    :url => url,
    :timeout_ms => timeout_ms,
    :cookie => _get_cookie_list(auth_user, cookies_data).join(';'),
    :ssl_verifyhost => 0,
    :ssl_verifypeer => 0,
    :postfields => (encoded_data) ? encoded_data : nil,
    :httpget => (post ? 0 : 1),
    :nosignal => 1, # required for multi-threading
  })
  req.compose_header('Expect', '')
  return_code = req.perform
  response_code = req.response_code
  response_body = req.response_body
  req.cleanup
  if return_code == :ok
    return response_code, response_body
  else
    if is_proxy_set(ENV)
      $logger.warn(
        'Proxy is set in environment variables, try disabling it'
      )
    end
    $logger.info(
      "No response from: #{node} request: #{request}, error: #{return_code}"
    )
    return 400,'{"noresponse":true}'
  end
end

def is_proxy_set(env_var_hash)
  proxy_list = ["https_proxy", "all_proxy"]
  proxy_list += proxy_list.map {|item| item.upcase}
  proxy_list.each { |var|
    if env_var_hash[var] and env_var_hash[var] != ''
      return true
    end
  }
  return false
end

def get_local_node_id()
  out, errout, retval = run_cmd(
    PCSAuth.getSuperuserAuth(),
    COROSYNC_CMAPCTL, "-g", "runtime.votequorum.this_node_id"
  )
  if retval != 0
    return ""
  else
    return out[0].split(/ = /)[1].strip()
  end
end

def has_corosync_conf()
  return Cfgsync::cluster_cfg_class.exist?()
end

def get_corosync_conf()
  return Cfgsync::cluster_cfg_class.from_file().text()
end

def get_corosync_nodes_names()
  if has_corosync_conf()
    return CorosyncConf::get_corosync_nodes_names(
      CorosyncConf::parse_string(get_corosync_conf())
    )
  end
  return []
end

def get_nodes()
  nodes = get_nodes_status()
  return [
    (nodes["corosync_online"] + nodes["pacemaker_online"]).uniq,
    (nodes["corosync_offline"] + nodes["pacemaker_offline"] + nodes["pacemaker_standby"]).uniq
  ]
end

def get_nodes_status()
  corosync_online = []
  corosync_offline = []
  pacemaker_online = []
  pacemaker_offline = []
  pacemaker_standby = []
  in_pacemaker = false
  stdout, stderr, retval = run_cmd(
    PCSAuth.getSuperuserAuth(), PCS, "--", "status", "nodes", "both"
  )
  stdout.each {|l|
    l = l.chomp
    if l.start_with?("Pacemaker Nodes:")
      in_pacemaker = true
    end
    if l.start_with?("Pacemaker Remote Nodes:")
      break
    end
    if l.end_with?(":")
      next
    end

    title,nodes = l.split(/: /,2)
    if nodes == nil
      next
    end

    if title == " Online"
      in_pacemaker ? pacemaker_online.concat(nodes.split(/ /)) : corosync_online.concat(nodes.split(/ /))
    elsif title == " Standby"
      if in_pacemaker
        pacemaker_standby.concat(nodes.split(/ /))
      end
    elsif title == " Maintenance"
      if in_pacemaker
        pacemaker_online.concat(nodes.split(/ /))
      end
    else
      in_pacemaker ? pacemaker_offline.concat(nodes.split(/ /)) : corosync_offline.concat(nodes.split(/ /))
    end
  }
  return {
    'corosync_online' => corosync_online,
    'corosync_offline' => corosync_offline,
    'pacemaker_online' => pacemaker_online,
    'pacemaker_offline' => pacemaker_offline,
    'pacemaker_standby' => pacemaker_standby,
  }
end

def get_cluster_name_and_uuid()
  if has_corosync_conf()
    corosync_conf = CorosyncConf::parse_string(
      Cfgsync::CorosyncConf.from_file().text()
    )
    # mimic corosync behavior - the last value is used
    cluster_name = ''
    cluster_uuid = ''
    corosync_conf.sections('totem').each { |totem|
      totem.attributes('cluster_name').each { |attrib|
        cluster_name = attrib[1]
      }
      totem.attributes('cluster_uuid').each { |attrib|
        cluster_uuid = attrib[1]
      }
    }
    return cluster_name, cluster_uuid
  end
  return '', ''
end

def get_cluster_name()
  return get_cluster_name_and_uuid()[0]
end

def get_node_attributes(auth_user, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(auth_user)
    return {} unless cib_dom
  end
  node_attrs = {}
  cib_dom.elements.each(
    '/cib/configuration/nodes/node/instance_attributes/nvpair'
  ) { |e|
    node = e.parent.parent.attributes['uname']
    node_attrs[node] ||= []
    node_attrs[node] << {
      :id => e.attributes['id'],
      :name => e.attributes['name'],
      :value => e.attributes['value']
    }
  }
  node_attrs.each { |_, val| val.sort_by! { |obj| obj[:name] }}
  return node_attrs
end

def get_nodes_utilization(cib_dom)
  return {} unless cib_dom
  utilization = {}
  cib_dom.elements.each(
    '/cib/configuration/nodes/node/utilization/nvpair'
  ) { |e|
    node = e.parent.parent.attributes['uname']
    utilization[node] ||= []
    utilization[node] << {
      :id => e.attributes['id'],
      :name => e.attributes['name'],
      :value => e.attributes['value']
    }
  }
  return utilization
end

def get_fence_levels(auth_user, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(auth_user)
    return {} unless cib_dom
  end

  fence_levels = {}
  cib_dom.elements.each(
    '/cib/configuration/fencing-topology/fencing-level'
  ) { |e|
    target = e.attributes['target']
    if target
      fence_levels[target] ||= []
      fence_levels[target] << {
        'level' => e.attributes['index'],
        'devices' => e.attributes['devices']
      }
    end
  }

  fence_levels.each { |_, val| val.sort_by! { |obj| obj['level'].to_i }}
  return fence_levels
end

def get_acls(auth_user, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(auth_user)
    return {} unless cib_dom
  end

  acls = {
    'role' => {},
    'group' => {},
    'user' => {},
    'target' => {}
  }

  cib_dom.elements.each('/cib/configuration/acls/*') { |e|
    type = e.name[4..-1]
    if e.name == 'acl_role'
      role_id = e.attributes['id']
      desc = e.attributes['description']
      acls[type][role_id] = {}
      acls[type][role_id]['description'] = desc ? desc : ''
      acls[type][role_id]['permissions'] = []
      e.elements.each('acl_permission') { |p|
        p_id = p.attributes['id']
        p_kind = p.attributes['kind']
        val = ''
        if p.attributes['xpath']
          val = "xpath #{p.attributes['xpath']}"
        elsif p.attributes['reference']
          val = "id #{p.attributes['reference']}"
        else
          next
        end
        acls[type][role_id]['permissions'] << "#{p_kind} #{val} (#{p_id})"
      }
    elsif ['acl_target', 'acl_group'].include?(e.name)
      id = e.attributes['id']
      acls[type][id] = []
      e.elements.each('role') { |r|
        acls[type][id] << r.attributes['id']
      }
    end
  }
  acls['user'] = acls['target']
  return acls
end

def enable_cluster(auth_user, all)
  cmd = ["cluster", "enable"]
  flags = []
  flags << '--all' if all == '1'
  stdout, stderror, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  return false if retval != 0
  return true
end

def disable_cluster(auth_user, all)
  cmd = ["cluster", "disable"]
  flags = []
  flags << '--all' if all == '1'
  stdout, stderror, retval = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  return false if retval != 0
  return true
end

def get_corosync_version()
  begin
    stdout, stderror, retval = run_cmd(
      PCSAuth.getSuperuserAuth(), COROSYNC, "-v"
    )
  rescue
    stdout = []
  end
  if retval == 0
    match = /version\D+(\d+)\.(\d+)\.(\d+)/.match(stdout.join())
    if match
      return match[1..3].collect { | x | x.to_i }
    end
  end
  return nil
end

def pacemaker_running?()
  return ServiceChecker.new(
    ['pacemaker'], running: true
  ).is_running?('pacemaker')
end

def pacemaker_remote_running?()
  return ServiceChecker.new(
    ['pacemaker_remote'], running: true
  ).is_running?('pacemaker_remote')
end

def get_pacemaker_version()
  begin
    stdout, stderror, retval = run_cmd(
      PCSAuth.getSuperuserAuth(), PACEMAKERD, "-$"
    )
  rescue
    stdout = []
  end
  if retval == 0
    match = /(\d+)\.(\d+)\.(\d+)/.match(stdout.join())
    if match
      return match[1..3].collect { | x | x.to_i }
    end
  end
  return nil
end

def get_rhel_version()
  if File.exists?('/etc/system-release')
    release = File.open('/etc/system-release').read
    match = /(\d+)\.(\d+)/.match(release)
    if match
      return match[1, 2].collect{ |x| x.to_i}
    end
  end
  return nil
end

def get_pcsd_version()
  return PCS_VERSION.split(".").collect { | x | x.to_i }
end

def run_cmd(auth_user, *args)
  options = {}
  return run_cmd_options(auth_user, options, *args)
end

def run_cmd_options(auth_user, options, *args)
  $logger.info("Running: " + args.join(" "))
  start = Time.now
  out = Tempfile.new
  errout = Tempfile.new

  cib_user = auth_user[:username]
  # when running 'id -Gn' to get the groups they are not defined yet
  cib_groups = (auth_user[:usergroups] || []).join(' ')
  $logger.info("CIB USER: #{cib_user}, groups: #{cib_groups}")

  ChildProcess.posix_spawn = true
  cmd = ChildProcess.build(*args)
  cmd.io.stdout = out
  cmd.io.stdout.fcntl(Fcntl::F_SETFD, Fcntl::FD_CLOEXEC)
  cmd.io.stderr = errout
  cmd.io.stderr.fcntl(Fcntl::F_SETFD, Fcntl::FD_CLOEXEC)
  cmd.duplex = true
  cmd.environment['CIB_user'] = cib_user
  cmd.environment['CIB_user_groups'] = cib_groups
  cmd.environment['LC_ALL'] = 'C'
  cmd.start

  if options and options.key?('stdin')
    cmd.io.stdin.puts options['stdin']
    cmd.io.stdin.close
  end

  cmd.wait
  duration = Time.now - start
  retval = cmd.exit_code

  out.rewind
  output = out.readlines
  errout.rewind
  error_output = errout.readlines
  out.close
  errout.close

  $logger.debug(output.join(" "))
  $logger.debug(error_output.join(" "))
  $logger.debug("Duration: " + duration.to_s + "s")
  $logger.info("Return Value: " + retval.to_s)

  return output, error_output, retval
end

def is_score(score)
  return !!/^[+-]?((INFINITY)|(\d+))$/.match(score)
end

# Does pacemaker consider a variable as true in cib?
# See crm_is_true in pacemaker/lib/common/utils.c
def is_cib_true(var)
  return false if not var.respond_to?(:downcase)
  return ['true', 'on', 'yes', 'y', '1'].include?(var.downcase)
end

def get_known_hosts()
  return CfgKnownHosts.new(
    Cfgsync::PcsdKnownHosts.from_file().text()
  ).known_hosts
end

def is_auth_against_nodes(auth_user, node_names, timeout=10)
  threads = []
  not_authorized_nodes = []
  online_nodes = []
  offline_nodes = []

  node_names.uniq.each { |node_name|
    threads << Thread.new(Thread.current[:pcsd_logger_container]) { |logger|
      Thread.current[:pcsd_logger_container] = logger
      code, response = send_request_with_token(
        auth_user, node_name, 'check_auth', false, {}, true, nil, timeout
      )
      if code == 200
        online_nodes << node_name
      else
        begin
          parsed_response = JSON.parse(response)
          if parsed_response['notauthorized'] or parsed_response['notoken']
            not_authorized_nodes << node_name
          else
            offline_nodes << node_name
          end
        rescue JSON::ParserError
          not_authorized_nodes << node_name
        end
      end
    }
  }
  threads.each { |t| t.join }
  return online_nodes, offline_nodes, not_authorized_nodes
end

def pcs_auth_token(nodes)
  # nodes is a hash of hashes:
  # {
  #   'node name' => {
  #     'token' => auth token
  #     'dest_list' => [ # currently only the first item is used
  #       {'addr' => addr, 'port' => port} # how to connect to a node
  #     ]
  #   }
  # }

  new_hosts = []
  nodes.each { |node_name, node_data|
    new_hosts << PcsKnownHost.new(
      node_name,
      node_data['token'],
      [node_data['dest_list'][0]]
    )
  }

  # We want to avoid send updated known hosts to all cluster nodes therefore we
  # are using 'nil' for cluster_name argument. Actually, automatic known hosts
  # synchronization should be disabled in cluster when setting a custom token.
  Cfgsync::save_sync_new_known_hosts(new_hosts, [], [], nil)
end

def pcs_auth(auth_user, nodes)
  # nodes is a hash of hashes:
  # {
  #   'node name' => {
  #     'username' => a username used for auth
  #     'password' => a password used for auth
  #     'dest_list' => [ # currently only the first item is used
  #       {'addr' => addr, 'port' => port} # how to connect to a node
  #     ]
  #   }
  # }

  # authorize against the nodes
  auth_responses = {}
  threads = []
  nodes.each { |node_name, node_data|
    threads << Thread.new(Thread.current[:pcsd_logger_container]) { |logger|
      Thread.current[:pcsd_logger_container] = logger
      begin
        addr = node_data.fetch('dest_list').fetch(0).fetch('addr')
        port = node_data.fetch('dest_list').fetch(0).fetch('port')
        request_data = {
          :username => node_data.fetch('username'),
          :password => node_data.fetch('password'),
        }
        code, response = send_request(
          auth_user, addr, port, 'auth', true, request_data, true
        )
        if 200 == code
          token = response.strip
          if '' == token
            auth_responses[node_name] = {'status' => 'bad_password'}
          else
            auth_responses[node_name] = {'status' => 'ok', 'token' => token}
          end
        else
          auth_responses[node_name] = {'status' => 'noresponse'}
        end
      rescue => e
        auth_responses[node_name] = {'status' => 'error', 'error' => e}
      end
    }
  }
  threads.each { |t| t.join }

  # get the tokens form the response
  new_hosts = []
  auth_responses.each { |node_name, response|
    if 'ok' == response['status']
      new_hosts << PcsKnownHost.new(
        node_name,
        response['token'],
        [nodes[node_name]['dest_list'][0]]
      )
    end
  }

  # sync known hosts within the local cluster
  sync_successful = true
  sync_failed_nodes = []
  sync_responses = {}
  if new_hosts.empty?
    return auth_responses, sync_successful, sync_failed_nodes, sync_responses
  end
  # Only tokens used in pcsd-to-pcsd communication can and need to be synced.
  # Those are accessible only when running under root account.
  if Process.uid != 0
    # Other tokens just need to be stored localy for a user.
    sync_successful, sync_responses = Cfgsync::save_sync_new_known_hosts(
      new_hosts, [], [], nil
    )
    return auth_responses, sync_successful, sync_failed_nodes, sync_responses
  end
  cluster_nodes = get_corosync_nodes_names()
  sync_successful, sync_responses = Cfgsync::save_sync_new_known_hosts(
    new_hosts, [], cluster_nodes, $cluster_name
  )
  # sync_notauthorized_nodes is not used because clients extract that info from
  # auth_responses themselves
  sync_notauthorized_nodes, sync_failed_nodes = (
    Cfgsync::get_failed_nodes_from_sync_responses(sync_responses)
  )
  return auth_responses, sync_successful, sync_failed_nodes, sync_responses
end

def pcs_deauth(auth_user, host_names)
  # sync known hosts within the local cluster
  sync_successful = true
  sync_failed_nodes = []
  sync_responses = {}
  hosts_not_found = []

  if host_names.empty?
    return sync_successful, sync_failed_nodes, sync_responses, hosts_not_found
  end
  known_hosts_names = get_known_hosts().keys()
  host_names.each { |name_to_remove|
    if not known_hosts_names.include?(name_to_remove)
      hosts_not_found << name_to_remove
    end
  }
  if hosts_not_found.length > 0
    return sync_successful, sync_failed_nodes, sync_responses, hosts_not_found
  end

  # Only tokens used in pcsd-to-pcsd communication can and need to be synced.
  # Those are accessible only when running under root account.
  if Process.uid != 0
    # Other tokens just need to be stored localy for a user.
    sync_successful, sync_responses = Cfgsync::save_sync_new_known_hosts(
      [], host_names, [], nil
    )
    return sync_successful, sync_failed_nodes, sync_responses, hosts_not_found
  end
  cluster_nodes = get_corosync_nodes_names()
  sync_successful, sync_responses = Cfgsync::save_sync_new_known_hosts(
    [], host_names, cluster_nodes, $cluster_name
  )
  sync_responses.each { |node, response|
    if response['status'] != 'ok'
      sync_failed_nodes << node
    else
      node_result = response['result'][Cfgsync::PcsdKnownHosts.name]
      if not ['accepted', 'rejected'].include?(node_result)
        sync_failed_nodes << node
      end
    end
  }
  return sync_successful, sync_failed_nodes, sync_responses, hosts_not_found
end

def send_local_configs_to_nodes(
  auth_user, nodes, force=false, clear_local_permissions=false
)
  configs = Cfgsync::get_configs_local(true)
  if clear_local_permissions
    pcs_config = PCSConfig.new(configs[Cfgsync::PcsdSettings.name].text())
    pcs_config.permissions_local = Permissions::PermissionsSet.new([])
    configs[Cfgsync::PcsdSettings.name].text = pcs_config.text()
  end
  publisher = Cfgsync::ConfigPublisher.new(
    auth_user, configs.values(), nodes, $cluster_name
  )
  return publisher.send(force)
end

def get_uid(username)
  return Etc.getpwnam(username).uid
end

def get_gid(groupname)
  return Etc.getgrnam(groupname).gid
end

def write_file_lock(path, perm, data, binary=false, user=nil, group=nil)
  file = nil
  begin
    file = File.open(path, binary ? 'wb' : 'w', perm)
    file.flock(File::LOCK_EX)
    if user or group
      File.chown(get_uid(user), get_gid(group), path)
    end
    file.write(data)
  rescue => e
    $logger.error("Cannot save file '#{path}': #{e.message}")
    raise
  ensure
    unless file.nil?
      file.flock(File::LOCK_UN)
      file.close()
    end
  end
end

def read_file_lock(path, binary=false)
  file = nil
  begin
    file = File.open(path, binary ? 'rb' : 'r')
    file.flock(File::LOCK_SH)
    return file.read()
  rescue => e
    $logger.error("Cannot read file '#{path}': #{e.message}")
    raise
  ensure
    unless file.nil?
      file.flock(File::LOCK_UN)
      file.close()
    end
  end
end

def verify_cert_key_pair(cert_data, key_data)
  errors = []

  begin
    cert = OpenSSL::X509::Certificate.new(cert_data)
  rescue OpenSSL::X509::CertificateError => e
    errors << "Invalid certificate: #{e}"
  end

  begin
    key = OpenSSL::PKey.read(key_data)
  rescue OpenSSL::PKey::PKeyError => e
    errors << "Invalid key: #{e}"
  end

  if errors.empty?
    if not cert.check_private_key(key)
      errors << 'Certificate does not match the key'
    end
  end

  return errors
end

def cluster_status_from_nodes(auth_user, cluster_nodes, cluster_name)
  node_map = {}
  forbidden_nodes = {}
  overview = {
    :cluster_name => cluster_name,
    :error_list => [],
    :warning_list => [],
    :quorate => nil,
    :status => 'unknown',
    :node_list => [],
    :resource_list => [],
    :pcsd_capabilities => [],
  }

  threads = []
  cluster_nodes.uniq.each { |node|
    threads << Thread.new(Thread.current[:pcsd_logger_container]) { |logger|
      Thread.current[:pcsd_logger_container] = logger
      code, response = send_request_with_token(
        auth_user,
        node,
        'status',
        false,
        {:version=>'2', :operations=>'1'},
        true,
        nil,
        15
      )
      node_map[node] = {}
      node_map[node].update(overview)
      if 403 == code
        forbidden_nodes[node] = true
      end
      node_status_unknown = {
        :name => node,
        :status => 'unknown',
        :warning_list => [],
        :error_list => []
      }
      begin
        parsed_response = JSON.parse(response, {:symbolize_names => true})
        parsed_response[:pcsd_capabilities] ||= []
        if parsed_response[:noresponse]
          node_map[node][:node] = {}
          node_map[node][:node].update(node_status_unknown)
        elsif parsed_response[:notoken] or parsed_response[:notauthorized]
          node_map[node][:node] = {}
          node_map[node][:node].update(node_status_unknown)
          node_map[node][:node][:notauthorized] = true
        else
          if parsed_response[:node]
            parsed_response[:status_version] = '2'
            parsed_response[:node][:status_version] = '2'
            node_map[node] = parsed_response
          else
            node_map[node][:node] = {}
            node_map[node][:node].update(node_status_unknown)
          end
        end
        node_map[node][:node][:name] = node
      rescue JSON::ParserError
        node_map[node][:node] = {}
        node_map[node][:node].update(node_status_unknown)
      end
    }
  }
  threads.each { |t| t.join }

  cluster_nodes_map = {}
  node_status_list = []
  quorate_nodes = []
  not_authorized_nodes = []
  node_map.each { |node_name, cluster_status|
    # If we were able to get node's cluster name and it's different than
    # requested cluster name, the node belongs to some other cluster and its
    # data should not be used.
    # If we don't know node's cluster name, we keep the data because the node is
    # possibly in our cluster, we just didn't get its status.
    next if cluster_status[:cluster_name] != cluster_name
    cluster_nodes_map[node_name] = cluster_status
    node_status_list << cluster_status[:node]
    quorate_nodes << node_name if cluster_status[:node][:quorum]
    not_authorized_nodes << node_name if cluster_status[:node][:notauthorized]
  }

  node_status_list.each { |node|
    return nil if forbidden_nodes[node[:name]]
  }
  if cluster_nodes_map.length < 1
    return overview
  end

  # if we have quorum, use data from a node in the quorate partition
  if quorate_nodes.length > 0
    status = overview.update(cluster_nodes_map[quorate_nodes[0]])
    status[:quorate] = true
    status[:node_list] = node_status_list
  # if we don't have quorum, use data from any online node,
  # otherwise use data from any node no node has quorum, so no node has any
  # info about the cluster
  else
    node_to_use = cluster_nodes_map.values[0]
    cluster_nodes_map.each { |_, node_data|
      if node_data[:node] and node_data[:node][:status] == 'online'
        node_to_use = node_data
        break
      end
    }
    status = overview.update(node_to_use)
    status[:quorate] = false
    status[:node_list] = node_status_list
  end
  status.delete(:node)
  sbd_enabled = []
  sbd_running = []
  sbd_disabled_node_list = []
  node_map.each { |_, cluster_status|
    node_status = cluster_status[:node][:status]
    node_name = cluster_status[:node][:name]
    # Create a set of available features on all nodes as an intersection of
    # available features from all nodes.
    if node_status != 'unknown' and cluster_status[:pcsd_capabilities]
      status[:pcsd_capabilities] &= cluster_status[:pcsd_capabilities]
    end
    if (
      cluster_status[:node][:services] and
      cluster_status[:node][:services][:sbd]
    )
      if cluster_status[:node][:services][:sbd][:enabled]
        sbd_enabled << node_name
      else
        sbd_disabled_node_list << node_name if node_status != 'unknown'
      end
      if cluster_status[:node][:services][:sbd][:running]
        sbd_running << node_name
      end
    end
  }

  if status[:quorate]
    fence_count = 0
    status[:resource_list].each { |r|
      if r[:stonith]
        fence_count += 1
      end
    }
    if fence_count == 0 and sbd_enabled.empty?
      status[:warning_list] << {
        :message => 'No fencing configured in the cluster',
      }
    end

    if status[:cluster_settings]['stonith-enabled'.to_sym] and
        not is_cib_true(status[:cluster_settings]['stonith-enabled'.to_sym])
      status[:warning_list] << {
        :message => 'Stonith is not enabled',
      }
    end
    if not sbd_enabled.empty? and not sbd_disabled_node_list.empty?
      status[:warning_list] << {
        :message =>
          "SBD is not enabled on node(s) #{sbd_disabled_node_list.join(', ')}",
        :type => 'sbd_not_enabled_on_all_nodes',
        :node_list => sbd_disabled_node_list
      }
    end
    if not sbd_enabled.empty? and sbd_running.empty?
      # if there is SBD running on at least one node, SBD has to be running
      # on all online/standby nodes in cluster (it is impossible to have
      # online node without running SBD, pacemaker will shutdown/not start
      # in case like this)
      status[:warning_list] << {
        :message =>
          'SBD is enabled but not running. Restart of cluster is required.',
      }
    end
    if sbd_enabled.empty? and not sbd_running.empty?
      status[:warning_list] << {
        :message =>
          'SBD is disabled but still running. Restart of cluster is required.',
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
    status[:error_list] << {
      :message => 'Unable to connect to the cluster.'
    }
    status[:status] = 'unknown'
    return status
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
        if ['failed', 'blocked'].include?(resource[:status])
          status[:status] = 'error'
          break
        elsif ['partially running'].include?(resource[:status])
          status[:status] = 'warning'
        end
      }
    end
  end
  status[:status] = 'ok' if status[:status] == 'unknown'
  return status
end

def get_node_uptime()
  uptime = `/bin/cat /proc/uptime`.chomp.split(' ')[0].split('.')[0].to_i
  mm, ss = uptime.divmod(60)
  hh, mm = mm.divmod(60)
  dd, hh = hh.divmod(24)
  return '%d day%s, %02d:%02d:%02d' % [dd, dd != 1?'s':'', hh, mm, ss]
end

def get_node_status(auth_user, cib_dom)
  node_status = {
      :cluster_name => $cluster_name,
      :cluster_uuid => $cluster_uuid,
      :groups => [],
      :constraints => {
          # :rsc_location => [],
          # :rcs_colocation => [],
          # :rcs_order => []
      },
      :cluster_settings => {},
      :acls => get_acls(auth_user, cib_dom),
      :username => auth_user[:username],
      :fence_levels => get_fence_levels(auth_user, cib_dom),
      :node_attr => get_node_attributes(auth_user, cib_dom),
      :nodes_utilization => get_nodes_utilization(cib_dom),
      :alerts => get_alerts(auth_user),
      :known_nodes => [],
      :pcsd_capabilities => CAPABILITIES_PCSD
  }

  nodes = get_nodes_status()

  known_nodes = []
  nodes.each { |_, node_list|
    known_nodes.concat node_list
  }
  node_status[:known_nodes] = known_nodes.uniq

  nodes.each do |k,v|
    node_status[k.to_sym] = v
  end

  if cib_dom
    node_status[:groups] = get_resource_groups(cib_dom)
    node_status[:constraints] = getAllConstraints(cib_dom.elements['/cib/configuration/constraints'])
  end

  node_status[:cluster_settings] = getAllSettings(auth_user, cib_dom)

  return node_status
end

def get_resource_groups(cib_dom)
  unless cib_dom
    return []
  end
  group_list = []
  cib_dom.elements.each('/cib/configuration/resources//group') do |e|
    group_list << e.attributes['id']
  end
  return group_list
end

def get_resources(cib_dom, crm_dom=nil, get_operations=false)
  unless cib_dom
    return []
  end

  resource_list = []
  operations = (get_operations) ? ClusterEntity::get_resources_operations(cib_dom) : nil
  rsc_status = ClusterEntity::get_rsc_status(crm_dom)

  cib_dom.elements.each('/cib/configuration/resources/primitive') do |e|
    resource_list << ClusterEntity::Primitive.new(e, rsc_status, nil, operations)
  end
  cib_dom.elements.each('/cib/configuration/resources/group') do |e|
    resource_list << ClusterEntity::Group.new(e, rsc_status, nil, operations)
  end
  cib_dom.elements.each('/cib/configuration/resources/clone') do |e|
    resource_list << ClusterEntity::Clone.new(
      e, crm_dom, rsc_status, nil, operations
    )
  end
  cib_dom.elements.each('/cib/configuration/resources/master') do |e|
    resource_list << ClusterEntity::Clone.new(
      e, crm_dom, rsc_status, nil, operations
    )
  end
  return resource_list
end

def get_crm_mon_dom(auth_user)
  begin
    stdout, _, retval = run_crm_mon_xml(auth_user)
    if retval == 0
      return REXML::Document.new(stdout.join("\n"))
    end
  rescue
    $logger.error 'Failed to parse crm_mon.'
  end
  return nil
end

def get_cib_dom(auth_user)
  begin
    stdout, _, retval = run_cmd(auth_user, CIBADMIN, '-Q', '-l')
    if retval == 0
      return REXML::Document.new(stdout.join("\n"))
    end
  rescue
    $logger.error 'Failed to parse cib.'
  end
  return nil
end

def allowed_for_local_cluster(auth_user, action)
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file().text())
  return pcs_config.permissions_local.allows?(
    auth_user[:username], auth_user[:usergroups], action
  )
end

def allowed_for_superuser(auth_user)
  $logger.debug(
    "permission check superuser username=#{auth_user[:username]} groups=#{auth_user[:usergroups]}"
  )
  if SUPERUSER != auth_user[:username]
    $logger.debug('permission denied')
    return false
  end
  $logger.debug('permission granted for superuser')
  return true
end

def enable_service(service)
  result = run_pcs_internal(
    PCSAuth.getSuperuserAuth(),
    "services.enable_service",
    {:service => service, :instance => nil},
  )
  return result[:status] == 'success'
end

def disable_service(service)
  result = run_pcs_internal(
    PCSAuth.getSuperuserAuth(),
    "services.disable_service",
    {:service => service, :instance => nil},
  )
  return result[:status] == 'success'
end

def start_service(service)
  result = run_pcs_internal(
    PCSAuth.getSuperuserAuth(),
    "services.start_service",
    {:service => service, :instance => nil},
  )
  return result[:status] == 'success'
end

def stop_service(service)
  if not ServiceChecker.new([service], installed: true).is_installed?(service)
    return true
  end
  result = run_pcs_internal(
    PCSAuth.getSuperuserAuth(),
    "services.stop_service",
    {:service => service, :instance => nil},
  )
  return result[:status] == 'success'
end

class ServiceChecker
  def initialize(services, flags={})
    result = run_pcs_internal(
      PCSAuth.getSuperuserAuth(),
      "services.get_services_info",
      {
        :services => services,
        :installed => flags.fetch(:installed, true),
        :enabled => flags.fetch(:enabled, false),
        :running => flags.fetch(:running, false),
      },
    )
    @services_info = {}
    if result[:status] == 'success'
      data = result[:data]
      unless data.nil?
        @services_info = Hash[
          data[:services].collect{ |service| [service[:service], service]}
        ]
      end
    end
  end

  def get_service(service)
    info = @services_info[service]
    if info.nil?
      return {
        :service => service,
        :installed => nil,
        :enabled => nil,
        :running => nil,
      }
    end
    return info
  end

  def get_info(service)
    return {
      :installed => self.is_installed?(service),
      :enabled => self.is_enabled?(service),
      :running => self.is_running?(service),
    }
  end

  def is_installed?(service)
    return !!self.get_service(service)[:installed]
  end

  def is_enabled?(service)
    return !!self.get_service(service)[:enabled]
  end

  def is_running?(service)
    return !!self.get_service(service)[:running]
  end
end

def set_cluster_prop_force(auth_user, prop, val)
  cmd = ['property', 'set', "#{prop}=#{val}"]
  flags = ['--force']
  sig_file = "#{CIB_PATH}.sig"
  retcode = 0

  if pacemaker_running?
    _, _, retcode = run_cmd(auth_user, PCS, *flags, "--", *cmd)
  else
    if File.exist?(CIB_PATH)
      flags += ['-f', CIB_PATH]
      _, _, retcode = run_cmd(PCSAuth.getSuperuserAuth(), PCS, *flags, "--", *cmd)
      begin
        File.delete(sig_file)
      rescue => e
        $logger.debug("Cannot delete file '#{sig_file}': #{e.message}")
      end
    end
  end
  return (retcode == 0)
end

def get_parsed_local_sbd_config()
  cmd = [PCS, '--', 'stonith', 'sbd', 'local_config_in_json']
  out, _, retcode = run_cmd(PCSAuth.getSuperuserAuth(), *cmd)
  if retcode != 0
    return nil
  end
  begin
    return JSON.parse(out.join(' '))
  rescue JSON::ParserError
    return nil
  end
end

def get_sbd_service_name()
  if ISSYSTEMCTL
    return 'sbd'
  else
    return 'sbd_helper'
  end
end

def read_booth_config(config)
  if config.include?('/')
    raise InvalidFileNameException.new(config)
  end
  config_path = File.join(BOOTH_CONFIG_DIR, config)
  unless File.file?(config_path)
    return nil
  end
  return read_file_lock(config_path)
end

def read_booth_authfile(filename)
  if filename.include?('/')
    raise InvalidFileNameException.new(filename)
  end
  return Base64.strict_encode64(
    read_file_lock(File.join(BOOTH_CONFIG_DIR, filename), true)
  )
end

def get_authfile_from_booth_config(config_data)
  authfile_path = nil
  config_data.split("\n").each {|line|
    if line.include?('=')
      parts = line.split('=', 2)
      if parts[0].strip == 'authfile'
        authfile_path = parts[1].strip
      end
    end
  }
  return authfile_path
end

def get_alerts(auth_user)
  out, _, retcode = run_cmd(auth_user, PCS, '--', 'alert', 'get_all_alerts')

  if retcode !=  0
    return nil
  end

  begin
    return JSON.parse(out.join(""))
  rescue JSON::ParserError
    return nil
  end
end

def get_pcs_internal_output_format(status, status_msg=nil)
  return {
    :status => status,
    :status_msg => status_msg,
    :report_list => [],
    :data => nil,
  }
end

def run_pcs_internal(auth_user, cmd, data, request_timeout=nil)
  input_data = {
    :cmd => cmd,
    :cmd_data => data,
    :options => {
      :request_timeout => request_timeout,
    },
  }
  stdout, stderr, return_val = run_cmd_options(
    auth_user,
    {'stdin' => JSON.generate(input_data)},
    PCS_INTERNAL
  )
  if return_val != 0
    return get_pcs_internal_output_format(
      'exception', "Command failed: #{stderr.join("\n")}"
    )
  end
  begin
    parsed_output = JSON.parse(stdout.join("\n"), {:symbolize_names => true})
    if (
      parsed_output.include?(:report_list) \
      and \
      parsed_output[:report_list].kind_of?(Array) \
    )
      # Remove all debug messages as they may contain sensitive info.
      parsed_output[:report_list].delete_if { |report_item|
        report_item[:severity][:level] == 'DEBUG'
      }
    end
    return parsed_output
  rescue JSON::ParserError => e
    $logger.error("Invalid output data format of command '#{cmd}': #{e}")
    return get_pcs_internal_output_format(
      'exception', "Invalid data format #{e}"
    )
  end
end
