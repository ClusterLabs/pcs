require 'json'
require 'net/http'
require 'uri'

# Commands for remote access
def remote(params)
  case (params[:command])
  when "status"
    return node_status(params)
  when "resource_status"
    return resource_status(params)
  when "create_cluster"
    return create_cluster(params)
  when "set_corosync_conf"
    if set_cluster_conf(params)
      return "Succeeded"
    else
      return "Failed"
    end
  when "cluster_start"
    return cluster_start()
  when "cluster_stop"
    return cluster_stop()
  when "resource_start"
    return resource_start(params)
  when "resource_stop"
    return resource_stop(params)
  end
end

def cluster_start()
    puts "Starting Daemons"
    puts `#{PCS} start`
end

def cluster_stop()
    puts "Starting Daemons"
    puts `#{PCS} stop`
end

def set_cluster_conf(params)
  if params[:corosync_conf] != nil and params[:corosync_conf] != ""
    FileUtils.cp(COROSYNC_CONF,COROSYNC_CONF + "." + Time.now.to_i.to_s)
    File.open("/etc/corosync/corosync.conf",'w') {|f|
      f.write(params[:corosync_conf])
    }
    return true
  else
    return false
    puts "Invalid corosync.conf file"
  end
end

def create_cluster(params)
  if set_cluster_conf(params)
    cluster_start()
  else
    return "Failed"
  end
end

def node_status(params)
  if params[:node] != nil and params[:node] != "" and params[:node] != @@cur_node_name
    begin
      uri = URI.parse("http://#{params[:node]}:2222/remote/status?hello=1")
      output = Net::HTTP::get_response(uri)
      return output.body
    rescue
      return '{"noresponse":true}'
    end
  end
  uptime = `uptime`.chomp
  `systemctl status corosync.service`
  corosync_status = $?.success?
  `systemctl status pacemaker.service`
  pacemaker_status = $?.success?
  status = {"uptime" => uptime, "corosync" => corosync_status, "pacemaker" => pacemaker_status }
  ret = JSON.generate(status)
  return ret
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
  pp params
  puts "RESOURCE STOP"
  puts "#{PCS} resource stop #{params[:resource]}"
  puts `#{PCS} resource stop #{params[:resource]}`
end

def resource_start(params)
  pp params
  puts "RESOURCE START"
  puts "#{PCS} resource start #{params[:resource]}"
  puts `#{PCS} resource start #{params[:resource]}`
end
