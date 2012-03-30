require 'json'
require 'net/http'
require 'uri'

# Commands for remote access
def remote(params)
  case (params[:command])
  when "status"
    return remote_status(params)
  when "set_corosync_conf"
    puts "#{params['corosync_conf']}"
  when "start_daemons"
    puts "Starting Daemons"
    puts `/etc/init.d/corosync start`
    puts `/etc/init.d/pacemaker start`
  end
end

def remote_status(params)
  if params[:node] != nil and params[:node] != "" and params[:node] != @@cur_node_name
    begin
      uri = URI.parse("http://#{params[:node]}:2222/remote/status?hello=1")
      output = Net::HTTP::get_response(uri)
      return output.body
    rescue
      return '[{"noresponse":true}]'
    end
  end
  uptime = `uptime`.chomp
  corosync_status = system("/etc/init.d/corosync", "status")
  pacemaker_status = system("/etc/init.d/pacemaker", "status")
  status = {"uptime" => uptime, "corosync" => corosync_status, "pacemaker" => pacemaker_status }
  ret = JSON.generate(status)
  return ret
end

def resource_status(params)
  resource_id = params[:resource]
  @resources = getResources
  location = ""
  @resources.each {|r|
    if r.id == resource_id
      if r.failed
	status =  "Failed"
      elsif !r.active
	status = "Inactive"
      else
	status = "Running"
      end
      if r.nodes.length != 0
	location = r.nodes[0].name
	break
      end
    end
  }
  status = ["location" => location, "status" => status]
  return JSON.generate(status)
end
