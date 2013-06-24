# Wrapper for PCS command
#

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

# stickyness is ignored for now
def add_location_constraint(resource, node, score, stickyness)
  if score == ""
    score = "INFINITY"
  end
  id = "loc_" + node + "_" + resource
  $logger.info [PCS, "constraint", "location", "add", id, resource, node, score]
  Open3.popen3(PCS, "constraint", "location", "add", id, resource,
	       node, score) { |stdin, stdout, stderror, waitth|
    $logger.info stdout.readlines()
    return waitth.value
  }
end

def add_order_constraint(resourceA, resourceB, score, symmetrical = true)
  sym = symmetrical ? "symmetrical" : "nonsymmetrical"
  if score != ""
    score = "score=" + score
  end
  $logger.info [PCS, "constraint", "order", "add", resourceA, resourceB, score, sym]
  Open3.popen3(PCS, "constraint", "order", "add", resourceA,
	       resourceB, score, sym) { |stdin, stdout, stderror, waitth|
    $logger.info stdout.readlines()
    return waitth.value
  }
end

def add_colocation_constraint(resourceA, resourceB, score)
  if score == "" or score == nil
    score = "INFINITY"
  end
  $logger.info [PCS, "constraint", "colocation", "add", resourceA, resourceB, score]
  Open3.popen3(PCS, "constraint", "colocation", "add", resourceA,
	       resourceB, score) { |stdin, stdout, stderror, waitth|
    $logger.info stdout.readlines()
    return waitth.value
  }
end

def remove_constraint(constraint_id)
  stdout, stderror, retval = run_cmd(PCS, "constraint", "rm", constraint_id)
  $logger.info stdout
  return retval
end

def get_node_token(node)
  out, stderror, retval = run_cmd(PCS, "cluster", "token", node)
  return retval, out
end

# Gets all of the nodes specified in the pcs config file for the cluster
def get_cluster_nodes(cluster_name)
  pcs_config = PCSConfig.new
  clusters = pcs_config.clusters
  cluster = nil
  for c in clusters
    pp c.nodes
    pp c.name
    pp cluster_name
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
  nodes = get_cluster_nodes(cluster_name)

  for node in nodes
    out = send_request_with_token(node,request, post, data, remote=true, raw_data)
    if out != '{"noresponse":true}'
      $logger.info request
      break
    end
  end
  return out
end

def send_request_with_token(node,request, post=false, data={}, remote=true, raw_data = nil)
  start = Time.now
  begin
    retval, token = get_node_token(node)
    token = token[0].strip
    if remote
      uri = URI.parse("https://#{node}:2224/remote/" + request)
    else
      uri = URI.parse("https://#{node}:2224/" + request)
    end

    p "Sending Request: " + uri.to_s
    if post
      req = Net::HTTP::Post.new(uri.path)
      raw_data ? req.body = raw_data : req.set_form_data(data)
    else
      req = Net::HTTP::Get.new(uri.path)
      req.set_form_data(data)
    end
    $logger.info("Request: " + uri.to_s + " (" + (Time.now-start).to_s + "s)")
    req.add_field("Cookie","token="+token)
    myhttp = Net::HTTP.new(uri.host, uri.port)
    myhttp.use_ssl = true
    myhttp.verify_mode = OpenSSL::SSL::VERIFY_NONE
    res = myhttp.start do |http|
      http.read_timeout = 5
      http.request(req)
    end
    output = res
    return output.body
  rescue Exception => e
    $logger.info "No response from: " + node
    return '{"noresponse":true}'
  end
end

def add_node(new_nodename)
  out, stderror, retval = run_cmd(PCS, "cluster", "localnode", "add", new_nodename)
  return retval, out.join("\n")
end

def remove_node(new_nodename)
  out, stderror, retval = run_cmd(PCS, "cluster", "localnode", "remove", new_nodename)
  return retval, out
end

def get_corosync_nodes()
  stdout, stderror, retval = run_cmd(PCS, "status", "nodes", "corosync")
  if retval != 0
    return nil
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
  result = send_cluster_request_with_token(params[:cluster], 'get_avail_resource_agents')
  ra = JSON.parse(result)
  if (ra["noresponse"] == true)
    return {}
  else
    return ra
  end
end

def get_stonith_agents_avail()
  sa = JSON.parse(send_cluster_request_with_token(params[:cluster], 'get_avail_fence_agents'))
  if (sa["noresponse"] == true)
    return {}
  else
    return sa
  end
end

def get_cluster_version()
  stdout, stderror, retval = run_cmd("corosync-cmapctl","totem.cluster_name")
  if retval != 0
    return ""
  else
    return stdout.join().gsub(/.*= /,"").strip
  end
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

def run_cmd(*args)
  $logger.info("Running: " + args.join(" "))
  start = Time.now
  stdin, stdout, stderror, waitth = Open3.popen3(*args)
  out = stdout.readlines()
  errout = stderror.readlines()
  retval = waitth.value.exitstatus
  duration = Time.now - start
  $logger.debug("Return Value: " + retval.to_s)
  $logger.debug(out)
  $logger.debug("Duration: " + duration.to_s + "s")
  return out, errout, retval
end
