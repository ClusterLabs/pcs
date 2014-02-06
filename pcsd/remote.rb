require 'json'
require 'net/http'
require 'uri'
require 'pcs.rb'
require 'resource.rb'
require 'open3'

# Commands for remote access
def remote(params,request)
  case (params[:command])
  when "status"
    return node_status(params)
  when "status_all"
    return status_all(params)
  when "auth"
    return auth(params,request)
  when "check_auth"
    return check_auth(params, request)
  when "resource_status"
    return resource_status(params)
  when "setup_cluster"
    return setup_cluster(params)
  when "create_cluster"
    return create_cluster(params)
  when "get_cib"
    return get_cib(params)
  when "get_corosync_conf"
    return get_corosync_conf(params)
  when "set_corosync_conf"
    if set_corosync_conf(params)
      return "Succeeded"
    else
      return "Failed"
    end
  when "cluster_start"
    return cluster_start(params)
  when "cluster_stop"
    return cluster_stop(params)
  when "node_restart"
    return node_restart(params)
  when "node_standby"
    return node_standby(params)
  when "node_unstandby"
    return node_unstandby(params)
  when "cluster_enable"
    return cluster_enable(params)
  when "cluster_disable"
    return cluster_disable(params)
  when "resource_start"
    return resource_start(params)
  when "resource_stop"
    return resource_stop(params)
  when "resource_cleanup"
    return resource_cleanup(params)
  when "check_gui_status"
    return check_gui_status(params)
  when "node_available"
    return remote_node_available(params)
  when "add_node_all"
    return remote_add_node(params,true)
  when "add_node"
    return remote_add_node(params,false)
  when "remove_nodes"
    return remote_remove_nodes(params)
  when "remove_node"
    return remote_remove_node(params)
  when "resource_form"
    return resource_form(params)
  when "fence_device_form"
    return fence_device_form(params)
  when "update_resource"
    return update_resource(params)
  when "update_fence_device"
    return update_fence_device(params)
  when "resource_metadata"
    return resource_metadata(params)
  when "fence_device_metadata"
    return fence_device_metadata(params)
  when "get_avail_resource_agents"
    return get_avail_resource_agents(params)
  when "get_avail_fence_agents"
    return get_avail_fence_agents(params)
  when "remove_resource"
    return remove_resource(params)
  when "add_constraint"
    return add_constraint(params)
  when "add_constraint_remote"
    return add_constraint_remote(params)
  when "add_group"
    return add_group(params)
  when "update_cluster_settings"
    return update_cluster_settings(params)
  when "cluster_destroy"
    return cluster_destroy(params)
  when "get_wizard"
    return get_wizard(params)
  when "wizard_submit"
    return wizard_submit(params)
  else
    return [404, "Unknown Request"]
  end
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
    code, response = send_request_with_token(params[:name], 'cluster_stop', true)
  else
    $logger.info "Starting Daemons"
    output =  `#{PCS} cluster stop`
    $logger.debug output
    return output
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
    code, response = send_request_with_token(params[:name], 'node_standby', true)
  else
    $logger.info "Standby Node"
    stdout, stderr, retval = run_cmd(PCS,"cluster","standby",params[:node])
    return stdout
  end
end

def node_unstandby(params)
  if params[:name]
    code, response = send_request_with_token(params[:name], 'node_unstandby', true)
  else
    $logger.info "Standby Node"
    stdout, stderr, retval = run_cmd(PCS,"cluster","unstandby",params[:node])
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

def get_cib(parasm)
  cib, stderr, retval = run_cmd(CIBADMIN, "-Ql")
  if retval != 0
    return [400, "Unable to get CIB: " + cib.to_s + stderr.to_s]
  else
    return [200, cib]
  end
end

def get_corosync_conf(params)
  f = File.open("/etc/corosync/corosync.conf",'r')
  return f.read
end

def set_corosync_conf(params)
  if params[:corosync_conf] != nil and params[:corosync_conf] != ""
    begin
      FileUtils.cp(COROSYNC_CONF,COROSYNC_CONF + "." + Time.now.to_i.to_s)
    rescue
    end
    File.open("/etc/corosync/corosync.conf",'w') {|f|
      f.write(params[:corosync_conf])
    }
    return true
  else
    return false
    $logger.info "Invalid corosync.conf file"
  end
