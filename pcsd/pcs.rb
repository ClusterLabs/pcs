# Wrapper for PCS command
#
require 'open4'
require 'shellwords'
require 'cgi'
require 'net/http'
require 'net/https'
require 'json'
require 'fileutils'

require 'config.rb'
require 'cfgsync.rb'
require 'corosyncconf.rb'

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
    return retval,stdout, stderr
  else
    stdout, stderr, retval = run_cmd(PCS, "stonith", "level", "remove", level, node, devices)
    return retval,stdout, stderr
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
    if stderror.empty?
      return "Error adding permission"
    else
      return stderror.join("\n").strip
    end
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
    if stderror.empty?
      return "Error adding #{user_group}"
    else
      return stderror.join("\n").strip
    end
  end
  return ""
end

def remove_acl_permission(acl_perm_id)
  stdout, stderror, retval = run_cmd(PCS, "acl", "permission", "delete", acl_perm_id.to_s)
  if retval != 0
    if stderror.empty?
      return "Error removing permission"
    else
      return stderror.join("\n").strip
    end
  end
  return ""
end

def remove_acl_usergroup(role_id, usergroup_id)
  stdout, stderror, retval = run_cmd(
    PCS, "acl", "role", "unassign", role_id.to_s, usergroup_id.to_s,
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
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
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
  $logger.info("SCRWT: " + request)
  nodes = get_cluster_nodes(cluster_name)
  return send_nodes_request_with_token(
    nodes, request, post, data, remote, raw_data
  )
end

def send_nodes_request_with_token(nodes, request, post=false, data={}, remote=true, raw_data=nil)
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
      node, request, post, data, remote, raw_data
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

def send_request_with_token(node, request, post=false, data={}, remote=true, raw_data=nil, timeout=30, additional_tokens={}, username=nil)
  token = additional_tokens[node] || get_node_token(node)
  $logger.info "SRWT Node: #{node} Request: #{request}"
  if not token
    return 400,'{"notoken":true}'
  end
  cookies_data = {
    'token' => token,
  }
  return send_request(
    node, request, post, data, remote, raw_data, timeout, cookies_data, username
  )
end

def send_request(node, request, post=false, data={}, remote=true, raw_data=nil, timeout=30, cookies_data={}, username=nil)
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
    if username
      cookies_data_default['CIB_user'] = username.to_s
    else
      cookies_data_default['CIB_user'] = $session[:username].to_s
    end
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
  $logger.info("Adding #{new_nodename} to pcs_settings.conf")
  corosync_nodes = get_corosync_nodes()
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
  pcs_config.update($cluster_name, corosync_nodes)
  sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
  # on version conflict just go on, config will be corrected eventually
  # by displaying the cluster in the web UI
  Cfgsync::save_sync_new_version(
    sync_config, corosync_nodes, $cluster_name, true
  )
  return retval, out.join("\n") + stderror.join("\n")
end

def remove_node(new_nodename, all = false)
  if all
    # we check for a quorum loss warning in remote_remove_nodes
    out, stderror, retval = run_cmd(PCS, "cluster", "node", "remove", new_nodename, "--force")
  else
    out, stderror, retval = run_cmd(PCS, "cluster", "localnode", "remove", new_nodename)
  end
  $logger.info("Removing #{new_nodename} from pcs_settings.conf")
  corosync_nodes = get_corosync_nodes()
  pcs_config = PCSConfig.new(Cfgsync::PcsdSettings.from_file('').text())
  pcs_config.update($cluster_name, corosync_nodes)
  sync_config = Cfgsync::PcsdSettings.from_text(pcs_config.text())
  # on version conflict just go on, config will be corrected eventually
  # by displaying the cluster in the web UI
  Cfgsync::save_sync_new_version(
    sync_config, corosync_nodes, $cluster_name, true
  )
  return retval, out + stderror
end

def get_current_node_name()
  stdout, stderror, retval = run_cmd(CRM_NODE, "-n")
  if retval == 0 and stdout.length > 0
    return stdout[0].chomp()
  end
  return ""
end

def get_corosync_nodes(username=nil)
  run_options = {}
  run_options['username'] = username if username

  stdout, stderror, retval = run_cmd_options(
    run_options, PCS, "status", "nodes", "corosync"
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
  stdout, stderr, retval = run_cmd(PCS,"status","nodes","both")
  stdout.each {|l|
    l = l.chomp
    if l.start_with?("Pacemaker Nodes:")
      in_pacemaker = true
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

def get_cluster_name(username=nil)
  run_options = {}
  run_options['username'] = username if username

  if ISRHEL6
    stdout, stderror, retval = run_cmd_options(
      run_options, COROSYNC_CMAPCTL, "cluster"
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

  stdout, stderror, retval = run_cmd_options(
    run_options, COROSYNC_CMAPCTL, "totem.cluster_name"
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

def run_cmd(*args)
  options = {}
  return run_cmd_options(options, *args)
end

def run_cmd_options(options, *args)
  $logger.info("Running: " + args.join(" "))
  start = Time.now
  out = ""
  errout = ""

  if options and options.key?('username')
    ENV['CIB_user'] = options['username']
  else
    if $session[:username] == SUPERUSER
      ENV['CIB_user'] = $cookies[:CIB_user]
    else
      ENV['CIB_user'] = $session[:username]
    end
  end
  $logger.debug("CIB USER: #{ENV['CIB_user'].to_s}")

  status = Open4::popen4(*args) do |pid, stdin, stdout, stderr|
    if options and options.key?('stdin')
      stdin.puts(options['stdin'])
      stdin.close()
    end
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

def check_gui_status_of_nodes(nodes, check_mutuality=false, timeout=10)
  options = {}
  options[:check_auth_only] = '' if not check_mutuality
  threads = []
  not_authorized_nodes = []
  online_nodes = []
  offline_nodes = []

  nodes = nodes.uniq.sort
  nodes.each { |node|
    threads << Thread.new {
      code, response = send_request_with_token(node, 'check_auth', false, options, true, nil, timeout)
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

def pcs_auth(nodes, username, password, force=false, local=true)
  # if no sync is needed, do not report a sync error
  sync_successful = true
  sync_failed_nodes = []
  sync_responses = {}
  # check for already authorized nodes
  if not force
    online, offline, not_authenticated = check_gui_status_of_nodes(nodes, true)
    if not_authenticated.length < 1
      result = {}
      online.each { |node| result[node] = {'status' => 'already_authorized'} }
      offline.each { |node| result[node] = {'status' => 'noresponse'} }
      return result, sync_successful, sync_failed_nodes, sync_responses
    end
  end

  # authorize the nodes locally (i.e. not bidirectionally)
  auth_responses = run_auth_requests(nodes, nodes, username, password, force, true)

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
        nodes_to_auth, nodes, username, password, force, false
      )
      auth_responses.update(auth_responses2)
    end
  end

  return auth_responses, sync_successful, sync_failed_nodes, sync_responses
end

def run_auth_requests(nodes_to_send, nodes_to_auth, username, password, force=false, local=true)
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
      code, response = send_request(node, 'auth', true, data)
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

def send_local_configs_to_nodes(nodes, force=false, tokens={})
  publisher = Cfgsync::ConfigPublisher.new(
    Cfgsync::get_configs_local(true).values(), nodes, $session[:username],
    $cluster_name, tokens
  )
  return publisher.send(force)
end

def send_local_certs_to_nodes(nodes)
  if SUPERUSER != $session[:username]
    return {
      'status' => 'access_denied',
      'text' => 'Unable to send pcsd certificates: Permission denied',
    }
  end

  data = {
    'ssl_cert' => File.read(CRT_FILE),
    'ssl_key' => File.read(KEY_FILE),
    'cookie_secret' => File.read(COOKIE_FILE),
  }
  node_response = {}
  threads = []
  nodes.each { |node|
    threads << Thread.new {
      code, _ = send_request_with_token(node, '/set_certs', true, data)
      node_response[node] = 200 == code ? 'ok' : 'error'
    }
  }
  threads.each { |t| t.join }

  node_error = []
  node_response.each { |node, response|
    node_error << node if response != 'ok'
  }
  return {
    'status' => node_error.empty?() ? 'ok' : 'error',
    'text' => node_error.empty?() ? 'Success' : \
      "Unable to save pcsd certificates to nodes: #{node_error.join(', ')}",
  }
end

def pcsd_restart_nodes(nodes)
  node_response = {}
  threads = []
  nodes.each { |node|
    threads << Thread.new {
      code, _ = send_request_with_token(node, '/pcsd_restart', true)
      node_response[node] = 200 == code ? 'ok' : 'error'
    }
  }
  threads.each { |t| t.join }

  node_error = []
  node_response.each { |node, response|
    node_error << node if response != 'ok'
  }
  return {
    'status' => node_error.empty?() ? 'ok' : 'error',
    'text' => node_error.empty?() ? 'Success' : \
      "Unable to restart pcsd on nodes: #{node_error.join(', ')}",
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
