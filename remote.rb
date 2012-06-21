require 'json'
require 'net/http'
require 'uri'
require 'pcs.rb'

# Commands for remote access
def remote(params)
  case (params[:command])
  when "status"
    return node_status(params)
  when "auth"
    return auth(params)
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
    return cluster_start(params)
  when "cluster_stop"
    return cluster_stop(params)
  when "resource_start"
    return resource_start(params)
  when "resource_stop"
    return resource_stop(params)
  when "check_gui_status"
    return check_gui_status(params)
  end
end

def cluster_start(params)
  if params[:name]
    response = send_request_with_token(params[:name], 'cluster_start', true)
  else
    puts "Starting Daemons"
    puts `#{PCS} cluster start`
  end
end

def cluster_stop(params)
  if params[:name]
    response = send_request_with_token(params[:name], 'cluster_stop', true)
  else
    puts "Starting Daemons"
    puts `#{PCS} cluster stop`
  end
end

def set_cluster_conf(params)
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
    puts "Invalid corosync.conf file"
  end
end

def check_gui_status(params)
  node_results = {}
  if params[:nodes] != nil and params[:nodes] != ""
    node_array = params[:nodes].split(",")
   Open3.popen3(PCS, "cluster", "gui-status", *node_array) { |stdin, stdout, stderr, wait_thr|
     exit_status = wait_thr.value
     stdout.readlines.each {|l|
       l = l.chomp
       out = l.split(/: /)
       node_results[out[0]] = out[1]
     }
   }
  end
  return JSON.generate(node_results)
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
  in_pacemaker = false
  stdin, stdout, stderror, waitth = Open3.popen3("#{PCS} status nodes both")
  stdout.readlines.each {|l|
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
    else
      in_pacemaker ? pacemaker_offline.concat(nodes.split(/ /)) : corosync_offline.concat(nodes.split(/ /))
    end
  }

  status = {"uptime" => uptime, "corosync" => corosync_status, "pacemaker" => pacemaker_status,
 "corosync_online" => corosync_online, "corosync_offline" => corosync_offline,
 "pacemaker_online" => pacemaker_online, "pacemaker_offline" => pacemaker_offline }
  ret = JSON.generate(status)
  return ret
end

def auth(params)
  return PCSAuth.validUser(params['username'],params['password'])
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