end

def check_gui_status(params)
  node_results = {}
  if params[:nodes] != nil and params[:nodes] != ""
    node_array = params[:nodes].split(",")
    Open3.popen3(PCS, "cluster", "pcsd-status", *node_array) { |stdin, stdout, stderr, wait_thr|
      exit_status = wait_thr.value
      stdout.readlines.each {|l|
	l = l.chomp
	out = l.split(/: /)
	node_results[out[0].strip] = out[1]
      }
    }
  end
  return JSON.generate(node_results)
end

def remote_node_available(params)
  if File.exist?("/etc/corosync/corosync.conf") or File.exist?("/var/lib/pacemaker/cib/cib.xml")
    return JSON.generate({node_available: false})
  end
  return JSON.generate({node_available: true})
end

def remote_add_node(params,all = false)
  auto_start = false
  if params[:auto_start] and params[:auto_start] == "1"
    auto_start = true
  end

  if params[:new_nodename] != nil
    retval, output =  add_node(params[:new_nodename],all,auto_start)
  end

  if retval == 0
    return [200,JSON.generate([retval,get_corosync_conf([])])]
  end

  return [400,output]
end

def remote_remove_nodes(params)
  count = 0
  out = ""
  while params["nodename-" + count.to_s]
    retval, output = remove_node(params["nodename-"+count.to_s],true)
    out = out + output.join("\n")
    count = count + 1
  end
  return out
end

def remote_remove_node(params)
  if params[:remove_nodename] != nil
    retval, output = remove_node(params[:remove_nodename])
  else
    return 404, "No nodename specified"
  end

  if retval == 0
    return JSON.generate([retval,get_corosync_conf([])])
  end

  return JSON.generate([retval,output])
end

def setup_cluster(params)
  $logger.info("Setting up cluster: " + params.inspect)
  nodes = params[:nodes].split(',')
  stdout, stderr, retval = run_cmd(PCS, "cluster", "setup", "--enable", "--start", "--name",params[:clustername], *nodes)
  if retval != 0
    return [400, stdout.join("\n") + stderr.join("\n")]
  end
  return 200
end

def create_cluster(params)
  if set_corosync_conf(params)
    cluster_start()
  else
    return "Failed"
  end
end

def node_status(params)
  if params[:node] != nil and params[:node] != "" and params[:node] != $cur_node_name
    return send_request_with_token(params[:node],"status?hello=1")
  end

  uptime = `cat /proc/uptime`.chomp.split(' ')[0].split('.')[0].to_i
  mm, ss = uptime.divmod(60)
  hh, mm = mm.divmod(60)
  dd, hh = hh.divmod(24)
  uptime = "%d days, %02d:%02d:%02d" % [dd, hh, mm, ss]

  `systemctl status corosync.service`
  corosync_status = $?.success?
  `systemctl status pacemaker.service`
  pacemaker_status = $?.success?

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
  node_id = get_local_node_id()
  resource_list, group_list = getResourcesGroups(false,true)
  stonith_resource_list, stonith_group_list = getResourcesGroups(true,true)
  stonith_resource_list.each {|sr| sr.stonith = true}
  resource_list = resource_list + stonith_resource_list
  out_rl = []
  resource_list.each {|r|
    out_nodes = []
    oConstraints = []
    r.nodes.each{|n|
      out_nodes.push(n.name)
    }
    out_rl.push({:id => r.id, :agentname => r.agentname, :active => r.active,
		:nodes => out_nodes, :group => r.group, :clone => r.clone,
		:failed => r.failed, :orphaned => r.orphaned, :options => r.options,
    		:stonith => r.stonith, :ms => r.ms, :disabled => r.disabled,
    		:operations => r.operations, :instance_attr => r.instance_attr,
    		:meta_attr => r.meta_attr})
  }
  constraints = getAllConstraints()
  cluster_settings = getAllSettings()
  status = {"uptime" => uptime, "corosync" => corosync_status, "pacemaker" => pacemaker_status,
 "corosync_online" => corosync_online, "corosync_offline" => corosync_offline,
 "pacemaker_online" => pacemaker_online, "pacemaker_offline" => pacemaker_offline,
 "pacemaker_standby" => pacemaker_standby,
 "cluster_name" => $cluster_name, "resources" => out_rl, "groups" => group_list,
 "constraints" => constraints, "cluster_settings" => cluster_settings, "node_id" => node_id}
  ret = JSON.generate(status)
  return ret
