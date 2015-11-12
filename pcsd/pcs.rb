# Wrapper for PCS command
#
require 'open4'
require 'shellwords'
require 'cgi'
require 'net/http'
require 'net/https'
require 'json'
require 'fileutils'
require 'backports'

require 'config.rb'
require 'cfgsync.rb'
require 'corosyncconf.rb'
require 'resource.rb'
require 'cluster_entity.rb'
require 'auth.rb'

def getAllSettings(session, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(session)
  end
  stdout2, stderr2, retval2 = run_cmd(session, PENGINE, "metadata")
  metadata = stdout2.join
  ret = {}
  if cib_dom and retval2 == 0
    doc = REXML::Document.new(metadata)

    default = ""
    el_type = ""
    doc.elements.each("resource-agent/parameters/parameter") { |e|
      name = e.attributes["name"]
      name.gsub!(/-/,"_")
      e.elements.each("content") { |c|
        default = c.attributes["default"]
        el_type = c.attributes["type"]
      }
      ret[name] = {"value" => default, "type" => el_type}
    }

    cib_dom.elements.each('/cib/configuration/crm_config//nvpair') { |e|
      key = e.attributes['name']
      val = e.attributes['value']
      key.gsub!(/-/,"_")
      if ret.has_key?(key)
        if ret[key]["type"] == "boolean"
          val == "true" ?  ret[key]["value"] = true : ret[key]["value"] = false
        else
          ret[key]["value"] = val
        end

      else
        ret[key] = {"value" => val, "type" => "unknown"}
      end
    }
    return ret
  end
  return {"error" => "Unable to get configuration settings"}
end

def add_fence_level(session, level, devices, node, remove = false)
  if not remove
    stdout, stderr, retval = run_cmd(
      session, PCS, "stonith", "level", "add", level, node, devices
    )
    return retval,stdout, stderr
  else
    stdout, stderr, retval = run_cmd(
      session, PCS, "stonith", "level", "remove", level, node, devices
    )
    return retval,stdout, stderr
  end
end

def add_node_attr(session, node, key, value)
  stdout, stderr, retval = run_cmd(
    session, PCS, "property", "set", "--node", node, key.to_s + '=' + value.to_s
  )
  return retval
end

def add_meta_attr(session, resource, key, value)
  stdout, stderr, retval = run_cmd(
    session, PCS, "resource", "meta", resource, key.to_s + "=" + value.to_s
  )
  return retval
end

def add_location_constraint(
  session, resource, node, score, force=false, autocorrect=true
)
  if node == ""
    return "Bad node"
  end

  if score == ""
    nodescore = node
  else
    nodescore = node + "=" + score
  end

  cmd = [PCS, "constraint", "location", resource, "prefers", nodescore]
  cmd << '--force' if force
  cmd << '--autocorrect' if autocorrect

  stdout, stderr, retval = run_cmd(session, *cmd)
  return retval, stderr.join(' ')
end

def add_location_constraint_rule(
  session, resource, rule, score, force=false, autocorrect=true
)
  cmd = [PCS, "constraint", "location", resource, "rule"]
  if score != ''
    if is_score(score.upcase)
      cmd << "score=#{score.upcase}"
    else
      cmd << "score-attribute=#{score}"
    end
  end
  cmd.concat(rule.shellsplit())
  cmd << '--force' if force
  cmd << '--autocorrect' if autocorrect
  stdout, stderr, retval = run_cmd(session, *cmd)
  return retval, stderr.join(' ')
end

def add_order_constraint(
    session, resourceA, resourceB, actionA, actionB, score, symmetrical=true,
    force=false, autocorrect=true
)
  sym = symmetrical ? "symmetrical" : "nonsymmetrical"
  if score != ""
    score = "score=" + score
  end
  command = [
    PCS, "constraint", "order", actionA, resourceA, "then", actionB, resourceB,
    score, sym
  ]
  command << '--force' if force
  command << '--autocorrect' if autocorrect
  stdout, stderr, retval = run_cmd(session, *command)
  return retval, stderr.join(' ')
end

def add_order_set_constraint(
  session, resource_set_list, force=false, autocorrect=true
)
  command = [PCS, "constraint", "order"]
  resource_set_list.each { |resource_set|
    command << "set"
    command.concat(resource_set)
  }
  command << '--force' if force
  command << '--autocorrect' if autocorrect
  stdout, stderr, retval = run_cmd(session, *command)
  return retval, stderr.join(' ')
end

def add_colocation_constraint(
  session, resourceA, resourceB, score, force=false, autocorrect=true
)
  if score == "" or score == nil
    score = "INFINITY"
  end
  command = [
    PCS, "constraint", "colocation", "add", resourceA, resourceB, score
  ]
  command << '--force' if force
  command << '--autocorrect' if autocorrect
  stdout, stderr, retval = run_cmd(session, *command)
  return retval, stderr.join(' ')
end

def remove_constraint(session, constraint_id)
  stdout, stderror, retval = run_cmd(
    session, PCS, "constraint", "remove", constraint_id
  )
  $logger.info stdout
  return retval
end

def remove_constraint_rule(session, rule_id)
  stdout, stderror, retval = run_cmd(
    session, PCS, "constraint", "rule", "remove", rule_id
  )
  $logger.info stdout
  return retval
end

def add_acl_role(session, name, description)
  cmd = [PCS, "acl", "role", "create", name.to_s]
  if description.to_s != ""
    cmd << "description=#{description.to_s}"
  end
  stdout, stderror, retval = run_cmd(session, *cmd)
  if retval != 0
    return stderror.join("\n").strip
  end
  return ""
end

def add_acl_permission(session, acl_role_id, perm_type, xpath_id, query_id)
  stdout, stderror, retval = run_cmd(
    session, PCS, "acl", "permission", "add", acl_role_id.to_s, perm_type.to_s,
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

def add_acl_usergroup(session, acl_role_id, user_group, name)
  if (user_group == "user") or (user_group == "group")
    stdout, stderr, retval = run_cmd(
      session, PCS, "acl", user_group, "create", name.to_s, acl_role_id.to_s
    )
    if retval == 0
      return ""
    end
    if not /^error: (user|group) #{name.to_s} already exists$/i.match(stderr.join("\n").strip)
      return stderr.join("\n").strip
    end
  end
  stdout, stderror, retval = run_cmd(
    session, PCS, "acl", "role", "assign", acl_role_id.to_s, name.to_s
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

def remove_acl_permission(session, acl_perm_id)
  stdout, stderror, retval = run_cmd(
    session, PCS, "acl", "permission", "delete", acl_perm_id.to_s
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

def remove_acl_usergroup(session, role_id, usergroup_id)
  stdout, stderror, retval = run_cmd(
    session, PCS, "acl", "role", "unassign", role_id.to_s, usergroup_id.to_s,
    "--autodelete"
  )
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
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('{}').text())
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

def send_cluster_request_with_token(session, cluster_name, request, post=false, data={}, remote=true, raw_data=nil)
  $logger.info("SCRWT: " + request)
  nodes = get_cluster_nodes(cluster_name)
  return send_nodes_request_with_token(
    session, nodes, request, post, data, remote, raw_data
  )
end

def send_nodes_request_with_token(session, nodes, request, post=false, data={}, remote=true, raw_data=nil)
  out = ""
  code = 0
  $logger.info("SNRWT: " + request)

  # If we're removing nodes, we don't send this to one of the nodes we're
  # removing, unless we're removing all nodes
  if request == "/remove_nodes"
    new_nodes = nodes.dup
    data.each {|k,v|
      if new_nodes.include? v
        new_nodes.delete v
      end
    }
    if new_nodes.length > 0
      nodes = new_nodes
    end
  end

  for node in nodes
    $logger.info "SNRWT Node: #{node} Request: #{request}"
    code, out = send_request_with_token(
      session, node, request, post, data, remote, raw_data
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

def send_request_with_token(session, node, request, post=false, data={}, remote=true, raw_data=nil, timeout=30, additional_tokens={})
  token = additional_tokens[node] || get_node_token(node)
  $logger.info "SRWT Node: #{node} Request: #{request}"
  if not token
    $logger.error "Unable to connect to node #{node}, no token available"
    return 400,'{"notoken":true}'
  end
  cookies_data = {
    'token' => token,
  }
  return send_request(
    session, node, request, post, data, remote, raw_data, timeout, cookies_data
  )
end

def send_request(session, node, request, post=false, data={}, remote=true, raw_data=nil, timeout=30, cookies_data=nil)
  cookies_data = {} if not cookies_data
  begin
    request = "/#{request}" if not request.start_with?("/")

    # fix ipv6 address for URI.parse
    node6 = node
    if (node.include?(":") and ! node.start_with?("["))
      node6 = "[#{node}]"
    end

    if remote
      uri = URI.parse("https://#{node6}:2224/remote" + request)
    else
      uri = URI.parse("https://#{node6}:2224" + request)
    end

    if post
      req = Net::HTTP::Post.new(uri.path)
      raw_data ? req.body = raw_data : req.set_form_data(data)
    else
      req = Net::HTTP::Get.new(uri.path)
      req.set_form_data(data)
    end

    cookies_to_send = []
    cookies_data_default = {}
    # Let's be safe about characters in cookie variables and do base64.
    # We cannot do it for CIB_user however to be backward compatible
    # so we at least remove disallowed characters.
    cookies_data_default['CIB_user'] = PCSAuth.cookieUserSafe(
      session[:username].to_s
    )
    cookies_data_default['CIB_user_groups'] = PCSAuth.cookieUserEncode(
      (session[:usergroups] || []).join(' ')
    )

    cookies_data_default.update(cookies_data)
    cookies_data_default.each { |name, value|
      cookies_to_send << CGI::Cookie.new('name' => name, 'value' => value).to_s
    }
    req.add_field('Cookie', cookies_to_send.join(';'))

    # uri.host returns "[addr]" for ipv6 addresses, which is wrong
    # uri.hostname returns "addr" for ipv6 addresses, which is correct, but it
    #   is not available in older ruby versions
    # There is a bug in Net::HTTP.new in some versions of ruby which prevents
    # ipv6 addresses being used here at all.
    myhttp = Net::HTTP.new(node, uri.port)
    myhttp.use_ssl = true
    myhttp.verify_mode = OpenSSL::SSL::VERIFY_NONE
    res = myhttp.start do |http|
      http.read_timeout = timeout
      http.request(req)
    end
    return res.code.to_i, res.body
  rescue Exception => e
    $logger.info "No response from: #{node} request: #{request}, exception: #{e}"
    return 400,'{"noresponse":true}'
  end
end

def add_node(session, new_nodename, all=false, auto_start=true)
  if all
    command = [PCS, "cluster", "node", "add", new_nodename]
    if auto_start
      command << '--start'
      command << '--enable'
    end
    out, stderror, retval = run_cmd(session, *command)
  else
    out, stderror, retval = run_cmd(
      session, PCS, "cluster", "localnode", "add", new_nodename
    )
  end
  $logger.info("Adding #{new_nodename} to pcs_settings.conf")
  corosync_nodes = get_corosync_nodes()
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('{}').text())
  pcs_config.update_cluster($cluster_name, corosync_nodes)
  sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
  # on version conflict just go on, config will be corrected eventually
  # by displaying the cluster in the web UI
  Cfgsync::save_sync_new_version(
    sync_config, corosync_nodes, $cluster_name, true
  )
  return retval, out.join("\n") + stderror.join("\n")
end

def remove_node(session, new_nodename, all=false)
  if all
    # we check for a quorum loss warning in remote_remove_nodes
    out, stderror, retval = run_cmd(
      session, PCS, "cluster", "node", "remove", new_nodename, "--force"
    )
  else
    out, stderror, retval = run_cmd(
      session, PCS, "cluster", "localnode", "remove", new_nodename
    )
  end
  $logger.info("Removing #{new_nodename} from pcs_settings.conf")
  corosync_nodes = get_corosync_nodes()
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('{}').text())
  pcs_config.update_cluster($cluster_name, corosync_nodes)
  sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
  # on version conflict just go on, config will be corrected eventually
  # by displaying the cluster in the web UI
  Cfgsync::save_sync_new_version(
    sync_config, corosync_nodes, $cluster_name, true
  )
  return retval, out + stderror
end

def get_current_node_name()
  stdout, stderror, retval = run_cmd(
    PCSAuth.getSuperuserSession, CRM_NODE, "-n"
  )
  if retval == 0 and stdout.length > 0
    return stdout[0].chomp()
  end
  return ""
end

def get_local_node_id()
  if ISRHEL6
    out, errout, retval = run_cmd(
      PCSAuth.getSuperuserSession, COROSYNC_CMAPCTL, "cluster.cman"
    )
    if retval != 0
      return ""
    end
    match = /cluster\.nodename=(.*)/.match(out.join("\n"))
    if not match
      return ""
    end
    local_node_name = match[1]
    out, errout, retval = run_cmd(
      PCSAuth.getSuperuserSession,
      CMAN_TOOL, "nodes", "-F", "id", "-n", local_node_name
    )
    if retval != 0
      return ""
    end
    return out[0].strip()
  end
  out, errout, retval = run_cmd(
    PCSAuth.getSuperuserSession,
    COROSYNC_CMAPCTL, "-g", "runtime.votequorum.this_node_id"
  )
  if retval != 0
    return ""
  else
    return out[0].split(/ = /)[1].strip()
  end
end

def get_corosync_conf()
  return Cfgsync::cluster_cfg_class.from_file().text()
end

def get_corosync_nodes()
  stdout, stderror, retval = run_cmd(
    PCSAuth.getSuperuserSession, PCS, "status", "nodes", "corosync"
  )
  if retval != 0
    return []
  end

  stdout.each {|x| x.strip!}
  corosync_online = stdout[1].sub(/^.*Online:/,"").strip
  corosync_offline = stdout[2].sub(/^.*Offline:/,"").strip
  corosync_nodes = (corosync_online.split(/ /)) + (corosync_offline.split(/ /))

  return corosync_nodes
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
    PCSAuth.getSuperuserSession, PCS, "status", "nodes", "both"
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

def need_ring1_address?()
  out, errout, retval = run_cmd(PCSAuth.getSuperuserSession, COROSYNC_CMAPCTL)
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

def get_resource_agents_avail(session)
  code, result = send_cluster_request_with_token(
    session, params[:cluster], 'get_avail_resource_agents'
  )
  return {} if 200 != code
  begin
    ra = JSON.parse(result)
    if (ra["noresponse"] == true) or (ra["notauthorized"] == "true") or (ra["notoken"] == true) or (ra["pacemaker_not_running"] == true)
      return {}
    else
      return ra
    end
  rescue JSON::ParserError
    return {}
  end
end

def get_stonith_agents_avail(session)
  code, result = send_cluster_request_with_token(
    session, params[:cluster], 'get_avail_fence_agents'
  )
  return {} if 200 != code
  begin
    sa = JSON.parse(result)
    if (sa["noresponse"] == true) or (sa["notauthorized"] == "true") or (sa["notoken"] == true) or (sa["pacemaker_not_running"] == true)
      return {}
    else
      return sa
    end
  rescue JSON::ParserError
    return {}
  end
end

def get_cluster_name()
  if ISRHEL6
    stdout, stderror, retval = run_cmd(
      PCSAuth.getSuperuserSession, COROSYNC_CMAPCTL, "cluster"
    )
    if retval == 0
      stdout.each { |line|
        match = /^cluster\.name=(.*)$/.match(line)
        return match[1] if match
      }
    end
    begin
      cluster_conf = Cfgsync::ClusterConf.from_file().text()
    rescue
      return ''
    end
    conf_dom = REXML::Document.new(cluster_conf)
    if conf_dom.root and conf_dom.root.name == 'cluster'
      return conf_dom.root.attributes['name']
    end
    return ''
  end

  stdout, stderror, retval = run_cmd(
    PCSAuth.getSuperuserSession, COROSYNC_CMAPCTL, "totem.cluster_name"
  )
  if retval != 0 and not ISRHEL6
    # Cluster probably isn't running, try to get cluster name from
    # corosync.conf
    begin
      corosync_conf = CorosyncConf::parse_string(
        Cfgsync::CorosyncConf.from_file().text()
      )
      # mimic corosync behavior - the last cluster_name found is used
      cluster_name = nil
      corosync_conf.sections('totem').each { |totem|
        totem.attributes('cluster_name').each { |attrib|
          cluster_name = attrib[1]
        }
      }
      return cluster_name if cluster_name
    rescue
      return ''
    end
    return ""
  else
    return stdout.join().gsub(/.*= /,"").strip
  end
end

def get_node_attributes(session, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(session)
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
      :key => e.attributes['name'],
      :value => e.attributes['value']
    }
  }
  node_attrs.each { |_, val| val.sort_by! { |obj| obj[:key] }}
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

def get_fence_levels(session, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(session)
    return {} unless cib_dom
  end

  fence_levels = {}
  cib_dom.elements.each(
    '/cib/configuration/fencing-topology/fencing-level'
  ) { |e|
    target = e.attributes['target']
    fence_levels[target] ||= []
    fence_levels[target] << {
      'level' => e.attributes['index'],
      'devices' => e.attributes['devices']
    }
  }

  fence_levels.each { |_, val| val.sort_by! { |obj| obj['level'].to_i }}
  return fence_levels
end

def get_acls(session, cib_dom=nil)
  unless cib_dom
    cib_dom = get_cib_dom(session)
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

def enable_cluster(session)
  stdout, stderror, retval = run_cmd(session, PCS, "cluster", "enable")
  return false if retval != 0
  return true
end

def disable_cluster(session)
  stdout, stderror, retval = run_cmd(session, PCS, "cluster", "disable")
  return false if retval != 0
  return true
end

def corosync_running?()
  if ISSYSTEMCTL
    `systemctl status corosync.service`
  else
    `service corosync status`
  end
  return $?.success?
end

def corosync_enabled?()
  if ISSYSTEMCTL
    `systemctl is-enabled corosync.service`
  else
    `chkconfig corosync`
  end
  return $?.success?
end

def get_corosync_version()
  begin
    stdout, stderror, retval = run_cmd(
      PCSAuth.getSuperuserSession, COROSYNC, "-v"
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
  if ISSYSTEMCTL
    `systemctl status pacemaker.service`
  else
    `service pacemaker status`
  end
  return $?.success?
end

def pacemaker_enabled?()
  if ISSYSTEMCTL
    `systemctl is-enabled pacemaker.service`
  else
    `chkconfig pacemaker`
  end
  return $?.success?
end

def get_pacemaker_version()
  begin
    stdout, stderror, retval = run_cmd(
      PCSAuth.getSuperuserSession, PACEMAKERD, "-$"
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

def cman_running?()
  if ISSYSTEMCTL
    `systemctl status cman.service`
  else
    `service cman status`
  end
  return $?.success?
end

def get_cman_version()
  begin
    stdout, stderror, retval = run_cmd(
      PCSAuth.getSuperuserSession, CMAN_TOOL, "-V"
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

def pcsd_restart()
  fork {
    sleep(10)
    if ISSYSTEMCTL
      `systemctl restart pcsd`
    else
      `service pcsd restart`
    end
  }
end

def pcsd_enabled?()
  if ISSYSTEMCTL
    `systemctl is-enabled pcsd.service`
  else
    `chkconfig pcsd`
  end
  return $?.success?
end

def get_pcsd_version()
  return PCS_VERSION.split(".").collect { | x | x.to_i }
end

def run_cmd(session, *args)
  options = {}
  return run_cmd_options(session, options, *args)
end

def run_cmd_options(session, options, *args)
  $logger.info("Running: " + args.join(" "))
  start = Time.now
  out = ""
  errout = ""

  proc_block = proc { |pid, stdin, stdout, stderr|
    if options and options.key?('stdin')
      stdin.puts(options['stdin'])
      stdin.close()
    end
    out = stdout.readlines()
    errout = stderr.readlines()
    duration = Time.now - start
    $logger.debug(out)
    $logger.debug(errout)
    $logger.debug("Duration: " + duration.to_s + "s")
  }
  cib_user = session[:username]
  # when running 'id -Gn' to get the groups they are not defined yet
  cib_groups = (session[:usergroups] || []).join(' ')
  $logger.info("CIB USER: #{cib_user}, groups: #{cib_groups}")
  # Open4.popen4 reimplementation which sets ENV in a child process prior
  # to running an external process by exec
  status = Open4::do_popen(proc_block, :init) { |ps_read, ps_write|
    ps_read.fcntl(Fcntl::F_SETFD, Fcntl::FD_CLOEXEC)
    ps_write.fcntl(Fcntl::F_SETFD, Fcntl::FD_CLOEXEC)
    ENV['CIB_user'] = cib_user
    ENV['CIB_user_groups'] = cib_groups
    exec(*args)
  }

  retval = status.exitstatus
  $logger.info("Return Value: " + retval.to_s)
  return out, errout, retval
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

def read_tokens()
  return PCSTokens.new(Cfgsync::PcsdTokens.from_file('').text()).tokens
end

def write_tokens(tokens)
  begin
    cfg = PCSTokens.new(Cfgsync::PcsdTokens.from_file('').text())
    cfg.tokens = tokens
    Cfgsync::PcsdTokens.from_text(cfg.text()).save()
  rescue
    return false
  end
  return true
end

def get_tokens_of_nodes(nodes)
  tokens = {}
  read_tokens.each { |node, token|
    if nodes.include? node
      tokens[node] = token
    end
  }
  return tokens
end

def get_node_token(node)
  tokens = read_tokens()
  if tokens.include? node
    return tokens[node]
  else
    return nil
  end
end

def get_token_node_list()
  return read_tokens.keys
end

def add_prefix_to_keys(hash, prefix)
  new_hash = {}
  hash.each { |k,v|
    new_hash["#{prefix}#{k}"] = v
  }
  return new_hash
end

def check_gui_status_of_nodes(session, nodes, check_mutuality=false, timeout=10)
  options = {}
  options[:check_auth_only] = '' if not check_mutuality
  threads = []
  not_authorized_nodes = []
  online_nodes = []
  offline_nodes = []

  nodes = nodes.uniq.sort
  nodes.each { |node|
    threads << Thread.new {
      code, response = send_request_with_token(
        session, node, 'check_auth', false, options, true, nil, timeout
      )
      if code == 200
        if check_mutuality
          begin
            parsed_response = JSON.parse(response)
            if parsed_response['node_list'] and parsed_response['node_list'].uniq.sort == nodes
              online_nodes << node
            else
              not_authorized_nodes << node
            end
          rescue
            not_authorized_nodes << node
          end
        else
          online_nodes << node
        end
      else
        begin
          parsed_response = JSON.parse(response)
          if parsed_response['notauthorized'] or parsed_response['notoken']
            not_authorized_nodes << node
          else
            offline_nodes << node
          end
        rescue JSON::ParserError
        end
      end
    }
  }
  threads.each { |t| t.join }
  return online_nodes, offline_nodes, not_authorized_nodes
end

def pcs_auth(session, nodes, username, password, force=false, local=true)
  # if no sync is needed, do not report a sync error
  sync_successful = true
  sync_failed_nodes = []
  sync_responses = {}
  # check for already authorized nodes
  if not force
    online, offline, not_authenticated = check_gui_status_of_nodes(
      session, nodes, true
    )
    if not_authenticated.length < 1
      result = {}
      online.each { |node| result[node] = {'status' => 'already_authorized'} }
      offline.each { |node| result[node] = {'status' => 'noresponse'} }
      return result, sync_successful, sync_failed_nodes, sync_responses
    end
  end

  # authorize the nodes locally (i.e. not bidirectionally)
  auth_responses = run_auth_requests(
    session, nodes, nodes, username, password, force, true
  )

  # get the tokens and sync them within the local cluster
  new_tokens = {}
  auth_responses.each { |node, response|
    new_tokens[node] = response['token'] if 'ok' == response['status']
  }
  if not new_tokens.empty?
    cluster_nodes = get_corosync_nodes()
    tokens_cfg = Cfgsync::PcsdTokens.from_file('')
    # only tokens used in pcsd-to-pcsd communication can and need to be synced
    # those are accessible only when running under root account
    if Process.uid != 0
      # other tokens just need to be stored localy for the user
      sync_successful, sync_responses = Cfgsync::save_sync_new_tokens(
        tokens_cfg, new_tokens, [], nil
      )
      return auth_responses, sync_successful, sync_failed_nodes, sync_responses
    end
    sync_successful, sync_responses = Cfgsync::save_sync_new_tokens(
      tokens_cfg, new_tokens, cluster_nodes, $cluster_name
    )
    sync_failed_nodes = []
    sync_not_supported_nodes = []
    sync_responses.each { |node, response|
      if 'not_supported' == response['status']
        sync_not_supported_nodes << node
      elsif response['status'] != 'ok'
        sync_failed_nodes << node
      else
        node_result = response['result'][Cfgsync::PcsdTokens.name]
        if 'not_supported' == node_result
          sync_not_supported_nodes << node
        elsif not ['accepted', 'rejected'].include?(node_result)
          sync_failed_nodes << node
        end
      end
    }
    if not local
      # authorize nodes outside of the local cluster and nodes not supporting
      # the tokens file synchronization in the other direction
      nodes_to_auth = []
      nodes.each { |node|
        nodes_to_auth << node if sync_not_supported_nodes.include?(node)
        nodes_to_auth << node if not cluster_nodes.include?(node)
      }
      auth_responses2 = run_auth_requests(
        session, nodes_to_auth, nodes, username, password, force, false
      )
      auth_responses.update(auth_responses2)
    end
  end

  return auth_responses, sync_successful, sync_failed_nodes, sync_responses
end

def run_auth_requests(session, nodes_to_send, nodes_to_auth, username, password, force=false, local=true)
  data = {}
  nodes_to_auth.each_with_index { |node, index|
    data["node-#{index}"] = node
  }
  data['username'] = username
  data['password'] = password
  data['bidirectional'] = 1 if not local
  data['force'] = 1 if force

  auth_responses = {}
  threads = []
  nodes_to_send.each { |node|
    threads << Thread.new {
      code, response = send_request(session, node, 'auth', true, data)
      if 200 == code
        token = response.strip
        if '' == token
          auth_responses[node] = {'status' => 'bad_password'}
        else
          auth_responses[node] = {'status' => 'ok', 'token' => token}
        end
      else
        auth_responses[node] = {'status' => 'noresponse'}
      end
    }
  }
  threads.each { |t| t.join }
  return auth_responses
end

def send_local_configs_to_nodes(
  session, nodes, force=false, clear_local_permissions=false
)
  configs = Cfgsync::get_configs_local(true)
  if clear_local_permissions
    pcs_config = PCSConfig.new(configs[Cfgsync::PcsdSettings.name].text())
    pcs_config.permissions_local = Permissions::PermissionsSet.new([])
    configs[Cfgsync::PcsdSettings.name].text = pcs_config.text()
  end
  publisher = Cfgsync::ConfigPublisher.new(
    session, configs.values(), nodes, $cluster_name
  )
  return publisher.send(force)
end

def send_local_certs_to_nodes(session, nodes)
  begin
    data = {
      'ssl_cert' => File.read(CRT_FILE),
      'ssl_key' => File.read(KEY_FILE),
      'cookie_secret' => File.read(COOKIE_FILE),
    }
  rescue => e
    return {
      'status' => 'error',
      'text' => "Unable to read certificates: #{e}",
      'node_status' => {},
    }
  end

  crt_errors = verify_cert_key_pair(data['ssl_cert'], data['ssl_key'])
  if crt_errors and not crt_errors.empty?
    return {
      'status' => 'error',
      'text' => "Invalid certificate and/or key: #{crt_errors.join}",
      'node_status' => {},
    }
  end
  secret_errors = verify_cookie_secret(data['cookie_secret'])
  if secret_errors and not secret_errors.empty?
    return {
      'status' => 'error',
      'text' => "Invalid cookie secret: #{secret_errors.join}",
      'node_status' => {},
    }
  end

  node_response = {}
  threads = []
  nodes.each { |node|
    threads << Thread.new {
      code, response = send_request_with_token(
        session, node, '/set_certs', true, data
      )
      node_response[node] = [code, response]
    }
  }
  threads.each { |t| t.join }

  node_error = []
  node_status = {}
  node_response.each { |node, response|
    if response[0] == 200
      node_status[node] = {
        'status' => 'ok',
        'text' => 'Success',
      }
    else
      text = response[1]
      if response[0] == 401
        text = "Unable to authenticate, try running 'pcs cluster auth'"
      elsif response[0] == 400
        begin
          parsed_response = JSON.parse(response[1], {:symbolize_names => true})
          if parsed_response[:noresponse]
            text = "Unable to connect"
          elsif parsed_response[:notoken] or parsed_response[:notauthorized]
            text = "Unable to authenticate, try running 'pcs cluster auth'"
          end
        rescue JSON::ParserError
        end
      end
      node_status[node] = {
        'status' => 'error',
        'text' => text
      }
      node_error << node
    end
  }
  return {
    'status' => node_error.empty?() ? 'ok' : 'error',
    'text' => node_error.empty?() ? 'Success' : \
      "Unable to save pcsd certificates to nodes: #{node_error.join(', ')}",
    'node_status' => node_status,
  }
end

def pcsd_restart_nodes(session, nodes)
  node_response = {}
  threads = []
  nodes.each { |node|
    threads << Thread.new {
      code, response = send_request_with_token(
        session, node, '/pcsd_restart', true
      )
      node_response[node] = [code, response]
    }
  }
  threads.each { |t| t.join }

  node_error = []
  node_status = {}
  node_response.each { |node, response|
    if response[0] == 200
      node_status[node] = {
        'status' => 'ok',
        'text' => 'Success',
      }
    else
      text = response[1]
      if response[0] == 401
        text = "Unable to authenticate, try running 'pcs cluster auth'"
      elsif response[0] == 400
        begin
          parsed_response = JSON.parse(response[1], {:symbolize_names => true})
          if parsed_response[:noresponse]
            text = "Unable to connect"
          elsif parsed_response[:notoken] or parsed_response[:notauthorized]
            text = "Unable to authenticate, try running 'pcs cluster auth'"
          end
        rescue JSON::ParserError
        end
      end
      node_status[node] = {
        'status' => 'error',
        'text' => text
      }
      node_error << node
    end
  }
  return {
    'status' => node_error.empty?() ? 'ok' : 'error',
    'text' => node_error.empty?() ? 'Success' : \
      "Unable to restart pcsd on nodes: #{node_error.join(', ')}",
    'node_status' => node_status,
  }
end

def write_file_lock(path, perm, data)
  begin
    file = nil
    file = File.open(path, 'w', perm)
    file.flock(File::LOCK_EX)
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

def verify_cert_key_pair(cert, key)
  errors = []
  cert_modulus = nil
  key_modulus = nil

  stdout, stderr, retval = run_cmd_options(
    PCSAuth.getSuperuserSession(),
    {
      'stdin' => cert,
    },
    '/usr/bin/openssl', 'x509', '-modulus', '-noout'
  )
  if retval != 0
    errors << "Invalid certificate: #{stderr.join}"
  else
    cert_modulus = stdout.join.strip
  end

  stdout, stderr, retval = run_cmd_options(
    PCSAuth.getSuperuserSession(),
    {
      'stdin' => key,
    },
    '/usr/bin/openssl', 'rsa', '-modulus', '-noout'
  )
  if retval != 0
    errors << "Invalid key: #{stderr.join}"
  else
    key_modulus = stdout.join.strip
  end

  if errors.empty? and cert_modulus and key_modulus
    if cert_modulus != key_modulus
      errors << 'Certificate does not match the key'
    end
  end

  return errors
end

def verify_cookie_secret(secret)
  if secret.empty?
    return ['Cookie secret is empty']
  end
  return []
end

def cluster_status_from_nodes(session, cluster_nodes, cluster_name)
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
  }

  threads = []
  cluster_nodes.uniq.each { |node|
    threads << Thread.new {
      code, response = send_request_with_token(
        session,
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
          else
            parsed_response = status_v1_to_v2(parsed_response)
          end
          node_map[node] = parsed_response
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
  old_status = false
  node_map.each { |node_name, cluster_status|
    # If we were able to get node's cluster name and it's different than
    # requested cluster name, the node belongs to some other cluster and its
    # data should not be used.
    # If we don't know node's cluster name, we keep the data because the node is
    # possibly in our cluster, we just didn't get its status.
    next if cluster_status[:cluster_name] != cluster_name
    cluster_nodes_map[node_name] = cluster_status
    node_status_list << cluster_status[:node]
    old_status = true if '1' == cluster_status[:status_version]
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
  elsif not old_status
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
  # old pcsd doesn't provide info about quorum, use data from any node
  else
    status = overview
    status[:quorate] = nil
    status[:node_list] = node_status_list
    cluster_nodes_map.each { |_, node|
      if node[:status_version] and node[:status_version] == '1' and
          !node[:cluster_settings][:error]
        status = overview.update(node)
        break
      end
    }
  end
  status.delete(:node)

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
        not is_cib_true(status[:cluster_settings]['stonith-enabled'.to_sym])
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
    if old_status
      status[:warning_list] << {
        :message => 'Cluster is running an old version of pcs/pcsd which '\
          + "doesn't provide data for the dashboard.",
        :type => 'old_pcsd'
      }
    else
      status[:error_list] << {
        :message => 'Unable to connect to the cluster.'
      }
    end
    status[:status] == 'unknown'
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
  uptime = `cat /proc/uptime`.chomp.split(' ')[0].split('.')[0].to_i
  mm, ss = uptime.divmod(60)
  hh, mm = mm.divmod(60)
  dd, hh = hh.divmod(24)
  return '%d day%s, %02d:%02d:%02d' % [dd, dd != 1?'s':'', hh, mm, ss]
end

def get_node_status(session, cib_dom)
  node_status = {
      :cluster_name => $cluster_name,
      :groups => [],
      :constraints => {
          # :rsc_location => [],
          # :rcs_colocation => [],
          # :rcs_order => []
      },
      :cluster_settings => {},
      :need_ring1_address => need_ring1_address?,
      :is_cman_with_udpu_transport => is_cman_with_udpu_transport?,
      :acls => get_acls(session, cib_dom),
      :username => session[:username],
      :fence_levels => get_fence_levels(session, cib_dom),
      :node_attr => node_attrs_to_v2(get_node_attributes(session, cib_dom)),
      :nodes_utilization => get_nodes_utilization(cib_dom),
      :known_nodes => []
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

  cluster_settings = getAllSettings(session, cib_dom)
  if not cluster_settings.has_key?('error')
    node_status[:cluster_settings] = cluster_settings
  end

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
    resource_list << ClusterEntity::MasterSlave.new(
      e, crm_dom, rsc_status, nil, operations
    )
  end
  return resource_list
end

def get_resource_by_id(id, cib_dom, crm_dom=nil, rsc_status=nil, operations=false)
  unless cib_dom
    return nil
  end

  e = cib_dom.elements["/cib/configuration/resources//*[@id='#{id}']"]
  unless e
    return nil
  end

  if e.parent.name != 'resources' # if resource is in group, clone or master/slave
    p = get_resource_by_id(
      e.parent.attributes['id'], cib_dom, crm_dom, rsc_status, operations
    )
    return p.get_map[id.to_sym]
  end

  case e.name
    when 'primitive'
      return ClusterEntity::Primitive.new(e, rsc_status, nil, operations)
    when 'group'
      return ClusterEntity::Group.new(e, rsc_status, nil, operations)
    when 'clone'
      return ClusterEntity::Clone.new(e, crm_dom, rsc_status, nil, operations)
    when 'master'
      return ClusterEntity::MasterSlave.new(e, crm_dom, rsc_status, nil, operations)
    else
      return nil
  end
end

def get_crm_mon_dom(session)
  begin
    stdout, _, retval = run_cmd(
      session, CRM_MON, '--one-shot', '-r', '--as-xml'
    )
    if retval == 0
      return REXML::Document.new(stdout.join("\n"))
    end
  rescue
    $logger.error 'Failed to parse crm_mon.'
  end
  return nil
end

def get_cib_dom(session)
  begin
    stdout, _, retval = run_cmd(session, 'cibadmin', '-Q', '-l')
    if retval == 0
      return REXML::Document.new(stdout.join("\n"))
    end
  rescue
    $logger.error 'Failed to parse cib.'
  end
  return nil
end

def node_attrs_to_v2(node_attrs)
  all_nodes_attr = {}
  node_attrs.each { |node, attrs|
    all_nodes_attr[node] = []
    attrs.each { |attr|
      all_nodes_attr[node] << {
        :id => attr[:id],
        :name => attr[:key],
        :value => attr[:value]
      }
    }
  }
  return all_nodes_attr
end

def status_v1_to_v2(status)
  new_status = status.select { |k,_|
    [:cluster_name, :username, :is_cman_with_udpu_transport,
     :need_ring1_address, :cluster_settings, :constraints, :groups,
     :corosync_online, :corosync_offline, :pacemaker_online, :pacemaker_standby,
     :pacemaker_offline, :acls, :fence_levels
    ].include?(k)
  }
  new_status[:node_attr] = node_attrs_to_v2(status[:node_attr])

  resources = ClusterEntity::make_resources_tree(
    ClusterEntity::get_primitives_from_status_v1(status[:resources])
  )
  resources_hash = []
  resources.each { |r|
    resources_hash << r.to_status('2')
  }
  new_status[:resource_list] = resources_hash
  new_status[:node] = status.select { |k,_|
    [:uptime, :corosync, :pacemaker, :cman, :corosync_enabled,
     :pacemaker_enabled, :pcsd_enabled
    ].include?(k)
  }

  new_status[:node].update(
    {
      :id => status[:node_id],
      :quorum => nil,
      :warning_list => [],
      :error_list => [],
      :status => (new_status[:node][:corosync] and
        new_status[:node][:pacemaker]) ? "online" : "offline",
      :status_version => '1'
    }
  )
  new_status[:status_version] = '1'

  return new_status
end

def allowed_for_local_cluster(session, action)
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('{}').text())
  return pcs_config.permissions_local.allows?(
    session[:username], session[:usergroups], action
  )
end

def allowed_for_superuser(session)
  $logger.debug(
    "permission check superuser username=#{session[:username]} groups=#{session[:groups]}"
  )
  if SUPERUSER != session[:username]
    $logger.debug('permission denied')
    return false
  end
  $logger.debug('permission granted for superuser')
  return true
end

def get_default_overview_node_list(clustername)
  nodes = get_cluster_nodes clustername
  node_list = []
  nodes.each { |node|
    node_list << {
      'error_list' => [],
      'warning_list' => [],
      'status' => 'unknown',
      'quorum' => false,
      'name' => node
    }
  }
  return node_list
end
