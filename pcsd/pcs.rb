# Wrapper for PCS command
#
require 'open4'
require 'shellwords'
require 'cgi'
require 'net/http'
require 'net/https'

def getAllSettings()
  stdout, stderr, retval = run_cmd(PCS, "property")
  stdout.map(&:chomp!)
  stdout.map(&:strip!)
  stdout2, stderr2, retval2 = run_cmd(PENGINE, "metadata")
  metadata = stdout2.join
  ret = {}
  if retval == 0 and retval2 == 0
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

    stdout.each {|line|
      key,val = line.split(': ', 2)
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

def add_fence_level (level, devices, node, remove = false)
  if not remove
    stdout, stderr, retval = run_cmd(PCS, "stonith", "level", "add", level, node, devices)
    return retval
  else
    stdout, stderr, retval = run_cmd(PCS, "stonith", "level", "remove", level, node, devices)
    return retval
  end
end

def add_node_attr(node, key, value)
  stdout, stderr, retval = run_cmd(PCS, "property", "set", "--node", node, key.to_s + '=' + value.to_s)
  return retval
end

def add_meta_attr(resource, key, value)
  stdout, stderr, retval = run_cmd(PCS,"resource","meta",resource,key.to_s + "=" + value.to_s)
  return retval
end

def add_location_constraint(resource, node, score)
  if node == ""
    return "Bad node"
  end

  if score == ""
    nodescore = node
  else
    nodescore = node +"="+score
  end

  stdout, stderr, retval = run_cmd(
    PCS, "constraint", "location", resource, "prefers", nodescore,
    "--autocorrect"
  )
  return retval, stderr.join(' ')
end

def add_location_constraint_rule(resource, rule, score, force=false)
  cmd = [PCS, "constraint", "location", "--autocorrect", resource, "rule"]
  if score != ''
    if is_score(score.upcase)
      cmd << "score=#{score.upcase}"
    else
      cmd << "score-attribute=#{score}"
    end
  end
  cmd.concat(rule.shellsplit())
  cmd << '--force' if force
  stdout, stderr, retval = run_cmd(*cmd)
  return retval, stderr.join(' ')
end

def add_order_constraint(
    resourceA, resourceB, actionA, actionB, score, symmetrical=true, force=false
)
  sym = symmetrical ? "symmetrical" : "nonsymmetrical"
  if score != ""
    score = "score=" + score
  end
  command = [
    PCS, "constraint", "order", actionA, resourceA, "then", actionB, resourceB,
    score, sym, "--autocorrect"
  ]
  command << '--force' if force
  stdout, stderr, retval = run_cmd(*command)
  return retval, stderr.join(' ')
end

def add_order_set_constraint(resource_set_list, force=false)
  command = [PCS, "constraint", "order", "--autocorrect"]
  resource_set_list.each { |resource_set|
    command << "set"
    command.concat(resource_set)
  }
  command << '--force' if force
  stdout, stderr, retval = run_cmd(*command)
  return retval, stderr.join(' ')
end

def add_colocation_constraint(resourceA, resourceB, score, force=false)
  if score == "" or score == nil
    score = "INFINITY"
  end
  command = [
    PCS, "constraint", "colocation", "add", resourceA, resourceB, score,
    "--autocorrect"
  ]
  command << '--force' if force
  stdout, stderr, retval = run_cmd(*command)
  return retval, stderr.join(' ')
end

def remove_constraint(constraint_id)
  stdout, stderror, retval = run_cmd(PCS, "constraint", "remove", constraint_id)
  $logger.info stdout
  return retval
end

def remove_constraint_rule(rule_id)
  stdout, stderror, retval = run_cmd(
    PCS, "constraint", "rule", "remove", rule_id
  )
  $logger.info stdout
  return retval
end

def add_acl_role(name, description)
  cmd = [PCS, "acl", "role", "create", name.to_s]
  if description.to_s != ""
    cmd << "description=#{description.to_s}"
  end
  stdout, stderror, retval = run_cmd(*cmd)
  if retval != 0
    return stderror.join("\n").strip
  end
  return ""
end

def add_acl_permission(acl_role_id, perm_type, xpath_id, query_id)
  stdout, stderror, retval = run_cmd(
    PCS, "acl", "permission", "add", acl_role_id.to_s, perm_type.to_s,
    xpath_id.to_s, query_id.to_s
  )
  if retval != 0
    return stderror.join("\n").strip
  end
  return ""
end

def add_acl_usergroup(acl_role_id, user_group, name)
  if (user_group == "user") or (user_group == "group")
    stdout, stderr, retval = run_cmd(
      PCS, "acl", user_group, "create", name.to_s, acl_role_id.to_s
    )
    if retval == 0
      return ""
    end
    if not /^error: (user|group) #{name.to_s} already exists$/i.match(stderr.join("\n").strip)
      return stderr.join("\n").strip
    end
  end
  stdout, stderror, retval = run_cmd(
    PCS, "acl", "role", "assign", acl_role_id.to_s, name.to_s
  )
  if retval != 0
    return stderror.join("\n").strip
  end
  return ""
end

def remove_acl_permission(acl_perm_id)
  stdout, stderror, retval = run_cmd(PCS, "acl", "permission", "delete", acl_perm_id.to_s)
  if retval != 0
    return stderror.join("\n").chomp
  end
  return ""
end

def remove_acl_usergroup(role_id, usergroup_id)
  stdout, stderror, retval = run_cmd(
    PCS, "acl", "role", "unassign", role_id.to_s, usergroup_id.to_s,
    "--autodelete"
  )
  if retval != 0
    return stderror.join("\n").chomp
  end
  return ""
end

def get_node_token(node)
  out, stderror, retval = run_cmd(PCS, "cluster", "token", node)
  return retval, out
end

def get_token_node_list()
  out, stderror, retval = run_cmd(PCS, "cluster", "token-nodes")
  return retval, out
end

# Gets all of the nodes specified in the pcs config file for the cluster
def get_cluster_nodes(cluster_name)
  pcs_config = PCSConfig.new
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

def send_cluster_request_with_token(cluster_name, request, post=false, data={}, remote=true, raw_data=nil)
  out = ""
  code = 0
  nodes = get_cluster_nodes(cluster_name)

  # If we're removing nodes, we don't send this to one of the nodes we're
  # removing, unless we're removing all nodes

  $logger.info("SCRWT: " + request)
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
    code, out = send_request_with_token(node,request, post, data, remote, raw_data)
    $logger.info "Node: #{node} Request: #{request}"
    if out != '{"noresponse":true}' and out != '{"pacemaker_not_running":true}'
      break
    end
    $logger.info "No response: Node: #{node} Request: #{request}"
  end
  return code,out
end

def send_request_with_token(node, request, post=false, data={}, remote=true, raw_data=nil, timeout=30)
  start = Time.now
  begin
    retval, token = get_node_token(node)
    if retval != 0
      return 400,'{"notoken":true}'
    end

    token = token[0].strip

    request = "/#{request}" if not request.start_with?("/")

    if remote
      uri = URI.parse("https://#{node}:2224/remote" + request)
    else
      uri = URI.parse("https://#{node}:2224" + request)
    end

    if post
      req = Net::HTTP::Post.new(uri.path)
      raw_data ? req.body = raw_data : req.set_form_data(data)
    else
      req = Net::HTTP::Get.new(uri.path)
      req.set_form_data(data)
    end
    cookies_to_send = [CGI::Cookie.new("name" => 'token', "value" => token).to_s]
    cookies_to_send << CGI::Cookie.new("name" =>  "CIB_user", "value" => $session[:username].to_s).to_s
    req.add_field("Cookie",cookies_to_send.join(";"))
    myhttp = Net::HTTP.new(uri.host, uri.port)
    myhttp.use_ssl = true
    myhttp.verify_mode = OpenSSL::SSL::VERIFY_NONE
    res = myhttp.start do |http|
      http.read_timeout = timeout
      http.request(req)
    end
    return res.code.to_i, res.body
  rescue Exception => e
    $logger.info "No response from: #{node} request: #{request}"
    return 400,'{"noresponse":true}'
  end
end

def add_node(new_nodename,all = false, auto_start=true)
  if all
    if auto_start
      out, stderror, retval = run_cmd(PCS, "cluster", "node", "add", new_nodename, "--start", "--enable")
    else
      out, stderror, retval = run_cmd(PCS, "cluster", "node", "add", new_nodename)
    end
  else
    out, stderror, retval = run_cmd(PCS, "cluster", "localnode", "add", new_nodename)
  end
  $logger.info("Adding #{new_nodename} from pcs_settings.conf")
  pcs_config = PCSConfig.new
  pcs_config.update($cluster_name,get_corosync_nodes())
  return retval, out.join("\n") + stderror.join("\n")
end

def remove_node(new_nodename, all = false)
  if all
    out, stderror, retval = run_cmd(PCS, "cluster", "node", "remove", new_nodename)
  else
    out, stderror, retval = run_cmd(PCS, "cluster", "localnode", "remove", new_nodename)
  end
  $logger.info("Removing #{new_nodename} from pcs_settings.conf")
  pcs_config = PCSConfig.new
  pcs_config.update($cluster_name,get_corosync_nodes())
  return retval, out + stderror
end

def get_current_node_name()
  stdout, stderror, retval = run_cmd(CRM_NODE, "-n")
  if retval == 0 and stdout.length > 0
    return stdout[0].chomp()
  end
  return ""
end

def get_corosync_nodes()
  stdout, stderror, retval = run_cmd(PCS, "status", "nodes", "corosync")
  if retval != 0
    return []
  end

  stdout.each {|x| x.strip!}
  corosync_online = stdout[1].sub(/^.*Online:/,"").strip
  corosync_offline = stdout[2].sub(/^.*Offline:/,"").strip
  corosync_nodes = (corosync_online.split(/ /)) + (corosync_offline.split(/ /))

  return corosync_nodes
end

# Get pacemaker nodes, but if they are not present fall back to corosync
def get_nodes()
  stdout, stderr, retval = run_cmd(PCS, "status", "nodes")
  if retval != 0
    stdout, stderr, retval = run_cmd(PCS, "status", "nodes", "corosync")
  end

  online = stdout[1]
  offline = stdout[2]

  if online
    online = online.split(' ')[1..-1].sort
  else
    online = []
  end

  if offline
    offline = offline.split(' ')[1..-1].sort
  else
    offline = []
  end

  [online, offline]
end

def get_resource_agents_avail()
  code, result = send_cluster_request_with_token(params[:cluster], 'get_avail_resource_agents')
  ra = JSON.parse(result)
  if (ra["noresponse"] == true) or (ra["notauthorized"] == "true") or (ra["notoken"] == true) or (ra["pacemaker_not_running"] == true)
    return {}
  else
    return ra
  end
end

def get_stonith_agents_avail()
  code, result = send_cluster_request_with_token(params[:cluster], 'get_avail_fence_agents')
  sa = JSON.parse(result)
  if (sa["noresponse"] == true) or (sa["notauthorized"] == "true") or (sa["notoken"] == true) or (sa["pacemaker_not_running"] == true)
    return {}
  else
    return sa
  end
end

def get_cluster_version()
  if ISRHEL6
    stdout, stderror, retval = run_cmd(COROSYNC_CMAPCTL, "cluster")
    if retval == 0
      stdout.each { |line|
        match = /^cluster\.name=(.*)$/.match(line)
        return match[1] if match
      }
    end
    begin
      cluster_conf = File.open('/etc/cluster/cluster.conf').read
    rescue
      return ''
    end
    conf_dom = REXML::Document.new(cluster_conf)
    if conf_dom.root and conf_dom.root.name == 'cluster'
      return conf_dom.root.attributes['name']
    end
    return ''
  end

  stdout, stderror, retval = run_cmd(COROSYNC_CMAPCTL,"totem.cluster_name")
  if retval != 0 and not ISRHEL6
    # Cluster probably isn't running, try to get cluster name from
    # corosync.conf
    begin
      corosync_conf = File.open("/etc/corosync/corosync.conf").read
    rescue
      return ""
    end
    in_totem = false
    current_level = 0
    corosync_conf.each_line do |line|
      if line =~ /totem\s*\{/
        in_totem = true
      end
      if in_totem
        md = /cluster_name:\s*(\w+)/.match(line)
        if md
          return md[1]
        end
      end
      if in_totem and line =~ /\}/
        in_totem = false
      end
    end

    return ""
  else
    return stdout.join().gsub(/.*= /,"").strip
  end
end

def get_node_attributes()
  stdout, stderr, retval = run_cmd(PCS, "property", "list")
  if retval != 0
    return {}
  end

  attrs = {}
  found = false
  stdout.each { |line|
    if not found
      if line.strip.start_with?("Node Attributes:")
        found = true
      end
      next
    end
    if not line.start_with?(" ")
      break
    end
    sline = line.split(":", 2)
    nodename = sline[0].strip
    attrs[nodename] = []
    sline[1].strip.split(" ").each { |attr|
      key, val = attr.split("=", 2)
      attrs[nodename] << {:key => key, :value => val}
    }
  }
  return attrs
end

def get_fence_levels()
  stdout, stderr, retval = run_cmd(PCS, "stonith", "level")
  if retval != 0 or stdout == ""
    return {}
  end

  fence_levels = {}
  node = ""
  stdout.each {|line|
    if line.start_with?(" Node: ")
      node = line.split(":",2)[1].strip
      next
    end
    fence_levels[node] ||= []
    md = / Level (\S+) - (.*)$/.match(line)
    fence_levels[node] << {"level" => md[1], "devices" => md[2]}
  }
  return fence_levels
end

def get_acls()
  stdout, stderr, retval = run_cmd(PCS, "acl", "show")
  if retval != 0 or stdout == ""
    return []
  end

  ret_val = {}
  state = nil
  user = ""
  role = ""

  stdout.each do |line|
    if m = /^User: (.*)$/.match(line)
      user = m[1]
      state = "user"
      ret_val[state] ||= {}
      ret_val[state][user] ||= []
      next
    elsif m = /^Group: (.*)$/.match(line)
      user = m[1]
      state = "group"
      ret_val[state] ||= {}
      ret_val[state][user] ||= []
      next
    elsif m = /^Role: (.*)$/.match(line)
      role = m[1]
      state = "role"
      ret_val[state] ||= {}
      ret_val[state][role] ||= {}
      next
    end

    case state
    when "user", "group"
      m = /^  Roles: (.*)$/.match(line)
      ret_val[state][user] ||= []
      m[1].scan(/\S+/).each {|urole|
        ret_val[state][user] << urole
      }
    when "role"
      ret_val[state][role] ||= {}
      ret_val[state][role]["permissions"] ||= []
      ret_val[state][role]["description"] ||= ""
      if m = /^  Description: (.*)$/.match(line)
        ret_val[state][role]["description"] = m[1]
      elsif m = /^  Permission: (.*)$/.match(line)
        ret_val[state][role]["permissions"] << m[1]
      end
    end
  end
  return ret_val
end

def enable_cluster()
  stdout, stderror, retval = run_cmd(PCS, "cluster", "enable")
  return false if retval != 0
  return true
end

def disable_cluster()
  stdout, stderror, retval = run_cmd(PCS, "cluster", "disable")
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
    stdout, stderror, retval = run_cmd(COROSYNC, "-v")
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
    stdout, stderror, retval = run_cmd(PACEMAKERD, "-$")
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
    stdout, stderror, retval = run_cmd(CMAN_TOOL, "-V")
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

def run_cmd(*args)
  $logger.info("Running: " + args.join(" "))
  start = Time.now
  out = ""
  errout = ""
  if $session[:username] == "hacluster"
    ENV['CIB_user'] = $cookies[:CIB_user]
  else
    ENV['CIB_user'] = $session[:username]
  end
  $logger.debug("CIB USER: #{ENV['CIB_user'].to_s}")
  status = Open4::popen4(*args) do |pid, stdin, stdout, stderr|
    out = stdout.readlines()
    errout = stderr.readlines()
    duration = Time.now - start
    $logger.debug(out)
    $logger.debug("Duration: " + duration.to_s + "s")
  end
  retval = status.exitstatus
  $logger.debug("Return Value: " + retval.to_s)
  return out, errout, retval
end

def is_score(score)
  return !!/^[+-]?((INFINITY)|(\d+))$/.match(score)
end