end

def status_all(params, nodes = [])
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
    }
  }
  threads.each { |t| t.join }

  # Get full list of nodes and see if we need to update the configuration
  node_list = []
  final_response.each { |fr,n|
    node_list += n["corosync_offline"]
    node_list += n["corosync_online"]
    node_list += n["pacemaker_offline"]
    node_list += n["pacemaker_online"]
  }

  node_list.uniq!
  if node_list.length > 0
    config = PCSConfig.new
    old_node_list = config.get_nodes(params[:cluster])
    if old_node_list & node_list != old_node_list or old_node_list.size!=node_list.size
      $logger.info("Updating node list for: " + params[:cluster] + " " + old_node_list.inspect + "->" + node_list.inspect)
      config.update(params[:cluster], node_list)
      return status_all(params, node_list)
    end
  end
  $logger.debug("NODE LIST: " + node_list.inspect)
  return JSON.generate(final_response)
end

def auth(params,request)
  token =  PCSAuth.validUser(params['username'],params['password'], true, request)
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

# We can't pass username/password on the command line for security purposes
def pcs_auth(nodes, username, password, force=False)
  command = [PCS, "cluster", "auth", "--local"] + nodes
  command += ["--force"] if force
  Open3.popen3(*command) {|stdin, stdout, stderr, wait_thr|
    begin
      while line = stdout.readpartial(4096)
	if line =~ /Username: \Z/
	  stdin.write(username + "\n")
	end

	if line =~ /Password: \Z/
	  stdin.write(password + "\n")
	end
      end
    rescue EOFError
    end
  }
end

# If we get here, we're already authorized
def check_auth(params, request)
  return true
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
  @resources, @groups, retval = getResourcesGroups()
  if retval != 0
    return "Unable to get options, pacemaker is not running on node"
  end
  @existing_resource = true
  @resources.each do |r|
    if r.id == params[:resource]
      @cur_resource = r
    end
  end
  if @cur_resource
    @cur_resource.options = getResourceOptions(@cur_resource.id)
    @resource_agents = getResourceAgents(@cur_resource.agentname)
    @resource = @resource_agents[@cur_resource.agentname.gsub('::',':')]
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
  @resources, @groups, retval = getResourcesGroups(true)
  if retval != 0
    return "Unable to get options, pacemaker is not running on node"
  end

  @cur_resource = nil
  @resources.each do |r|
    if r.id == params[:resource]
      @cur_resource = r
      break
    end
  end

  if @cur_resource
    @cur_resource.options = getResourceOptions(@cur_resource.id,true)
    @resource_agents = getFenceAgents(@cur_resource.agentname)
    @existing_resource = true
    @fenceagent = @resource_agents[@cur_resource.agentname.gsub(/.*:/,"")]
    erb :fenceagentform
  else
    "Can't find fence device"
  end
end

# Creates resource if params[:resource_id] is not set
def update_resource (params)
  param_line = getParamLine(params)
  if not params[:resource_id]
    out, stderr, retval = run_cmd(PCS, "resource", "create", params[:name], params[:resource_type],
	    *(param_line.split(" ")))
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
    run_cmd(PCS, "resource", "update", params[:resource_id], *(param_line.split(" ")))
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
    run_cmd(PCS, "resource", "master", params[:resource_id] + "-master", params[:resource_id])
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
  param_line = getParamLine(params)
  logger.info param_line

  param_line = getParamLine(params)
  if not params[:resource_id]
    out, stderr, retval = run_cmd(PCS, "stonith", "create", params[:name], params[:resource_type],
	    *(param_line.split(" ")))
    if retval != 0
      return JSON.generate({"error" => "true", "stderr" => stderr, "stdout" => out})
    end
    return "{}"
  end

  if param_line.length != 0
    out, stderr, retval = run_cmd(PCS, "stonith", "update", params[:resource_id], *(param_line.split(" ")))
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
  @fenceagent.required_options, @fenceagent.optional_options = getFenceAgentMetadata(params[:resourcename])
  @new_fenceagent = params[:new]
  
  erb :fenceagentform
