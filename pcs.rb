# Wrapper for PCS command
#

def add_location_constraint(resource, node, score)
  id = "loc_" + node + "_" + resource
  puts "ADD LOCATION CONSTRAINT"
  puts PCS, "constraint", "location", "add", id, resource, node, score
  Open3.popen3(PCS, "constraint", "location", "add", id, resource,
	       node, score) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def add_order_constraint(resourceA, resourceB, score, symmetrical = true)
  sym = symmetrical ? "symmetrical" : "nonsymmetrical"
  puts "ADD ORDER CONSTRAINT"
  puts PCS, "constraint", "order", "add", resourceA, resourceB, score, sym
  Open3.popen3(PCS, "constraint", "order", "add", resourceA,
	       resourceB, score, sym) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def add_colocation_constraint(resourceA, resourceB, score)
  puts "ADD COLOCATION CONSTRAINT"
  puts PCS, "constraint", "colocation", "add", resourceA, resourceB, score
  Open3.popen3(PCS, "constraint", "colocation", "add", resourceA,
	       resourceB, score) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def remove_constraint(constraint_id)
  stdout, stderror, retval = run_cmd(PCS, "constraint", "rm", constraint_id)
  puts stdout
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

  if cluster.nodes != nil
    nodes = cluster.nodes
  else
    print "Error: no nodes found for #{cluster}"
    nodes = []
  end
  return nodes
end

def send_cluster_request_with_token(cluster_name, request, post=false, data={}, remote=true)
  out = ""
  nodes = get_cluster_nodes(cluster_name)

  for node in nodes
    out = send_request_with_token(node,request, post=false, data, remote=true)
    if out != '{"noresponse":true}'
      puts "OUT"
      puts request
      break
    end
  end
  return out
end

def send_request_with_token(node,request, post=false, data={}, remote=true)
  start = Time.now
  begin
    retval, token = get_node_token(node)
    token = token[0].strip
    if remote
      uri = URI.parse("http://#{node}:2222/remote/" + request)
    else
      uri = URI.parse("http://#{node}:2222/" + request)
    end

    p "Sending Request: " + uri.to_s
    if post
      req = Net::HTTP::Post.new(uri.path)
      req.set_form_data(data)
    else
      req = Net::HTTP::Get.new(uri.path)
      req.set_form_data(data)
    end
    $logger.info("Request: " + uri.to_s + " (" + (Time.now-start).to_s + "s)")
    req.add_field("Cookie","token="+token)
    res = Net::HTTP.new(uri.host, uri.port).start do |http|
      http.read_timeout = 5
      http.request(req)
    end
    output = res
    return output.body
  rescue Exception => e
    puts "EXCEPTION"
    puts e
    puts "No response from: " + node
    return '{"noresponse":true}'
  end
end

def add_node(new_nodename)
  out, stderror, retval = run_cmd(PCS, "cluster", "localnode", "add", new_nodename)
  return retval, out
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
  ra = JSON.parse(send_cluster_request_with_token(params[:cluster], 'get_avail_resource_agents'))
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
  $logger.info("Return Value: " + retval.to_s)
  $logger.info(out)
  $logger.info("Duration: " + duration.to_s + "s")
  return out, errout, retval
end