end

def remove_resource (params)
  errors = ""
  params.each { |k,v|
    if k.index("resid-") == 0
      out, errout, retval = run_cmd(PCS, "resource", "delete", k.gsub("resid-",""))
      if retval != 0
	errors += "Unable to remove: " + k.gsub("resid-","") + "\n"
      end
    end
  }
  if errors == ""
    return 200
  else
    logger.info("Remove resource errors:\n"+errors)
    return [500, errors]
  end
end

def add_constraint(params)
  if params[:location_constraint]
    params.each {|k,v|
      if k.start_with?("deny-") and v == "on"
	score = "-INFINITY"
	add_location_constraint(params[:cur_resource], k.split(/-/,2)[1], score)
      elsif k.start_with?("allow-") and v == "on"
	score = "INFINITY"
	add_location_constraint(params[:cur_resource], k.split(/-/,2)[1], score)
      elsif k.start_with?("score-") and v != ""
	score = v
	add_location_constraint(params[:cur_resource], k.split(/-/,2)[1], score)
      end
    }
  elsif params[:order_constraint]
    params.each {|k,v|
      if k.start_with?("order-") and v != ""
	if v.start_with?("before-")
	  score = "INFINITY"
	  if params["symmetrical-" + v.split(/-/,2)[1]] == "on"
	    sym = true
	  else
	    sym = false
	  end
	  add_order_constraint(v.split(/-/,2)[1], params[:cur_resource], score, sym)
	elsif v.start_with?("after-")
	  score = "INFINITY"
	  if params["symmetrical-" + v.split(/-/,2)[1]] == "on"
	    sym = true
	  else
	    sym = false
	  end
	  add_order_constraint(params[:cur_resource], v.split(/-/,2)[1], score, sym)
	end
      end
    }
  elsif params[:colocation_constraint]
    params.each {|k,v|
      if k.start_with?("order-") and v != ""
	if v.start_with?("together-")
	  if params["score-" + v.split(/-/,2)[1]] != nil
	    score = params["score-" + v.split(/-/,2)[1]]
	  else
	    score = "INFINITY"
	  end
	  add_colocation_constraint(params[:cur_resource], v.split(/-/,2)[1], score)
	elsif v.start_with?("apart-")
	  if params["score-" + v.split(/-/,2)[1]] != nil
	    score = params["score-" + v.split(/-/,2)[1]]
	  else
	    score = "-INFINITY"
	  end
	  add_colocation_constraint(params[:cur_resource], v.split(/-/,2)[1], score)
	end
      end
    }
  end
end

def add_constraint_remote(params)
  case params["c_type"]
  when "loc"
    retval = add_location_constraint(params["res_id"], params["node_id"],
				     params["score"])
  when "ord"
    resA = params["res_id"]
    resB = params["target_res_id"]
    if params["order"] == "before"
      resA, resB = resB, resA
    end

    retval = add_order_constraint(resA, resB, params["score"])
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

    retval = add_colocation_constraint(resA, resB, score)
  else
    return [400, "Unknown constraint type: #{params["ctype"]}"]
  end

  if retval == 0
    return [200, "Successfully added constraint"]
  else
    return [400, "Error adding constraint"]
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
  p "Settings"
  pp settings
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
    run_cmd(PCS, "property", "set", name + "=" + val)
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
  out, errout, retval = run_cmd(COROSYNC_CMAPCTL, "-g", "runtime.votequorum.this_node_id")
  if retval != 0
    return ""
  else
    return out[0].split(/ = /)[1].strip()
  end
end
